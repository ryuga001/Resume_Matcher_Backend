import json
import os

import google.generativeai as genai

from common.s3 import S3Service

_SUBTOPIC_PROMPT = """You are a curriculum designer.

Analyse the course content below (topic: "{topic}") and return a comprehensive list of subtopics a learner must master.

Rules:
- Return ONLY a valid JSON array — no markdown fences, no explanation.
- Each element: {{"title": "<string>", "difficulty": "Beginner" | "Intermediate" | "Advanced", "order": <int starting at 1>}}
- 5–20 subtopics, ordered from foundational to advanced.

Course content:
{content}
"""

_MAX_CONTENT_CHARS = 60_000   # ~15k tokens — enough for most docs


class GeminiService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY", "")
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel("gemini-3.5-flash")
        self._s3    = S3Service()

    def generate_subtopics(self, source_key: str, topic: str) -> list[dict]:
        """
        Stream the S3 source file, extract text without loading the full file
        into memory, feed it to Gemini Flash, and return a parsed subtopics list.

        Raises:
            ValueError  — unsupported file type or empty content.
            RuntimeError — Gemini call failed or response is not valid JSON.
        """
        ext = source_key.rsplit(".", 1)[-1].lower() if "." in source_key else ""

        with self._s3.stream_to_temp(source_key) as tmp_path:
            content = self._extract_text(tmp_path, ext)

        if not content.strip():
            raise ValueError("Could not extract text from the source file.")

        content = content[:_MAX_CONTENT_CHARS]
        prompt  = _SUBTOPIC_PROMPT.format(topic=topic, content=content)

        try:
            response = self._model.generate_content(prompt)
            raw      = response.text.strip()
        except Exception as exc:
            raise RuntimeError(f"Gemini call failed: {exc}") from exc

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            subtopics = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Gemini returned invalid JSON: {exc}\n\nRaw:\n{raw}") from exc

        if not isinstance(subtopics, list):
            raise RuntimeError("Gemini response was not a JSON array.")

        return [
            {
                "title":      str(s.get("title", "")).strip(),
                "difficulty": s.get("difficulty", "Intermediate"),
                "order":      i + 1,
            }
            for i, s in enumerate(subtopics)
            if s.get("title")
        ]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_text(self, path: str, ext: str) -> str:
        if ext == "pdf":
            return self._extract_pdf(path)
        raise ValueError(f"Unsupported file type: .{ext}. Only PDF is supported for subtopic generation.")

    @staticmethod
    def _extract_pdf(path: str) -> str:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise RuntimeError("PyMuPDF is not installed. Run: uv pip install pymupdf")

        parts = []
        with fitz.open(path) as doc:
            for page in doc:
                parts.append(page.get_text())   # one page at a time — memory-efficient
        return "\n".join(parts)
