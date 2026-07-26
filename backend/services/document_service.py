"""
Kautilya AI — Document Study Service.

THE PROBLEM THIS SOLVES
-----------------------
The old path extracted a document's text, cut it at 60k chars, and pasted it
into ONE message. Three failures fell out of that:
  1. Anything past ~15k tokens was silently invisible to the model.
  2. The document lived in a single turn — after history trimming, follow-up
     questions were answered from memory of the answer, not from the document.
  3. No anchors, so the model couldn't cite a page and couldn't be checked.

WHAT THIS DOES INSTEAD
----------------------
Ingest the WHOLE document once, then feed the model what each question needs:

  small doc  (< INLINE_FULL_TEXT_LIMIT)
      Stored whole. Re-injected in full on every turn that references it —
      highest fidelity, no retrieval loss.

  large doc
      Split into overlapping chunks that keep their page/section anchors,
      embedded, and stored. Every turn injects:
        • the DOCUMENT MAP (title, pages, outline) so the model knows the
          shape of the whole thing, and
        • the passages that actually answer THIS question, each labelled with
          its page/section so the model can cite it and the user can verify.

Degrades honestly: no Gemini key → keyword scoring instead of embeddings; no
Firestore → in-process cache for the life of the worker. It says so in the
context block rather than pretending it read everything.
"""
import hashlib
import re
import time
import threading

import numpy as np

# ── Tuning ───────────────────────────────────────────────────────────────────
INLINE_FULL_TEXT_LIMIT = 24_000     # chars — below this, keep the whole doc inline
CHUNK_CHARS = 1_400                 # ~350 tokens per chunk
CHUNK_OVERLAP = 200                 # keeps sentences from being cut mid-thought
MAX_CHUNKS = 800                    # ~1.1M chars ceiling per document
EMBED_BATCH = 64                    # Gemini batch size
DEFAULT_TOP_K = 8                   # passages injected per question
MAX_OUTLINE_ENTRIES = 45
CONTEXT_CHAR_BUDGET = 45_000        # ceiling on everything injected per turn
_CACHE_TTL_SEC = 1800

# doc_id → {"meta": {...}, "chunks": [...], "expires": ts}
_DOC_CACHE = {}
_CACHE_LOCK = threading.Lock()

# Headings we recognise when building the outline: markdown, numbered sections,
# ALL-CAPS lines, and the "--- Page N ---" anchors the PDF extractor emits.
_HEADING_RE = re.compile(
    r'^(?:#{1,4}\s+.+'                      # markdown: ## Title
    r'|\d+(?:\.\d+)*\.?\s+[A-Z].{2,80}'     # numbered: "4.2 Scope" and "4. Scope"
    r'|[A-Z][A-Z0-9 &/,\'\-]{6,70}'         # ALL CAPS SECTION
    r'|--- Page \d+ ---)$'                  # page anchors from the PDF extractor
)
_PAGE_RE = re.compile(r'^--- Page (\d+) ---$', re.MULTILINE)


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion
# ─────────────────────────────────────────────────────────────────────────────
def make_doc_id(uid, filename, text):
    """Stable id — re-uploading the same file to the same user reuses the
    existing ingestion instead of paying to embed it twice."""
    h = hashlib.sha256()
    h.update((uid or 'guest').encode('utf-8', 'ignore'))
    h.update((filename or '').encode('utf-8', 'ignore'))
    h.update(str(len(text or '')).encode())
    h.update((text or '')[:4096].encode('utf-8', 'ignore'))
    return h.hexdigest()[:24]


def chunk_document(text):
    """Split into overlapping chunks, tagging each with the page and the last
    heading seen above it. Those anchors are what make citation possible."""
    if not text:
        return []

    lines = text.split('\n')
    chunks = []
    buf = []
    buf_len = 0
    cur_page = None
    cur_heading = None
    chunk_start_page = None
    chunk_start_heading = None

    def flush():
        nonlocal buf, buf_len, chunk_start_page, chunk_start_heading
        body = '\n'.join(buf).strip()
        if body:
            chunks.append({
                "text": body,
                "page": chunk_start_page,
                "heading": chunk_start_heading,
            })
        # Carry the tail forward so a sentence split across the boundary still
        # appears whole in one of the two chunks.
        if CHUNK_OVERLAP > 0 and body:
            tail = body[-CHUNK_OVERLAP:]
            buf = [tail]
            buf_len = len(tail)
        else:
            buf = []
            buf_len = 0
        chunk_start_page = cur_page
        chunk_start_heading = cur_heading

    for line in lines:
        stripped = line.strip()
        m = _PAGE_RE.match(stripped)
        if m:
            cur_page = int(m.group(1))
        elif stripped and _HEADING_RE.match(stripped):
            cur_heading = stripped.lstrip('#').strip()[:120]

        if chunk_start_page is None:
            chunk_start_page = cur_page
        if chunk_start_heading is None:
            chunk_start_heading = cur_heading

        buf.append(line)
        buf_len += len(line) + 1
        if buf_len >= CHUNK_CHARS:
            flush()
        if len(chunks) >= MAX_CHUNKS:
            break

    if len(chunks) < MAX_CHUNKS:
        flush()

    return chunks[:MAX_CHUNKS]


def build_outline(text):
    """Headings in document order — the model's map of the whole document."""
    out = []
    for line in text.split('\n'):
        s = line.strip()
        if not s or _PAGE_RE.match(s):
            continue
        if _HEADING_RE.match(s):
            clean = s.lstrip('#').strip()
            if clean and clean not in out:
                out.append(clean[:110])
        if len(out) >= MAX_OUTLINE_ENTRIES:
            break
    return out


def _embed_batch(texts):
    """Embed a list of strings. Returns a list of np arrays (None where failed).

    Uses the same Gemini model as the memory vector store so a document chunk
    and a memory live in the same space.
    """
    from services.vector_store_service import VectorStore

    store = VectorStore()
    store.init_client()
    if not store.client:
        return [None] * len(texts)

    model = VectorStore._working_model or "models/text-embedding-004"
    out = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        try:
            result = store.client.models.embed_content(model=model, contents=batch)
            embs = [np.array(e.values) for e in result.embeddings]
            if len(embs) != len(batch):
                raise ValueError(f"embedding count mismatch: {len(embs)} vs {len(batch)}")
            out.extend(embs)
            VectorStore._working_model = model
        except Exception as e:
            print(f"[DocService] Batch embed failed ({len(batch)} chunks): {e} — falling back to per-chunk")
            for t in batch:
                try:
                    out.append(store.get_embedding(t))
                except Exception:
                    out.append(None)
    return out


def ingest_document(uid, session_id, filename, text, kind="document"):
    """Ingest a document end to end. Returns its metadata dict.

    Idempotent by content hash: the same file re-uploaded is a cache hit.
    """
    if not text or not text.strip():
        return None

    text = text.strip()
    doc_id = make_doc_id(uid, filename, text)

    cached = _cache_get(doc_id)
    if cached:
        meta = dict(cached["meta"])
        meta["cached"] = True
        _register_session_doc(uid, session_id, doc_id, meta)
        return meta

    pages = [int(p) for p in _PAGE_RE.findall(text)]
    meta = {
        "doc_id": doc_id,
        "filename": filename,
        "kind": kind,
        "chars": len(text),
        "words": len(text.split()),
        "pages": max(pages) if pages else None,
        "outline": build_outline(text),
        "session_id": session_id,
        "created_at": time.time(),
        "truncated": False,
        "retrieval": "none",
    }

    # ---- Small doc: keep it whole. Nothing beats the actual text. ----
    if len(text) <= INLINE_FULL_TEXT_LIMIT:
        meta["mode"] = "full"
        meta["retrieval"] = "full-text"
        _cache_put(doc_id, meta, [{"text": text, "page": None, "heading": None, "embedding": None}])
        _persist(uid, doc_id, meta, full_text=text)
        _register_session_doc(uid, session_id, doc_id, meta)
        print(f"[DocService] {filename}: {len(text)} chars kept inline (full mode)")
        return meta

    # ---- Large doc: chunk + embed ----
    chunks = chunk_document(text)
    if not chunks:
        return None
    meta["mode"] = "chunked"
    meta["chunk_count"] = len(chunks)
    meta["truncated"] = len(text) > MAX_CHUNKS * CHUNK_CHARS

    embeddings = _embed_batch([c["text"] for c in chunks])
    embedded = sum(1 for e in embeddings if e is not None)
    for c, e in zip(chunks, embeddings):
        c["embedding"] = e
    meta["retrieval"] = "semantic" if embedded else "keyword"
    meta["embedded_chunks"] = embedded

    _cache_put(doc_id, meta, chunks)
    _persist(uid, doc_id, meta, chunks=chunks)
    _register_session_doc(uid, session_id, doc_id, meta)
    print(f"[DocService] {filename}: {len(text)} chars → {len(chunks)} chunks, "
          f"{embedded} embedded ({meta['retrieval']})")
    return meta


# ─────────────────────────────────────────────────────────────────────────────
# Cache + persistence
# ─────────────────────────────────────────────────────────────────────────────
def _cache_get(doc_id):
    with _CACHE_LOCK:
        entry = _DOC_CACHE.get(doc_id)
        if entry and entry["expires"] > time.time():
            return entry
        if entry:
            _DOC_CACHE.pop(doc_id, None)
    return None


def _cache_put(doc_id, meta, chunks):
    with _CACHE_LOCK:
        # Keep the cache bounded — drop the oldest when it grows.
        if len(_DOC_CACHE) > 40:
            oldest = sorted(_DOC_CACHE.items(), key=lambda kv: kv[1]["expires"])[:10]
            for k, _ in oldest:
                _DOC_CACHE.pop(k, None)
        _DOC_CACHE[doc_id] = {
            "meta": meta,
            "chunks": chunks,
            "expires": time.time() + _CACHE_TTL_SEC,
        }


def _persist(uid, doc_id, meta, chunks=None, full_text=None):
    """Best-effort Firestore write so the document survives worker restarts and
    is visible to other workers. Never fatal — the cache still serves this one."""
    if not uid:
        return
    try:
        from extensions import db
        if not db:
            return
        doc_ref = db.collection('users').document(uid).collection('documents').document(doc_id)
        payload = {k: v for k, v in meta.items() if k != 'outline'}
        payload['outline'] = meta.get('outline', [])[:MAX_OUTLINE_ENTRIES]
        if full_text is not None:
            payload['full_text'] = full_text[:INLINE_FULL_TEXT_LIMIT]
        doc_ref.set(payload, merge=True)

        if chunks:
            # 768 floats per chunk blows the 1MB document ceiling fast, so
            # chunks live in a subcollection, written in batches of 400.
            col = doc_ref.collection('chunks')
            batch = db.batch()
            n = 0
            for i, c in enumerate(chunks):
                emb = c.get("embedding")
                batch.set(col.document(str(i)), {
                    "text": c["text"],
                    "page": c.get("page"),
                    "heading": c.get("heading"),
                    "embedding": emb.tolist() if emb is not None else None,
                })
                n += 1
                if n >= 400:
                    batch.commit()
                    batch = db.batch()
                    n = 0
            if n:
                batch.commit()
    except Exception as e:
        print(f"[DocService] persist failed for {doc_id}: {e}")


def _load_from_firestore(uid, doc_id):
    try:
        from extensions import db
        if not db or not uid:
            return None
        doc_ref = db.collection('users').document(uid).collection('documents').document(doc_id)
        snap = doc_ref.get()
        if not snap.exists:
            return None
        meta = snap.to_dict() or {}
        if meta.get('mode') == 'full':
            chunks = [{"text": meta.get('full_text', ''), "page": None,
                       "heading": None, "embedding": None}]
        else:
            chunks = []
            for cdoc in doc_ref.collection('chunks').stream():
                c = cdoc.to_dict() or {}
                emb = c.get('embedding')
                chunks.append({
                    "text": c.get('text', ''),
                    "page": c.get('page'),
                    "heading": c.get('heading'),
                    "embedding": np.array(emb) if emb else None,
                })
        if not chunks:
            return None
        _cache_put(doc_id, meta, chunks)
        return _cache_get(doc_id)
    except Exception as e:
        print(f"[DocService] Firestore load failed for {doc_id}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Session ↔ document registry
# ─────────────────────────────────────────────────────────────────────────────
# session_id → [meta, …]. In-process; Firestore metadata is the durable copy.
_SESSION_DOCS = {}


def _register_session_doc(uid, session_id, doc_id, meta):
    if not session_id:
        return
    with _CACHE_LOCK:
        docs = _SESSION_DOCS.setdefault(session_id, [])
        if not any(d["doc_id"] == doc_id for d in docs):
            docs.append(meta)
        # A conversation only carries its most recent handful of documents.
        if len(docs) > 6:
            del docs[0:len(docs) - 6]


def get_session_documents(uid, session_id):
    """Documents attached to this conversation, newest last."""
    if not session_id:
        return []
    with _CACHE_LOCK:
        docs = list(_SESSION_DOCS.get(session_id, []))
    if docs:
        return docs
    # Cold worker / restart: recover from Firestore.
    try:
        from extensions import db
        if not db or not uid:
            return []
        q = (db.collection('users').document(uid).collection('documents')
             .where('session_id', '==', session_id).limit(6))
        found = [d.to_dict() for d in q.stream()]
        found.sort(key=lambda m: m.get('created_at') or 0)
        with _CACHE_LOCK:
            _SESSION_DOCS[session_id] = found
        return found
    except Exception as e:
        print(f"[DocService] session doc lookup failed: {e}")
        return []


def clear_session_documents(session_id):
    with _CACHE_LOCK:
        _SESSION_DOCS.pop(session_id, None)


# ─────────────────────────────────────────────────────────────────────────────
# Retrieval
# ─────────────────────────────────────────────────────────────────────────────
_STOPWORDS = {
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'any', 'can', 'her', 'was',
    'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new',
    'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'she', 'use', 'way', 'this', 'that',
    'with', 'from', 'they', 'have', 'what', 'when', 'were', 'been', 'their', 'which',
    'would', 'there', 'about', 'into', 'more', 'other', 'than', 'then', 'them', 'these',
    'some', 'will', 'your', 'said', 'each', 'does', 'shall', 'such',
}


def _keyword_rank(query, chunks):
    """Fallback ranking when embeddings are unavailable.

    Plain term-overlap ranks filler text highly, because common words match
    everywhere. This weights each query term by how RARE it is in this document
    (idf), so "termination" outranks "for" — which is the whole point when the
    semantic index is down.
    """
    import math

    q_terms = {w for w in re.findall(r'\w+', query.lower())
               if len(w) > 2 and w not in _STOPWORDS}
    if not q_terms:
        return [(0.0, c) for c in chunks]

    tokenised = [set(re.findall(r'\w+', c["text"].lower())) for c in chunks]
    n = len(chunks)

    idf = {}
    for term in q_terms:
        df = sum(1 for toks in tokenised if term in toks)
        # A term in every chunk carries no signal; a term in one chunk carries a lot.
        idf[term] = math.log((n + 1) / (df + 1)) + 0.1

    scored = []
    for c, toks in zip(chunks, tokenised):
        score = sum(idf[t] for t in q_terms if t in toks)
        # Reward chunks matching several distinct query terms, not one repeated.
        matched = sum(1 for t in q_terms if t in toks)
        if matched > 1:
            score *= 1 + 0.15 * (matched - 1)
        scored.append((score, c))
    return scored


def retrieve(uid, doc_meta, query, top_k=DEFAULT_TOP_K):
    """Top passages from one document for this question."""
    doc_id = doc_meta.get('doc_id')
    entry = _cache_get(doc_id) or _load_from_firestore(uid, doc_id)
    if not entry:
        return []
    chunks = entry["chunks"]
    if not chunks:
        return []

    # Full-text docs aren't retrieved — they're injected whole.
    if entry["meta"].get('mode') == 'full':
        return [{"text": chunks[0]["text"], "page": None, "heading": None, "score": 1.0}]

    query_vec = None
    if any(c.get("embedding") is not None for c in chunks):
        try:
            from services.vector_store_service import VectorStore
            query_vec = VectorStore().get_embedding(query)
        except Exception as e:
            print(f"[DocService] query embed failed: {e}")

    scored = []
    if query_vec is not None:
        nq = np.linalg.norm(query_vec)
        for c in chunks:
            emb = c.get("embedding")
            if emb is None or nq == 0:
                continue
            nd = np.linalg.norm(emb)
            if nd == 0:
                continue
            scored.append((float(np.dot(query_vec, emb) / (nq * nd)), c))

    if not scored:  # no embeddings, or all failed
        scored = _keyword_rank(query, chunks)

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [
        {"text": c["text"], "page": c.get("page"), "heading": c.get("heading"), "score": s}
        for s, c in scored[:top_k] if s > 0
    ]
    # Reading order beats relevance order once the set is chosen — the model
    # reasons better over passages that flow the way the document does.
    picked.sort(key=lambda p: (p["page"] is None, p["page"] or 0))
    return picked


def build_document_context(uid, session_id, query, top_k=DEFAULT_TOP_K):
    """The block injected into the prompt for this turn. "" when no documents."""
    docs = get_session_documents(uid, session_id)
    if not docs:
        return ""

    # Newest document first: when several are attached and the budget runs out,
    # the one the user just uploaded is the one they're asking about.
    docs = list(reversed(docs))
    budget = CONTEXT_CHAR_BUDGET
    per_doc_budget = max(6_000, CONTEXT_CHAR_BUDGET // max(1, len(docs)))

    sections = []
    for meta in docs:
        if budget <= 0:
            break
        name = meta.get('filename', 'document')
        bits = []
        if meta.get('pages'):
            bits.append(f"{meta['pages']} pages")
        if meta.get('words'):
            bits.append(f"{meta['words']:,} words")
        stat = ", ".join(bits) or f"{meta.get('chars', 0):,} chars"

        header = f"### {name} ({stat})"
        body = []

        outline = meta.get('outline') or []
        if outline and meta.get('mode') != 'full':
            body.append("DOCUMENT MAP (headings in order): " + " · ".join(outline[:MAX_OUTLINE_ENTRIES]))

        passages = retrieve(uid, meta, query, top_k=top_k)
        if not passages:
            continue

        if meta.get('mode') == 'full':
            full = passages[0]["text"]
            if len(full) > per_doc_budget:
                # Several documents in one chat can't each claim the whole
                # window. Trim, and TELL the model it's looking at a slice.
                full = (full[:per_doc_budget]
                        + f"\n…[trimmed to fit — {len(passages[0]['text']) - per_doc_budget:,} "
                          f"chars of this document are not shown. Say so rather than "
                          f"assuming the rest says nothing.]")
            body.append("FULL TEXT:\n" + full)
        else:
            body.append(f"RELEVANT PASSAGES for the current question "
                        f"({len(passages)} of {meta.get('chunk_count', '?')} sections):")
            used = 0
            for p in passages:
                if used + len(p["text"]) > per_doc_budget:
                    break
                anchor = []
                if p.get("page"):
                    anchor.append(f"p.{p['page']}")
                if p.get("heading"):
                    anchor.append(p["heading"])
                label = " — ".join(anchor) if anchor else "excerpt"
                body.append(f"\n[{label}]\n{p['text']}")
                used += len(p["text"])
            if meta.get('truncated'):
                body.append(f"\n[NOTE: {name} exceeded the ingestion ceiling — the tail of the "
                            f"document was not indexed. Say so if the answer might live there.]")
            if meta.get('retrieval') == 'keyword':
                body.append("\n[NOTE: retrieved by keyword match, not semantic search — "
                            "relevant passages may have been missed. Say so if the excerpts "
                            "don't clearly answer the question.]")

        section = header + "\n" + "\n".join(body)
        sections.append(section)
        budget -= len(section)

    if not sections:
        return ""

    return (
        "\n\n═══ ATTACHED DOCUMENTS ═══\n"
        "The user has attached the document(s) below. Passages were selected for THIS "
        "question from the full ingested text.\n\n"
        "HOW TO USE THEM:\n"
        "- Answer from these passages, not from memory. Cite the page or heading when you "
        "make a specific claim (e.g. \"p.14\" or \"under Termination\").\n"
        "- These are EXCERPTS of a larger document, not the whole of it. If the answer "
        "isn't in them, say so plainly and tell the user which section to point you at — "
        "never fill the gap by guessing.\n"
        "- If the document contradicts what you believe, the document wins for questions "
        "about the document. Say when it contradicts general fact.\n\n"
        + "\n\n".join(sections)
        + "\n═══ END DOCUMENTS ═══\n"
    )
