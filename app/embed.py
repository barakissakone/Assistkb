from __future__ import annotations

import os
from sentence_transformers import SentenceTransformer
from app.ingest import load_chunks
from app.store import QdrantStore

_model = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        name = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        _model = SentenceTransformer(name)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_model()
    return model.encode(texts, normalize_embeddings=True).tolist()


def index_corpus(batch_size: int = 64) -> None:
    chunks = load_chunks()
    store = QdrantStore()
    store.ensure_collection()
    total = len(chunks)
    for start in range(0, total, batch_size):
        batch = chunks[start:start + batch_size]
        vectors = embed_texts([c.text for c in batch])
        store.upsert((c.id, v, c.text, c.metadata) for c, v in zip(batch, vectors))
        print(f"[embed] {min(start + batch_size, total)}/{total} chunks indexes")
    print(f"[embed] Termine : {total} chunks dans Qdrant")


if __name__ == "__main__":
    index_corpus()
