from __future__ import annotations

import tempfile
import uuid
import os
from typing import Any

from common.s3 import S3Service
from resumes.services.resume_structurer_service import ResumeStructurerService
from resumes.services.formatters.factory import ResumeFormatterFactory
from resumes.services.enhancers.skills_enhancer import SkillsEnhancer
from resumes.services.enhancers.keyword_enhancer import KeywordEnhancer
from resumes.services.enhancers.summary_enhancer import SummaryEnhancer


class ResumeBuilderService:
    """
    Orchestrates the full resume-builder pipeline:
      1. Structure raw text with Gemini           (ResumeStructurerService)
      2. Enhance with decorator chain             (SkillsEnhancer → KeywordEnhancer → SummaryEnhancer)
      3. Format to bytes                          (ResumeFormatterFactory / Strategy)
      4. Upload to S3                             (S3Service)
    """

    def __init__(self) -> None:
        self._structurer = ResumeStructurerService()
        self._s3 = S3Service()

    # ── Public API ─────────────────────────────────────────────────────────────

    def structure(self, resume_text: str) -> dict[str, Any]:
        """Return cached or freshly parsed structured data."""
        return self._structurer.structure(resume_text)

    def build_enhanced(
        self,
        structured: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Apply recommendations via Gemini then run the decorator chain for
        deterministic post-processing.

        context keys: recommendations, missingSkills, jobDescription
        """
        enhanced = self._structurer.build(
            structured=structured,
            recommendations=context.get("recommendations") or [],
            missing_skills=context.get("missingSkills") or [],
            job_description=context.get("jobDescription") or "",
        )

        # Decorator chain: SummaryEnhancer wraps KeywordEnhancer wraps SkillsEnhancer
        chain = SummaryEnhancer(KeywordEnhancer(SkillsEnhancer()))
        return chain.enhance(enhanced, context)

    def render_and_upload(
        self,
        structured: dict[str, Any],
        folder: str,
        fmt: str = "pdf",
    ) -> str:
        """
        Render structured data → bytes, upload to S3, return the S3 key.

        folder examples: "resumes/customized", "resumes/export"
        """
        formatter = ResumeFormatterFactory.create(fmt)
        pdf_bytes = formatter.format(structured)

        name = (structured.get("contact") or {}).get("name", "resume").replace(" ", "_").lower()
        key = f"{folder.strip('/')}/{name}_{uuid.uuid4().hex[:8]}.{formatter.extension}"

        tmp_path = self._write_temp(pdf_bytes, formatter.extension)
        try:
            self._s3.upload_file(tmp_path, key, formatter.content_type)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return key

    # ── Internal ───────────────────────────────────────────────────────────────

    @staticmethod
    def _write_temp(data: bytes, ext: str) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as f:
            f.write(data)
            return f.name
