from __future__ import annotations

import numpy as np
from pgvector.django import CosineDistance

from embeddings.models import ResumeChunk


class EmbeddingRepository:
    """pgvector-backed repository for resume chunk embeddings."""

    def save_many(self, documents: list[dict]) -> None:
        chunks = [
            ResumeChunk(
                resume_id=int(doc["resumeId"]),
                chunk_index=doc["chunkIndex"],
                text=doc["text"],
                embedding=doc["embedding"],
            )
            for doc in documents
        ]
        ResumeChunk.objects.bulk_create(chunks)

    def find_by_resume_id(self, resume_id: str) -> list[dict]:
        rows = ResumeChunk.objects.filter(resume_id=int(resume_id))
        return [
            {
                "resumeId":   resume_id,
                "chunkIndex": r.chunk_index,
                "text":       r.text,
                "embedding":  list(r.embedding),
            }
            for r in rows
        ]

    def vector_search(self, resume_id: str, query_embedding: list[float], limit: int = 5) -> list[dict]:
        rows = (
            ResumeChunk.objects
            .filter(resume_id=int(resume_id))
            .annotate(distance=CosineDistance("embedding", query_embedding))
            .order_by("distance")[:limit]
        )
        return [
            {"text": r.text, "score": float(1 - r.distance), "chunkIndex": r.chunk_index}
            for r in rows
        ]

    def delete_by_resume(self, resume_id: str) -> None:
        ResumeChunk.objects.filter(resume_id=int(resume_id)).delete()
