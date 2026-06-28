"""
Course-content embedding service using Gemini text-embedding-004 + pgvector.
"""
import os

from google import genai
from google.genai import types
from pgvector.django import CosineDistance

_EMBED_MODEL    = "models/text-embedding-004"
_CHUNK_TOKENS   = 800
_OVERLAP_TOKENS = 80


class EmbeddingService:
    """Chunk subtopic content → Gemini embed → store in pgvector CourseChunk table."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))

    # ── Public API ────────────────────────────────────────────────────────────

    def index_content(self, course_id: str, subtopic_order: int, content: dict) -> int:
        """Chunk, embed, and persist a subtopic's content. Returns chunk count."""
        from courses.models import CourseChunk  # import here to avoid circular at module load

        chunks = self._content_to_chunks(content)

        CourseChunk.objects.filter(
            course_id=int(course_id), subtopic_order=subtopic_order
        ).delete()

        objs = [
            CourseChunk(
                course_id=int(course_id),
                subtopic_order=subtopic_order,
                chunk_index=i,
                text=chunk_text,
                embedding=self.embed(chunk_text),
            )
            for i, chunk_text in enumerate(chunks)
        ]
        CourseChunk.objects.bulk_create(objs)
        return len(objs)

    def search(self, course_id: str, query: str, top_k: int = 5) -> list[dict]:
        """Cosine-similarity search over stored course chunks."""
        from courses.models import CourseChunk

        q_vec = self.embed_query(query)
        rows = (
            CourseChunk.objects
            .filter(course_id=int(course_id))
            .annotate(distance=CosineDistance("embedding", q_vec))
            .order_by("distance")[:top_k]
        )
        return [
            {"text": r.text, "subtopicOrder": r.subtopic_order, "score": float(1 - r.distance)}
            for r in rows
        ]

    # ── Embedding calls ───────────────────────────────────────────────────────

    def embed(self, text: str) -> list[float]:
        result = self._client.models.embed_content(
            model=_EMBED_MODEL,
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        return list(result.embeddings[0].values)

    def embed_query(self, text: str) -> list[float]:
        result = self._client.models.embed_content(
            model=_EMBED_MODEL,
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        return list(result.embeddings[0].values)

    # ── Chunking ──────────────────────────────────────────────────────────────

    def _content_to_chunks(self, content: dict) -> list[str]:
        sections: list[str] = []

        if overview := content.get("overview", ""):
            sections.append(f"Overview\n{overview}")
        for t in content.get("theory", []):
            sections.append(f"{t.get('heading', '')}\n{t.get('body', '')}")
        for d in content.get("diagrams", []):
            sections.append(f"Diagram: {d.get('title', '')}\n{d.get('description', '')}")
        for ex in content.get("code_examples", []):
            sections.append(
                f"Code Example: {ex.get('title', '')}\n"
                f"{ex.get('explanation', '')}\n```{ex.get('language', '')}\n{ex.get('code', '')}\n```"
            )
        if kp := content.get("key_points", []):
            sections.append("Key Points\n" + "\n".join(f"- {k}" for k in kp))

        words: list[str] = []
        for s in sections:
            words.extend(s.split())

        step = _CHUNK_TOKENS - _OVERLAP_TOKENS
        chunks, i = [], 0
        while i < len(words):
            chunks.append(" ".join(words[i: i + _CHUNK_TOKENS]))
            i += step

        return chunks or [" ".join(words)]
