from __future__ import annotations

import copy
from typing import Any

from resumes.services.enhancers.base_enhancer import ResumeEnhancer


class SummaryEnhancer(ResumeEnhancer):
    """
    Decorator — prepends a one-line ATS note to the summary when there are recommendations.

    Context keys used: "recommendations" (list[str])
    """

    def _apply(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        recs: list[str] = context.get("recommendations") or []
        if not recs:
            return data

        data = copy.deepcopy(data)
        existing_summary = (data.get("summary") or "").strip()

        first_rec = recs[0].rstrip(".")
        note = f"{first_rec}."
        data["summary"] = f"{note} {existing_summary}".strip() if existing_summary else note

        return data
