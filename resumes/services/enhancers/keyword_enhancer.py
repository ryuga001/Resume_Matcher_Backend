from __future__ import annotations

import copy
from typing import Any

from resumes.services.enhancers.base_enhancer import ResumeEnhancer


class KeywordEnhancer(ResumeEnhancer):
    """
    Decorator — appends a concise keyword-rich bullet to the most recent experience entry
    when the job description mentions technologies not yet present anywhere in the resume text.

    Context keys used: "jobDescription" (str), "missingSkills" (list[str])
    """

    def _apply(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        missing: list[str] = context.get("missingSkills") or []
        jd: str = context.get("jobDescription") or ""
        if not missing or not jd:
            return data

        resume_text = self._flatten(data).lower()
        keywords = [kw for kw in missing if kw.lower() not in resume_text]
        if not keywords:
            return data

        data = copy.deepcopy(data)
        experience: list[dict] = data.get("experience") or []
        if experience:
            bullet = f"Demonstrated working knowledge of {', '.join(keywords[:5])} in a collaborative engineering environment."
            experience[0].setdefault("bullets", []).append(bullet)

        return data

    @staticmethod
    def _flatten(data: dict) -> str:
        """Concatenate all string values for a quick full-text search."""
        parts: list[str] = []
        for val in data.values():
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        parts.extend(str(v) for v in item.values())
        return " ".join(parts)
