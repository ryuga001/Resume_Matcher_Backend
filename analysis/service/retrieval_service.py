import numpy as np

from embeddings.service.embedding_service import EmbeddingService
from embeddings.repositories.embedding_repository import EmbeddingRepository

class RetrievalService:

    @staticmethod
    def cosine_similarity(a,b):

        a = np.array(a)
        b = np.array(b)

        return np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b))
    
    @classmethod
    def retrieve_local_cosine(cls, resume_id, job_description, top_k=5):
        """
        Returns top-k most relevant resume chunks for the given job description
        """

        jd_embeddings = EmbeddingService().create_embedding(job_description)

        chunks = EmbeddingRepository().find_by_resume_id(resume_id)

        if not chunks:
            return []
        
        scored_chunks = []

        for chunk in chunks:
            chunk_embedding = chunk.get("embedding",[])
            score = cls.cosine_similarity(jd_embeddings, chunk_embedding)
            scored_chunks.append({
                "chunkIndex": chunk.get("chunkIndex"),
                "text": chunk.get("text"),
                "score": score
            })
        
        scored_chunks.sort(key=lambda x:x["score"],reverse=True)

        return scored_chunks[:top_k]


    @classmethod
    def retrieve(cls, resume_id: str, job_description: str, top_k: int = 5):
        jd_embeddings = EmbeddingService().create_embedding(job_description)
        chunks = EmbeddingRepository().vector_search(resume_id, query_embedding=jd_embeddings, limit=top_k)
        return chunks
        