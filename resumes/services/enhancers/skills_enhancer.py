from __future__ import annotations

import copy
from typing import Any

from resumes.services.enhancers.base_enhancer import ResumeEnhancer


class SkillsEnhancer(ResumeEnhancer):
    """
    Decorator — merges missing skills from the analysis context into the skills list.

    Context key used: "missingSkills" (list[str])
    """

    def _apply(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        missing: list[str] = context.get("missingSkills") or []
        if not missing:
            return data

        data = copy.deepcopy(data)
        existing = {s.lower() for s in (data.get("skills") or [])}
        for skill in missing:
            if skill.lower() not in existing:
                data.setdefault("skills", []).append(skill)
                existing.add(skill.lower())

        return data
