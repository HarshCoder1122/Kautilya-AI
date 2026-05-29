"""
Kautilya AI — Vector Store Service
Embedding-based memory system using Google GenAI.
"""
import os
import json
import uuid
import numpy as np

from config import GEMINI_API_KEYS, CHAT_DATA_DIR


def _get_user_chat_dir(uid):
    """Get or create per-user chat data directory."""
    user_dir = os.path.join(CHAT_DATA_DIR, uid)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


class VectorStore:
    # Class-level TTL cache: {uid: (vectors_dict, expires_at)}. The vectors
    # rarely change between messages but were being re-streamed from
    # Firestore on every chat call, costing 300-800ms TTFT per request.
    _CACHE = {}
    _CACHE_TTL_SEC = 60

    def __init__(self):
        self.client = None

    @classmethod
    def invalidate_cache(cls, uid):
        cls._CACHE.pop(uid, None)

    def init_client(self):
        if not self.client and GEMINI_API_KEYS:
            try:
                from google.genai import Client as GenAIClient
                self.client = GenAIClient(api_key=GEMINI_API_KEYS[0])
            except Exception as e:
                print(f"[VectorStore] Client init failed: {e}")

    def load_vectors(self, uid):
        vectors = {}
        if not uid:
            return vectors

        # Cache check: avoid re-streaming Firestore on every chat message.
        import time as _t
        cached = VectorStore._CACHE.get(uid)
        if cached and cached[1] > _t.time():
            return cached[0]

        # 1. Try Firestore First
        from extensions import db
        if db:
            try:
                from firebase_admin import firestore as _fs
                memories_ref = db.collection('users').document(uid).collection('memories')
                docs = memories_ref.stream()
                for doc in docs:
                    v = doc.to_dict()
                    vectors[doc.id] = {
                        "text": v["text"],
                        "embedding": np.array(v["embedding"]),
                        "metadata": v.get("metadata", {})
                    }
                if vectors:
                    print(f"[VectorStore] Loaded {len(vectors)} memories from Firestore.")
                    VectorStore._CACHE[uid] = (vectors, _t.time() + VectorStore._CACHE_TTL_SEC)
                    return vectors
            except Exception as e:
                print(f"[VectorStore] Firestore load failed: {e}")

        # 2. Fallback to Local Filesystem (Legacy)
        try:
            user_dir = _get_user_chat_dir(uid)
            vec_file = os.path.join(user_dir, 'vectors.json')
            if os.path.exists(vec_file):
                with open(vec_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for k, v in data.items():
                        vectors[k] = {
                            "text": v["text"],
                            "embedding": np.array(v["embedding"]),
                            "metadata": v.get("metadata", {})
                        }
                print(f"[VectorStore] Loaded {len(vectors)} memories from local JSON.")
        except Exception as e:
            print(f"[VectorStore] Local load failed: {e}")
        return vectors

    def save_vectors(self, uid, vectors, new_id=None):
        if not uid:
            return
        # Invalidate cache so the next read sees the new entries.
        VectorStore._CACHE.pop(uid, None)

        from extensions import db

        # 1. Save to Firestore
        if db:
            try:
                from firebase_admin import firestore as _fs
                if new_id and new_id in vectors:
                    v = vectors[new_id]
                    db.collection('users').document(uid).collection('memories').document(new_id).set({
                        "text": v["text"],
                        "embedding": v["embedding"].tolist(),
                        "metadata": v.get("metadata", {}),
                        "timestamp": _fs.SERVER_TIMESTAMP
                    })
                else:
                    batch = db.batch()
                    mem_ref = db.collection('users').document(uid).collection('memories')
                    for mid, v in vectors.items():
                        batch.set(mem_ref.document(mid), {
                            "text": v["text"],
                            "embedding": v["embedding"].tolist(),
                            "metadata": v.get("metadata", {})
                        })
                    batch.commit()
            except Exception as e:
                print(f"[VectorStore] Firestore save failed: {e}")

        # 2. Local Sync (Redundancy)
        try:
            user_dir = _get_user_chat_dir(uid)
            vec_file = os.path.join(user_dir, 'vectors.json')
            serializable = {}
            for k, v in vectors.items():
                serializable[k] = {
                    "text": v["text"],
                    "embedding": v["embedding"].tolist(),
                    "metadata": v["metadata"]
                }
            with open(vec_file, 'w', encoding='utf-8') as f:
                json.dump(serializable, f)
        except Exception as e:
            print(f"[VectorStore] Local save failed: {e}")

    # Cache the embedding model that works — avoids repeated 404 round-trips.
    _working_model = None

    def get_embedding(self, text):
        self.init_client()
        if not self.client:
            return None
        try:
            # Try cached model first to skip the fallback loop on every call.
            if VectorStore._working_model:
                try:
                    result = self.client.models.embed_content(model=VectorStore._working_model, contents=text)
                    return np.array(result.embeddings[0].values)
                except Exception:
                    VectorStore._working_model = None  # reset — try all again

            # Prefer text-embedding-004 (current); embedding-001 often 404s.
            models_to_try = ["models/text-embedding-004", "models/embedding-001"]
            for model in models_to_try:
                try:
                    result = self.client.models.embed_content(model=model, contents=text)
                    VectorStore._working_model = model  # remember for next call
                    return np.array(result.embeddings[0].values)
                except Exception as e:
                    if "404" in str(e) or "NOT_FOUND" in str(e):
                        continue
                    continue
            return None
        except Exception as e:
            print(f"[VectorStore] Embedding failed: {e}")
            return None

    def add_memory(self, uid, text, metadata=None):
        if not text:
            return
        vector = self.get_embedding(text)
        if vector is None:
            return
        mem_id = str(uuid.uuid4())
        entry = {
            "text": text,
            "embedding": vector,
            "metadata": metadata or {}
        }

        # Fast path: write single doc to Firestore directly instead of
        # load-all → append → save-all.  The old approach re-streamed every
        # memory just to add one, costing 300-800ms.
        from extensions import db
        if db:
            try:
                from firebase_admin import firestore as _fs
                db.collection('users').document(uid).collection('memories').document(mem_id).set({
                    "text": text,
                    "embedding": vector.tolist(),
                    "metadata": metadata or {},
                    "timestamp": _fs.SERVER_TIMESTAMP
                })
                # Invalidate cache so next search sees this new memory.
                VectorStore._CACHE.pop(uid, None)
                print(f"[VectorStore] Added memory (fast path): {text[:30]}...")
                return
            except Exception as e:
                print(f"[VectorStore] Firestore direct write failed, falling back: {e}")

        # Fallback: load-all + save-all (local filesystem or Firestore failure)
        vectors = self.load_vectors(uid)
        vectors[mem_id] = entry
        self.save_vectors(uid, vectors, new_id=mem_id)
        print(f"[VectorStore] Added memory (fallback path): {text[:30]}...")

    def search(self, uid, query, top_k=3):
        vectors = self.load_vectors(uid)
        if not vectors:
            return []

        query_vec = self.get_embedding(query)
        if query_vec is not None:
            # Cosine similarity search — pre-compute query norm once.
            norm_q = np.linalg.norm(query_vec)
            if norm_q == 0:
                return []
            results = []
            for mid, data in vectors.items():
                db_vec = data["embedding"]
                norm_d = np.linalg.norm(db_vec)
                if norm_d == 0:
                    continue
                similarity = np.dot(query_vec, db_vec) / (norm_q * norm_d)
                results.append((float(similarity), data["text"], data["metadata"]))
            results.sort(key=lambda x: x[0], reverse=True)
            return results[:top_k]

        # Fallback: keyword overlap search when Gemini embeddings unavailable
        query_words = set(query.lower().split())
        results = []
        for mid, data in vectors.items():
            text = data["text"]
            text_words = set(text.lower().split())
            overlap = len(query_words & text_words)
            if overlap > 0:
                results.append((overlap, text, data["metadata"]))
        results.sort(key=lambda x: x[0], reverse=True)
        return [(1.0, r[1], r[2]) for r in results[:top_k]]
