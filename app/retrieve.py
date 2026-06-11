from __future__ import annotations

import os
import sys

from app.embed import embed_texts
from app.store import QdrantStore, SearchHit


def retrieve(question: str, top_k: int | None = None) -> list[SearchHit]:
    """Embed a user question and retrieve the closest corpus chunks."""
    effective_top_k = top_k or int(os.environ.get("TOP_K", "5"))
    vector = embed_texts([question])[0]

    store = QdrantStore()
    store.ensure_collection()
    return store.search(vector, top_k=effective_top_k)


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "mesures de securite donnees personnelles"
    hits = retrieve(question)

    for hit in hits:
        source = hit.metadata.get("source")
        chunk_index = hit.metadata.get("chunk_index")
        print(f"[{hit.score:.3f}] {source}#{chunk_index} :: {hit.text[:220]}...")