import json
import os
import uuid

from google import genai
from google.genai import types

from common.s3 import S3Service

_CHAT_SYSTEM = """You are an AI study assistant for the course "{topic}", subtopic "{subtopic_title}".

Answer the student's question using ONLY the context below. Be concise, clear, and educational.
If the answer is not covered in the context, say so honestly rather than guessing.

Context:
{context}
"""

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

_CONTENT_PROMPT = """You are an expert technical educator. Generate comprehensive, high-quality learning content for the following subtopic.

Course: "{topic}"
Subtopic: "{subtopic_title}" (Difficulty: {difficulty})

Reference material from the source document:
{reference_content}

Output ONLY a valid JSON object with this exact structure (no markdown fences, no extra text):
{{
  "overview": "<2-3 sentence introduction to the subtopic and why it matters>",
  "theory": [
    {{
      "heading": "<section heading>",
      "body": "<detailed explanation — min 3 paragraphs. Use clear, precise language. Cover concepts deeply.>"
    }}
  ],
  "diagrams": [
    {{
      "title": "<diagram title>",
      "description": "<one sentence explaining what the diagram shows>",
      "mermaid": "<valid Mermaid.js diagram code — flowchart, sequence, class, or ER. MUST be syntactically correct.>"
    }}
  ],
  "code_examples": [
    {{
      "title": "<example title>",
      "language": "<programming language>",
      "code": "<complete, runnable code snippet with comments>",
      "explanation": "<what the code does and key points to understand>"
    }}
  ],
  "key_points": ["<concise takeaway>"],
  "quiz": [
    {{
      "question": "<clear, specific question testing understanding>",
      "options": ["<option A>", "<option B>", "<option C>", "<option D>"],
      "correct": 0,
      "explanation": "<why this answer is correct and others are not>"
    }}
  ]
}}

Rules:
- theory: 3–5 sections, each with 3+ paragraphs of depth
- diagrams: 1–3 diagrams. STRICT Mermaid syntax rules — node labels must contain plain text ONLY: no parentheses (), no brackets [], no colons :, no angle brackets <>, no quotes, no special characters. Use flowchart TD for processes, sequenceDiagram for interactions. Example safe node: A --> B[Simple Label] NOT A --> B[Method: foo(x)]
- code_examples: 1–4 complete, runnable examples with inline comments
- key_points: 4–8 actionable takeaways
- quiz: exactly 5 multiple-choice questions, varying difficulty, correct index is 0-based
- All content must be accurate, educational, and professional
- Mermaid syntax must be valid — test mentally before generating
"""


class GeminiService:
    def __init__(self):
        self._client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
        self._model  = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self._s3     = S3Service()

    def generate_subtopics(self, source_key: str, topic: str) -> list[dict]:
        """
        Stream the S3 source file, extract text without loading the full file
        into memory, feed it to Gemini, and return a parsed subtopics list.

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
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            raw = response.text.strip()
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

    def generate_subtopic_content(
        self,
        source_key: str,
        topic: str,
        subtopic_title: str,
        difficulty: str,
    ) -> tuple[dict, str]:
        """
        Generate full structured content for a single subtopic.

        Returns:
            (content_dict, s3_key) where content_dict is the parsed JSON and
            s3_key is the key under which the raw JSON was uploaded to S3.

        Raises:
            ValueError  — unsupported file type or empty content.
            RuntimeError — Gemini call failed or bad JSON.
        """
        ext = source_key.rsplit(".", 1)[-1].lower() if "." in source_key else ""

        with self._s3.stream_to_temp(source_key) as tmp_path:
            reference_content = self._extract_text(tmp_path, ext)

        if not reference_content.strip():
            raise ValueError("Could not extract text from the source file.")

        reference_content = reference_content[:_MAX_CONTENT_CHARS]
        prompt = _CONTENT_PROMPT.format(
            topic=topic,
            subtopic_title=subtopic_title,
            difficulty=difficulty,
            reference_content=reference_content,
        )

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=8192),
            )
            raw = response.text.strip()
        except Exception as exc:
            raise RuntimeError(f"Gemini call failed: {exc}") from exc

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            content = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Gemini returned truncated/invalid JSON: {exc}") from exc

        if not isinstance(content, dict):
            raise RuntimeError("Gemini response was not a JSON object.")

        # Upload to S3 as .json
        s3_key = f"courses/content/{uuid.uuid4()}.json"
        self._s3.put_text(s3_key, json.dumps(content, ensure_ascii=False), "application/json")

        return content, s3_key

    def chat_subtopic(
        self,
        topic: str,
        subtopic_title: str,
        context: str,
        history: list[dict],
        message: str,
    ) -> str:
        """
        Multi-turn RAG chat for a subtopic.
        `history` is a list of {role: "user"|"model", content: str} dicts.
        """
        system_prompt = _CHAT_SYSTEM.format(
            topic=topic,
            subtopic_title=subtopic_title,
            context=context or "No context available.",
        )

        gemini_history = [
            types.Content(
                role=h["role"],
                parts=[types.Part(text=h["content"])],
            )
            for h in history
            if h.get("role") in ("user", "model") and h.get("content")
        ]

        chat = self._client.chats.create(
            model=self._model,
            history=gemini_history,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=1024,
            ),
        )
        try:
            response = chat.send_message(message)
            return response.text.strip()
        except Exception as exc:
            raise RuntimeError(f"Gemini chat failed: {exc}") from exc

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
