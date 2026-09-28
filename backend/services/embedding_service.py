"""
Kautilya AI — Embedding Service
Vector embeddings via NVIDIA's NeMo Retriever models on the hosted NIM API
(integrate.api.nvidia.com, OpenAI-compatible /v1/embeddings).
"""
import os
import requests
import time
from typing import List, Dict

# Reuse the SAME NVIDIA credentials the rest of the app already uses. The old
# code read a bespoke `NVIDIA_NIM_API_KEY` that is never set in deployment, so
# every embed call short-circuited to "no key" and silently returned nothing —
# which is why uploads/crawls produced zero embeddings.
try:
    from config import NVIDIA_API_KEY, NVIDIA_API_KEYS
except Exception:
    NVIDIA_API_KEY, NVIDIA_API_KEYS = "", []

# Optional explicit override (kept for backwards-compat); falls back to the
# shared NVIDIA keys below.
NVIDIA_NIM_API_KEY = os.environ.get("NVIDIA_NIM_API_KEY", "")
NVIDIA_NIM_BASE_URL = os.environ.get("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")

# Model is env-overridable. `baai/bge-m3` is a live, multilingual (100+ langs),
# single-mode embedding NIM on integrate.api.nvidia.com — it replaced the retired
# `llama-3.2-nv-embedqa-1b-v2` (EOL 2026-05-18). Set EMBED_MODEL to swap it
# without code changes; the input_type field is auto-added only for the models
# that need it (see _model_uses_input_type).
EMBED_MODEL = os.environ.get("EMBED_MODEL", "baai/bge-m3")
EMBED_BATCH_SIZE = 24       # max batch the embedding endpoint accepts
EMBED_DIMENSION = 1024      # native output dim for bge-m3


def _model_uses_input_type(model: str) -> bool:
    """NeMo Retriever dual-mode models (embedqa / e5 / nemotron-embed / nv-embed)
    REQUIRE an input_type ("query"/"passage"). Single-mode models (BGE / GTE /
    GTR) don't accept it and can 400 if it's sent, so we omit it for those."""
    m = (model or "").lower()
    return not any(tag in m for tag in ("bge", "gte", "gtr"))


def _embedding_api_keys() -> List[str]:
    """All usable NVIDIA keys, explicit override first, de-duplicated."""
    keys: List[str] = []
    for k in [NVIDIA_NIM_API_KEY, NVIDIA_API_KEY, *(NVIDIA_API_KEYS or [])]:
        if k and k not in keys:
            keys.append(k)
    return keys


def embed_texts(texts: List[str], model: str = EMBED_MODEL,
                input_type: str = "passage") -> List[List[float]]:
    """
    Generate embeddings for a list of texts via NVIDIA NIM.

    Args:
        texts: list of strings to embed.
        model: model id (default: env EMBED_MODEL).
        input_type: "passage" when indexing documents, "query" when embedding a
            search query. NVIDIA's retriever models REQUIRE this — using the
            wrong one tanks retrieval accuracy.

    Returns:
        One embedding vector per input (empty list for any batch that failed).
    """
    if not texts:
        return []

    keys = _embedding_api_keys()
    if not keys:
        print("[Embedding] No NVIDIA API key configured (NVIDIA_API_KEY / NVIDIA_NIM_API_KEY) "
              "— skipping embeddings", flush=True)
        return [[] for _ in texts]

    all_embeddings: List[List[float]] = []

    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i:i + EMBED_BATCH_SIZE]
        payload = {
            "input": batch,
            "model": model,
            "encoding_format": "float",
            "truncate": "END",          # safety net if a chunk exceeds context
        }
        # Dual-mode NeMo Retriever models require input_type; single-mode models
        # (bge/gte/gtr) reject it — so only send it when the model uses it.
        if _model_uses_input_type(model):
            payload["input_type"] = input_type

        batch_vectors = None
        last_err = None
        for key in keys:
            try:
                resp = requests.post(
                    f"{NVIDIA_NIM_BASE_URL}/embeddings",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                    timeout=60,
                )
            except Exception as e:
                last_err = f"request error: {e}"
                continue  # network blip — try the next key

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    batch_vectors = [item["embedding"] for item in data["data"]]
                except Exception as e:
                    last_err = f"parse error: {e}; body={resp.text[:200]}"
                break  # got a 200 — don't rotate keys further

            last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            # Only key rotation helps for auth / rate-limit; a 400/404/5xx means
            # the request itself is the problem (bad model id, etc.).
            if resp.status_code in (401, 403, 429):
                continue
            break

        if batch_vectors is None:
            print(f"[Embedding] batch {i // EMBED_BATCH_SIZE + 1} failed "
                  f"(model={model}): {last_err}", flush=True)
            all_embeddings.extend([[] for _ in batch])
        else:
            all_embeddings.extend(batch_vectors)

        if i + EMBED_BATCH_SIZE < len(texts):
            time.sleep(0.1)  # be gentle with rate limits

    return all_embeddings


def embed_text(text: str, model: str = EMBED_MODEL,
               input_type: str = "query") -> List[float]:
    """Embed a single text. Defaults to "query" input_type for retrieval."""
    embeddings = embed_texts([text], model=model, input_type=input_type)
    return embeddings[0] if embeddings else []


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors (0..1)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def search_similar_chunks(query: str, chunks: List[Dict], top_k: int = 4) -> List[Dict]:
    """
    Rank stored chunks by similarity to a query.

    Args:
        query: search query.
        chunks: list of chunk dicts each carrying an 'embedding' vector.
        top_k: how many top results to return.
    """
    if not chunks:
        return []

    query_embedding = embed_text(query, input_type="query")
    if not query_embedding:
        return []

    scored = []
    for chunk in chunks:
        chunk_embedding = chunk.get("embedding", [])
        if chunk_embedding:
            scored.append({
                **chunk,
                "similarity": cosine_similarity(query_embedding, chunk_embedding),
            })

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping fixed-size chunks."""
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def process_document_for_embedding(text: str, source_name: str = "",
                                   source_type: str = "text") -> List[Dict]:
    """
    Chunk a document and embed each chunk (as a "passage").

    Returns a list of chunk dicts with text, embedding and metadata. Chunks whose
    embedding failed are dropped so we never persist empty vectors.
    """
    chunks = chunk_text(text)
    embeddings = embed_texts(chunks, input_type="passage")

    result = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        if embedding:  # only keep successfully-embedded chunks
            result.append({
                "id": f"{source_name}_chunk_{i}" if source_name else f"chunk_{i}",
                "text": chunk,
                "embedding": embedding,
                "source": source_name,
                "source_type": source_type,
                "chunk_index": i,
                "created_at": time.time(),
            })
    return result
