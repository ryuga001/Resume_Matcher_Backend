from __future__ import annotations

from resumes.services.formatters.base_formatter import ResumeFormatter
from resumes.services.formatters.pdf_formatter import PDFResumeFormatter


class ResumeFormatterFactory:
    """Factory — maps format strings to concrete ResumeFormatter instances."""

    _registry: dict[str, type[ResumeFormatter]] = {
        "pdf": PDFResumeFormatter,
    }

    @classmethod
    def create(cls, fmt: str) -> ResumeFormatter:
        klass = cls._registry.get(fmt.lower())
        if klass is None:
            supported = ", ".join(cls._registry)
            raise ValueError(f"Unsupported format '{fmt}'. Supported: {supported}")
        return klass()
