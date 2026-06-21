from embeddings.service.embedding_service import EmbeddingService
from embeddings.service.chunking_service import ChunkingService
from embeddings.repositories.embedding_repository import EmbeddingRepository

class IndexingService:

    @staticmethod
    def index_resume(resume_id,resume_text):
        chunks = ChunkingService().chunk_text(resume_text)
        
        docs = []

        for index, chunk in enumerate(chunks):

            docs.append({
                "resumeId": resume_id,
                "chunkIndex": index,
                "text": chunk,
                "embedding": EmbeddingService().create_embedding(chunk)
            })
        
        EmbeddingRepository().save_many(docs)
