"""Unit tests — ResumeBuilderService orchestrator (all dependencies mocked)."""

import os
import unittest
from unittest.mock import MagicMock, patch, mock_open


STRUCTURED = {
    "contact": {"name": "Bob Builder", "email": "bob@example.com", "phone": "", "location": "", "linkedin": "", "github": ""},
    "summary": "Backend engineer.",
    "experience": [],
    "education": [],
    "skills": ["Python"],
    "projects": [],
    "certifications": [],
}

ENHANCED = {**STRUCTURED, "summary": "Enhanced backend engineer."}


class TestResumeBuilderService(unittest.TestCase):

    def _make_service(self, *, structurer=None, formatter_bytes=b"%PDF-fake", s3_key="resumes/customized/bob_abc123.pdf"):
        with (
            patch("resumes.services.resume_builder_service.ResumeStructurerService") as MockStructurer,
            patch("resumes.services.resume_builder_service.ResumeFormatterFactory") as MockFactory,
            patch("resumes.services.resume_builder_service.S3Service") as MockS3,
        ):
            MockStructurer.return_value.structure.return_value = STRUCTURED
            MockStructurer.return_value.build.return_value = ENHANCED
            mock_fmt = MagicMock()
            mock_fmt.format.return_value = formatter_bytes
            mock_fmt.content_type = "application/pdf"
            mock_fmt.extension = "pdf"
            MockFactory.create.return_value = mock_fmt
            MockS3.return_value.upload_file.return_value = None

            from resumes.services.resume_builder_service import ResumeBuilderService
            svc = ResumeBuilderService()
            svc._structurer = MockStructurer.return_value
            svc._s3 = MockS3.return_value
            svc._mock_factory = MockFactory
            svc._mock_fmt = mock_fmt

        return svc

    # ── structure() ───────────────────────────────────────────────────────────

    def test_structure_delegates_to_structurer(self):
        svc = self._make_service()
        result = svc.structure("raw text")
        svc._structurer.structure.assert_called_once_with("raw text")
        self.assertEqual(result, STRUCTURED)

    # ── build_enhanced() ──────────────────────────────────────────────────────

    def test_build_enhanced_calls_structurer_build(self):
        svc = self._make_service()
        ctx = {"recommendations": ["Add Docker."], "missingSkills": ["Docker"], "jobDescription": "Docker needed."}
        svc.build_enhanced(STRUCTURED, ctx)
        svc._structurer.build.assert_called_once_with(
            structured=STRUCTURED,
            recommendations=["Add Docker."],
            missing_skills=["Docker"],
            job_description="Docker needed.",
        )

    def test_build_enhanced_applies_decorator_chain(self):
        svc = self._make_service()
        ctx = {"recommendations": ["Quantify impact."], "missingSkills": ["Kubernetes"], "jobDescription": "k8s needed"}
        result = svc.build_enhanced(STRUCTURED, ctx)
        # SummaryEnhancer should have prepended the recommendation
        self.assertIn("Quantify impact.", result["summary"])

    def test_build_enhanced_empty_context_returns_enhanced_without_error(self):
        svc = self._make_service()
        result = svc.build_enhanced(STRUCTURED, {})
        self.assertIsInstance(result, dict)

    def test_build_enhanced_missing_skills_added_to_skills(self):
        svc = self._make_service()
        ctx = {"missingSkills": ["Go"], "recommendations": [], "jobDescription": ""}
        result = svc.build_enhanced(STRUCTURED, ctx)
        self.assertIn("Go", result["skills"])

    # ── render_and_upload() ───────────────────────────────────────────────────

    def test_render_and_upload_calls_formatter(self):
        svc = self._make_service()
        with (
            patch("resumes.services.resume_builder_service.ResumeFormatterFactory") as MockFactory,
            patch("resumes.services.resume_builder_service.os.unlink"),
            patch("builtins.open", mock_open()),
            patch("tempfile.NamedTemporaryFile") as MockTmp,
        ):
            mock_fmt = MagicMock()
            mock_fmt.format.return_value = b"%PDF-test"
            mock_fmt.content_type = "application/pdf"
            mock_fmt.extension = "pdf"
            MockFactory.create.return_value = mock_fmt
            tmp = MagicMock()
            tmp.name = "/tmp/fake_resume.pdf"
            tmp.__enter__ = lambda s: s
            tmp.__exit__ = MagicMock(return_value=False)
            MockTmp.return_value = tmp

            svc.render_and_upload(STRUCTURED, folder="resumes/customized")
            mock_fmt.format.assert_called_once_with(STRUCTURED)

    def test_render_and_upload_key_includes_folder(self):
        svc = self._make_service()
        with (
            patch("resumes.services.resume_builder_service.ResumeFormatterFactory") as MockFactory,
            patch("resumes.services.resume_builder_service.os.unlink"),
            patch("resumes.services.resume_builder_service.ResumeBuilderService._write_temp", return_value="/tmp/fake.pdf"),
        ):
            mock_fmt = MagicMock()
            mock_fmt.format.return_value = b"%PDF-test"
            mock_fmt.content_type = "application/pdf"
            mock_fmt.extension = "pdf"
            MockFactory.create.return_value = mock_fmt

            key = svc.render_and_upload(STRUCTURED, folder="resumes/export")
            self.assertTrue(key.startswith("resumes/export/"))
            self.assertTrue(key.endswith(".pdf"))

    def test_render_and_upload_deletes_temp_file_even_on_s3_error(self):
        svc = self._make_service()
        svc._s3.upload_file.side_effect = RuntimeError("S3 down")

        with (
            patch("resumes.services.resume_builder_service.ResumeFormatterFactory") as MockFactory,
            patch("resumes.services.resume_builder_service.ResumeBuilderService._write_temp", return_value="/tmp/fake.pdf"),
            patch("resumes.services.resume_builder_service.os.unlink") as mock_unlink,
        ):
            mock_fmt = MagicMock()
            mock_fmt.format.return_value = b"%PDF"
            mock_fmt.content_type = "application/pdf"
            mock_fmt.extension = "pdf"
            MockFactory.create.return_value = mock_fmt

            with self.assertRaises(RuntimeError):
                svc.render_and_upload(STRUCTURED, folder="resumes/export")
            mock_unlink.assert_called_once_with("/tmp/fake.pdf")

    # ── _write_temp() ─────────────────────────────────────────────────────────

    def test_write_temp_creates_file_with_correct_extension(self):
        from resumes.services.resume_builder_service import ResumeBuilderService
        path = ResumeBuilderService._write_temp(b"fake pdf bytes", "pdf")
        try:
            self.assertTrue(path.endswith(".pdf"))
            self.assertTrue(os.path.exists(path))
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"fake pdf bytes")
        finally:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == "__main__":
    unittest.main()
