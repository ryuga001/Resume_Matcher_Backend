from embeddings.service.embedding_service import EmbeddingService
from embeddings.service.chunking_service import ChunkingService
from embeddings.repositories.embedding_repository import EmbeddingRepository


class IndexingService:
    """Chunks resume text, embeds each chunk, and persists to pgvector."""

    def __init__(self) -> None:
        self._embedder   = EmbeddingService()
        self._chunker    = ChunkingService()
        self._repository = EmbeddingRepository()

    def index_resume(self, resume_id: str, resume_text: str) -> int:
        chunks = self._chunker.chunk_text(resume_text)
        docs = [
            {
                "resumeId":   resume_id,
                "chunkIndex": i,
                "text":       chunk,
                "embedding":  self._embedder.create_embedding(chunk),
            }
            for i, chunk in enumerate(chunks)
        ]
        self._repository.delete_by_resume(resume_id)
        self._repository.save_many(docs)
        return len(docs)
