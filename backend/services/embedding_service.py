"""
Kautilya AI — Embedding Service
Handles vector embeddings using NVIDIA's llama-nemotron-embed-1b-v2 model via NIM API.
"""
import os
import requests
import json
import time
from typing import List, Dict, Optional

# NVIDIA NIM API Configuration
NVIDIA_NIM_API_KEY = os.environ.get("NVIDIA_NIM_API_KEY", "")
NVIDIA_NIM_BASE_URL = os.environ.get("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")

# Model configuration
EMBED_MODEL = "nvidia/llama-nemotron-embed-1b-v2"
EMBED_BATCH_SIZE = 24  # Maximum batch size for the model
EMBED_DIMENSION = 3072  # Embedding dimension for llama-nemotron-embed-1b-v2


def get_nvidia_headers() -> Dict[str, str]:
    """Get headers for NVIDIA NIM API requests."""
    api_key = NVIDIA_NIM_API_KEY or os.environ.get("NVIDIA_NIM_API_KEY", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def embed_texts(texts: List[str], model: str = EMBED_MODEL) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using NVIDIA NIM API.
    
    Args:
        texts: List of text strings to embed
        model: Model identifier (default: nvidia/llama-nemotron-embed-1b-v2)
    
    Returns:
        List of embedding vectors (each is a list of floats)
    """
    if not texts:
        return []
    
    if not NVIDIA_NIM_API_KEY:
        print("[Embedding] Warning: NVIDIA_NIM_API_KEY not set, returning empty embeddings")
        return [[] for _ in texts]
    
    headers = get_nvidia_headers()
    all_embeddings = []
    
    # Process in batches
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i:i + EMBED_BATCH_SIZE]
        
        payload = {
            "input": batch,
            "model": model,
            "encoding_format": "float"
        }
        
        try:
            response = requests.post(
                f"{NVIDIA_NIM_BASE_URL}/embeddings",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract embeddings from response
            batch_embeddings = [item["embedding"] for item in data["data"]]
            all_embeddings.extend(batch_embeddings)
            
        except Exception as e:
            print(f"[Embedding] Error embedding batch {i//EMBED_BATCH_SIZE + 1}: {e}")
            # Return empty embeddings for failed batch
            all_embeddings.extend([[] for _ in batch])
        
        # Small delay to avoid rate limiting
        if i + EMBED_BATCH_SIZE < len(texts):
            time.sleep(0.1)
    
    return all_embeddings


def embed_text(text: str, model: str = EMBED_MODEL) -> List[float]:
    """
    Generate embedding for a single text.
    
    Args:
        text: Text string to embed
        model: Model identifier
    
    Returns:
        Embedding vector as list of floats
    """
    embeddings = embed_texts([text], model=model)
    return embeddings[0] if embeddings else []


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Args:
        a: First vector
        b: Second vector
    
    Returns:
        Cosine similarity score (0 to 1)
    """
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
    Search for most similar chunks to a query using embeddings.
    
    Args:
        query: Search query
        chunks: List of chunk dicts with 'embedding' and 'text' keys
        top_k: Number of top results to return
    
    Returns:
        List of top-k most similar chunks with similarity scores
    """
    if not chunks:
        return []
    
    # Generate query embedding
    query_embedding = embed_text(query)
    if not query_embedding:
        return []
    
    # Calculate similarities
    scored = []
    for chunk in chunks:
        chunk_embedding = chunk.get("embedding", [])
        if chunk_embedding:
            similarity = cosine_similarity(query_embedding, chunk_embedding)
            scored.append({
                **chunk,
                "similarity": similarity
            })
    
    # Sort by similarity and return top-k
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Text to split
        chunk_size: Size of each chunk
        overlap: Overlap between chunks
    
    Returns:
        List of text chunks
    """
    if not text:
        return []
    
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap
    
    return chunks


def process_document_for_embedding(text: str, source_name: str = "", source_type: str = "text") -> List[Dict]:
    """
    Process a document into chunks with embeddings.
    
    Args:
        text: Document text
        source_name: Name of the source (e.g., filename, URL)
        source_type: Type of source (pdf, docx, website, etc.)
    
    Returns:
        List of chunk dicts with text, embedding, and metadata
    """
    # Split into chunks
    chunks = chunk_text(text)
    
    # Generate embeddings for all chunks
    embeddings = embed_texts(chunks)
    
    # Build result
    result = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        if embedding:  # Only include if embedding was successful
            result.append({
                "id": f"{source_name}_chunk_{i}" if source_name else f"chunk_{i}",
                "text": chunk,
                "embedding": embedding,
                "source": source_name,
                "source_type": source_type,
                "chunk_index": i,
                "created_at": time.time()
            })
    
    return result