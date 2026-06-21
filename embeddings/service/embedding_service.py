from sentence_transformers import SentenceTransformer

class EmbeddingService:
    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

    @classmethod
    def create_embedding(cls, text: str):
        return cls.model.encode(text).tolist()
