from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ResumeEnhancer(ABC):
    """
    Decorator base — concrete enhancers wrap each other.

    Usage:
        enhanced = SummaryEnhancer(KeywordEnhancer(SkillsEnhancer())).enhance(data, ctx)
    """

    def __init__(self, wrapped: "ResumeEnhancer | None" = None) -> None:
        self._wrapped = wrapped

    def enhance(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if self._wrapped:
            data = self._wrapped.enhance(data, context)
        return self._apply(data, context)

    @abstractmethod
    def _apply(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        ...
