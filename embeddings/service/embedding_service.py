from sentence_transformers import SentenceTransformer


class EmbeddingService:
    _model: SentenceTransformer | None = None

    @classmethod
    def _get_model(cls) -> SentenceTransformer:
        if cls._model is None:
            cls._model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
        return cls._model

    @classmethod
    def create_embedding(cls, text: str) -> list[float]:
        return cls._get_model().encode(text).tolist()
