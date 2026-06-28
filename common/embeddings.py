import os
import json
import numpy as np
import google.generativeai as genai

_EMBED_MODEL = "models/text-embedding-004"
_CHUNK_TOKENS = 800    # ~600 words per chunk
_OVERLAP_TOKENS = 80   # ~60 words overlap


class EmbeddingService:
    """Chunk → embed → store in MongoDB, plus cosine-similarity search."""

    def __init__(self):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))

    # ── Embed ─────────────────────────────────────────────────────────────────

    def embed(self, text: str) -> list[float]:
        result = genai.embed_content(
            model=_EMBED_MODEL,
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
        )
        return result["embedding"]

    def embed_query(self, text: str) -> list[float]:
        result = genai.embed_content(
            model=_EMBED_MODEL,
            content=text,
            task_type="RETRIEVAL_QUERY",
        )
        return result["embedding"]

    # ── Chunk + index ─────────────────────────────────────────────────────────

    def index_content(self, db, course_id: str, subtopic_order: int, content: dict) -> int:
        """
        Chunk a subtopic content dict, embed each chunk, and upsert into
        the `course_chunks` collection.  Returns the number of chunks stored.
        """
        chunks = self._content_to_chunks(content)
        collection = db["course_chunks"]

        # Remove old chunks for this subtopic before re-indexing
        collection.delete_many({"courseId": course_id, "subtopicOrder": subtopic_order})

        docs = []
        for i, chunk_text in enumerate(chunks):
            embedding = self.embed(chunk_text)
            docs.append({
                "courseId":      course_id,
                "subtopicOrder": subtopic_order,
                "chunkIndex":    i,
                "text":          chunk_text,
                "embedding":     embedding,
            })

        if docs:
            collection.insert_many(docs)

        return len(docs)

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, db, course_id: str, query: str, top_k: int = 5) -> list[dict]:
        """
        Cosine-similarity search over course_chunks for a given course.
        Returns top_k chunks sorted by descending similarity.
        """
        q_vec = np.array(self.embed_query(query), dtype=np.float32)
        collection = db["course_chunks"]
        docs = list(collection.find({"courseId": course_id}, {"embedding": 1, "text": 1, "subtopicOrder": 1, "chunkIndex": 1}))

        if not docs:
            return []

        scores = []
        for doc in docs:
            d_vec = np.array(doc["embedding"], dtype=np.float32)
            sim = float(np.dot(q_vec, d_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(d_vec) + 1e-9))
            scores.append((sim, doc))

        scores.sort(key=lambda x: x[0], reverse=True)
        return [
            {"text": d["text"], "subtopicOrder": d["subtopicOrder"], "score": s}
            for s, d in scores[:top_k]
        ]

    # ── Private ───────────────────────────────────────────────────────────────

    def _content_to_chunks(self, content: dict) -> list[str]:
        """Convert the structured content JSON into overlapping text chunks."""
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
                f"{ex.get('explanation', '')}\n```{ex.get('language','')}\n{ex.get('code','')}\n```"
            )

        if key_points := content.get("key_points", []):
            sections.append("Key Points\n" + "\n".join(f"- {k}" for k in key_points))

        # Naive word-level chunking with overlap across sections
        words: list[str] = []
        for s in sections:
            words.extend(s.split())

        chunks: list[str] = []
        step = _CHUNK_TOKENS - _OVERLAP_TOKENS
        i = 0
        while i < len(words):
            chunk = " ".join(words[i : i + _CHUNK_TOKENS])
            chunks.append(chunk)
            i += step

        return chunks or [" ".join(words)]
