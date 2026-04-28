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
    def __init__(self):
        self.client = None

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

    def get_embedding(self, text):
        self.init_client()
        if not self.client:
            return None
        try:
            models_to_try = ["models/embedding-001", "models/text-embedding-004"]
            for model in models_to_try:
                try:
                    result = self.client.models.embed_content(model=model, contents=text)
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
        if vector is not None:
            vectors = self.load_vectors(uid)
            mem_id = str(uuid.uuid4())
            vectors[mem_id] = {
                "text": text,
                "embedding": vector,
                "metadata": metadata or {}
            }
            self.save_vectors(uid, vectors, new_id=mem_id)
            print(f"[VectorStore] Added memory: {text[:30]}...")

    def search(self, uid, query, top_k=3):
        vectors = self.load_vectors(uid)
        if not vectors:
            return []

        query_vec = self.get_embedding(query)
        if query_vec is None:
            return []

        results = []
        for mid, data in vectors.items():
            db_vec = data["embedding"]
            similarity = np.dot(query_vec, db_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(db_vec))
            results.append((similarity, data["text"], data["metadata"]))

        results.sort(key=lambda x: x[0], reverse=True)
        return results[:top_k]
