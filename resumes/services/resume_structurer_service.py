from __future__ import annotations

import json
import uuid
from typing import Any

from common.ai.llm_service import LLMService


_STRUCTURE_PROMPT = """
You are a precise resume parser. Extract the following structure from the resume text below.
Return ONLY valid JSON matching exactly this schema — no markdown, no extra keys.

{{
  "contact": {{
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedin": "",
    "github": ""
  }},
  "summary": "",
  "experience": [
    {{
      "id": "<uuid>",
      "company": "",
      "title": "",
      "startDate": "",
      "endDate": "",
      "bullets": []
    }}
  ],
  "education": [
    {{
      "id": "<uuid>",
      "institution": "",
      "degree": "",
      "field": "",
      "graduationDate": "",
      "gpa": ""
    }}
  ],
  "skills": [],
  "projects": [
    {{
      "id": "<uuid>",
      "name": "",
      "description": "",
      "technologies": [],
      "url": ""
    }}
  ],
  "certifications": []
}}

Rules:
- Every experience/education/project entry MUST include a unique "id" field (generate a short UUID).
- Leave fields empty string or empty array when not found — never omit them.
- Preserve all factual details exactly as stated in the resume.
- skills must be a flat array of strings.
- certifications must be a flat array of strings.

Resume text:
{resume_text}
""".strip()


_BUILD_PROMPT = """
You are a resume optimization expert. Rewrite the provided structured resume to address the ATS recommendations below.

Rules:
- Keep ALL factual information accurate — do not invent experience, companies, or dates.
- Rephrase bullet points to be action-oriented and quantified where possible.
- Strengthen the summary to highlight the most relevant experience for the job.
- Add missing skills ONLY if they genuinely appear in the candidate's background.
- Return ONLY valid JSON with the same schema as the input — no markdown, no extra keys.
- Preserve all id fields exactly as-is.

Original resume (JSON):
{structured_json}

ATS Recommendations:
{recommendations}

Missing skills to address (incorporate if genuinely present in background):
{missing_skills}

Job description context:
{job_description}
""".strip()


class ResumeStructurerService:
    """Uses Gemini to convert raw resume text into structured JSON and to apply ATS recommendations."""

    def __init__(self) -> None:
        self._llm = LLMService()

    def structure(self, resume_text: str) -> dict[str, Any]:
        """Parse raw resume text into a structured dict."""
        prompt = _STRUCTURE_PROMPT.format(resume_text=resume_text)
        raw = self._llm.generate(prompt)
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
        return self._ensure_ids(data)

    def build(
        self,
        structured: dict[str, Any],
        recommendations: list[str],
        missing_skills: list[str],
        job_description: str,
    ) -> dict[str, Any]:
        """Apply ATS recommendations to an already-structured resume via Gemini."""
        prompt = _BUILD_PROMPT.format(
            structured_json=json.dumps(structured, indent=2),
            recommendations="\n".join(f"- {r}" for r in recommendations),
            missing_skills=", ".join(missing_skills) or "none",
            job_description=job_description or "not provided",
        )
        raw = self._llm.generate(prompt)
        try:
            data = json.loads(raw)
        except Exception:
            data = structured
        return self._ensure_ids(data)

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _ensure_ids(data: dict) -> dict:
        """Guarantee every list entry has a unique id (Gemini sometimes forgets)."""
        for section in ("experience", "education", "projects"):
            for entry in data.get(section) or []:
                if not entry.get("id"):
                    entry["id"] = str(uuid.uuid4())[:8]
        return data
