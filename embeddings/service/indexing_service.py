from embeddings.service.embedding_service import EmbeddingService
from embeddings.service.chunking_service import ChunkingService
from embeddings.repositories.embedding_repository import EmbeddingRepository


class IndexingService:
    @staticmethod
    def index_resume(resume_id: str, resume_text: str):
        chunks = ChunkingService().chunk_text(resume_text)
        docs = [
            {
                "resumeId": resume_id,
                "chunkIndex": i,
                "text": chunk,
                "embedding": EmbeddingService().create_embedding(chunk),
            }
            for i, chunk in enumerate(chunks)
        ]
        EmbeddingRepository().save_many(docs)
