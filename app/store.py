from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


@dataclass(frozen=True)
class SearchHit:
    """Result returned by the vector store."""

    text: str
    score: float
    metadata: dict


class QdrantStore:
    """Small adapter around Qdrant used by the RAG pipeline."""

    def __init__(self) -> None:
        self.url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.collection = os.environ.get("COLLECTION_NAME", "assistkb")
        self.dim = int(os.environ.get("EMBEDDING_DIM", "384"))
        self.client = QdrantClient(url=self.url)

    def ensure_collection(self) -> None:
        """Create the collection if it does not already exist."""
        collections = self.client.get_collections().collections
        existing_collections = {collection.name for collection in collections}

        if self.collection not in existing_collections:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
            )
            print(f"[store] collection creee: {self.collection}")

    def upsert(self, items: Iterable[tuple[str, list[float], str, dict]]) -> None:
        """Insert or update chunks in Qdrant."""
        points = [
            PointStruct(
                id=chunk_id,
                vector=vector,
                payload={"text": text, **metadata},
            )
            for chunk_id, vector, text, metadata in items
        ]

        if points:
            self.client.upsert(collection_name=self.collection, points=points)

    def search(self, vector: list[float], top_k: int = 5) -> list[SearchHit]:
        """Return the most similar chunks for a query vector."""
        hits = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=top_k,
            with_payload=True,
        )

        results: list[SearchHit] = []
        for hit in hits:
            payload = hit.payload or {}
            metadata = {key: value for key, value in payload.items() if key != "text"}
            results.append(
                SearchHit(
                    text=payload.get("text", ""),
                    score=float(hit.score),
                    metadata=metadata,
                )
            )
        return results