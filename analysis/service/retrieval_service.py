from embeddings.service.embedding_service import EmbeddingService
from embeddings.repositories.embedding_repository import EmbeddingRepository


class RetrievalService:
    """Retrieves the most relevant resume chunks for a given job description via pgvector."""

    def __init__(self) -> None:
        self._embedder   = EmbeddingService()
        self._repository = EmbeddingRepository()

    def retrieve(self, resume_id: str, job_description: str, top_k: int = 5) -> list[dict]:
        jd_embedding = self._embedder.create_embedding(job_description)
        return self._repository.vector_search(resume_id, jd_embedding, top_k)
