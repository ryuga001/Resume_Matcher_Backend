import numpy as np
from embeddings.service.embedding_service import EmbeddingService
from embeddings.repositories.embedding_repository import EmbeddingRepository


class RetrievalService:

    @staticmethod
    def _cosine(a, b):
        a, b = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / denom) if denom else 0.0

    @classmethod
    def _local(cls, resume_id: str, jd_embedding: list, top_k: int):
        chunks = EmbeddingRepository().find_by_resume_id(resume_id)
        scored = sorted(chunks, key=lambda c: cls._cosine(jd_embedding, c.get("embedding", [])), reverse=True)
        return scored[:top_k]

    @classmethod
    def retrieve(cls, resume_id: str, job_description: str, top_k: int = 5):
        jd_embedding = EmbeddingService().create_embedding(job_description)
        try:
            chunks = EmbeddingRepository().vector_search(resume_id, jd_embedding, top_k)
            if chunks:
                return chunks
        except Exception:
            pass
        return cls._local(resume_id, jd_embedding, top_k)
