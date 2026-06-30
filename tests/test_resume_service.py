"""Unit tests — ResumeService.process_resume (all I/O mocked)."""

import unittest
from unittest.mock import MagicMock, patch, call
from io import BytesIO


def _uploaded_file(name="resume.pdf", content=b"PDF content"):
    """Minimal mock of Django's InMemoryUploadedFile."""
    f = MagicMock()
    f.name = name
    f.chunks.return_value = iter([content])
    return f


class TestResumeServiceProcessResume(unittest.TestCase):

    def test_returns_resume_id_as_string(self):
        with (
            patch("resumes.services.resume_service.ResumeParserService") as MockParser,
            patch("resumes.services.resume_service.SkillExtrationService") as MockSkills,
            patch("resumes.services.resume_service.S3Service")            as MockS3,
            patch("resumes.services.resume_service.ResumeRepository")     as MockRepo,
            patch("resumes.services.resume_service.IndexingService"),
            patch("resumes.services.resume_service.threading"),
        ):
            MockParser.extract_text_from_pdf.return_value = "Python developer"
            MockSkills.extract.return_value = ["Python"]
            MockS3.return_value.upload_file.return_value = None
            MockRepo.return_value.save_resume.return_value = "42"

            from resumes.services.resume_service import ResumeService
            svc = ResumeService()
            result = svc.process_resume(_uploaded_file(), "7")
            self.assertEqual(result, "42")

    def test_calls_parser_with_temp_file_path(self):
        with (
            patch("resumes.services.resume_service.ResumeParserService") as MockParser,
            patch("resumes.services.resume_service.SkillExtrationService") as MockSkills,
            patch("resumes.services.resume_service.S3Service")            as MockS3,
            patch("resumes.services.resume_service.ResumeRepository")     as MockRepo,
            patch("resumes.services.resume_service.IndexingService"),
            patch("resumes.services.resume_service.threading"),
        ):
            MockParser.extract_text_from_pdf.return_value = "text"
            MockSkills.extract.return_value = []
            MockS3.return_value.upload_file.return_value = None
            MockRepo.return_value.save_resume.return_value = "1"

            from resumes.services.resume_service import ResumeService
            svc = ResumeService()
            svc.process_resume(_uploaded_file("cv.pdf"), "1")
            MockParser.extract_text_from_pdf.assert_called_once()
            # arg should be a path string ending in .pdf
            path_arg = MockParser.extract_text_from_pdf.call_args[0][0]
            self.assertTrue(path_arg.endswith(".pdf"))

    def test_calls_skill_extraction_with_parsed_text(self):
        with (
            patch("resumes.services.resume_service.ResumeParserService") as MockParser,
            patch("resumes.services.resume_service.SkillExtrationService") as MockSkills,
            patch("resumes.services.resume_service.S3Service")            as MockS3,
            patch("resumes.services.resume_service.ResumeRepository")     as MockRepo,
            patch("resumes.services.resume_service.IndexingService"),
            patch("resumes.services.resume_service.threading"),
        ):
            MockParser.extract_text_from_pdf.return_value = "Expert in Python and Docker"
            MockSkills.extract.return_value = ["Python", "Docker"]
            MockS3.return_value.upload_file.return_value = None
            MockRepo.return_value.save_resume.return_value = "3"

            from resumes.services.resume_service import ResumeService
            svc = ResumeService()
            svc.process_resume(_uploaded_file(), "5")
            MockSkills.extract.assert_called_once_with("Expert in Python and Docker")

    def test_uploads_to_s3_with_resume_key(self):
        with (
            patch("resumes.services.resume_service.ResumeParserService") as MockParser,
            patch("resumes.services.resume_service.SkillExtrationService") as MockSkills,
            patch("resumes.services.resume_service.S3Service")            as MockS3,
            patch("resumes.services.resume_service.ResumeRepository")     as MockRepo,
            patch("resumes.services.resume_service.IndexingService"),
            patch("resumes.services.resume_service.threading"),
        ):
            MockParser.extract_text_from_pdf.return_value = "text"
            MockSkills.extract.return_value = ["Python"]
            mock_s3_instance = MockS3.return_value
            MockRepo.return_value.save_resume.return_value = "1"

            from resumes.services.resume_service import ResumeService
            svc = ResumeService()
            svc.process_resume(_uploaded_file("cv.pdf"), "1")
            mock_s3_instance.upload_file.assert_called_once()
            key_arg = mock_s3_instance.upload_file.call_args[0][1]
            self.assertTrue(key_arg.startswith("resumes/"))
            self.assertTrue(key_arg.endswith(".pdf"))

    def test_saves_resume_to_repository_with_user_id(self):
        with (
            patch("resumes.services.resume_service.ResumeParserService") as MockParser,
            patch("resumes.services.resume_service.SkillExtrationService") as MockSkills,
            patch("resumes.services.resume_service.S3Service")            as MockS3,
            patch("resumes.services.resume_service.ResumeRepository")     as MockRepo,
            patch("resumes.services.resume_service.IndexingService"),
            patch("resumes.services.resume_service.threading"),
        ):
            MockParser.extract_text_from_pdf.return_value = "content"
            MockSkills.extract.return_value = ["Go"]
            MockS3.return_value.upload_file.return_value = None
            MockRepo.return_value.save_resume.return_value = "7"

            from resumes.services.resume_service import ResumeService
            svc = ResumeService()
            svc.process_resume(_uploaded_file("cv.pdf"), "user_99")
            save_call_kwargs = MockRepo.return_value.save_resume.call_args[0][0]
            self.assertEqual(save_call_kwargs["userId"], "user_99")
            self.assertEqual(save_call_kwargs["fileName"], "cv.pdf")

    def test_spawns_background_thread_for_indexing(self):
        with (
            patch("resumes.services.resume_service.ResumeParserService") as MockParser,
            patch("resumes.services.resume_service.SkillExtrationService") as MockSkills,
            patch("resumes.services.resume_service.S3Service")            as MockS3,
            patch("resumes.services.resume_service.ResumeRepository")     as MockRepo,
            patch("resumes.services.resume_service.IndexingService"),
            patch("resumes.services.resume_service.threading")            as MockThread,
        ):
            MockParser.extract_text_from_pdf.return_value = "text"
            MockSkills.extract.return_value = []
            MockS3.return_value.upload_file.return_value = None
            MockRepo.return_value.save_resume.return_value = "5"
            mock_thread_instance = MagicMock()
            MockThread.Thread.return_value = mock_thread_instance

            from resumes.services.resume_service import ResumeService
            svc = ResumeService()
            svc.process_resume(_uploaded_file(), "1")
            MockThread.Thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()

    def test_thread_is_created_as_daemon(self):
        with (
            patch("resumes.services.resume_service.ResumeParserService") as MockParser,
            patch("resumes.services.resume_service.SkillExtrationService") as MockSkills,
            patch("resumes.services.resume_service.S3Service")            as MockS3,
            patch("resumes.services.resume_service.ResumeRepository")     as MockRepo,
            patch("resumes.services.resume_service.IndexingService"),
            patch("resumes.services.resume_service.threading")            as MockThread,
        ):
            MockParser.extract_text_from_pdf.return_value = "text"
            MockSkills.extract.return_value = []
            MockS3.return_value.upload_file.return_value = None
            MockRepo.return_value.save_resume.return_value = "5"
            MagicMock()
            MockThread.Thread.return_value = MagicMock()

            from resumes.services.resume_service import ResumeService
            svc = ResumeService()
            svc.process_resume(_uploaded_file(), "1")
            thread_kwargs = MockThread.Thread.call_args[1]
            self.assertTrue(thread_kwargs.get("daemon"))


class TestResumeServiceIndexAsync(unittest.TestCase):

    def test_index_async_sets_ready_on_success(self):
        with (
            patch("resumes.services.resume_service.IndexingService") as MockIndex,
            patch("resumes.services.resume_service.ResumeRepository") as MockRepo,
            patch("resumes.services.resume_service.S3Service"),
        ):
            from resumes.services.resume_service import ResumeService
            svc = ResumeService()
            svc._index_async("10", "full resume text")
            MockRepo.return_value.set_index_status.assert_called_once_with("10", "ready")

    def test_index_async_sets_error_on_indexing_failure(self):
        with (
            patch("resumes.services.resume_service.IndexingService") as MockIndex,
            patch("resumes.services.resume_service.ResumeRepository") as MockRepo,
            patch("resumes.services.resume_service.S3Service"),
        ):
            MockIndex.return_value.index_resume.side_effect = RuntimeError("embed failed")
            from resumes.services.resume_service import ResumeService
            svc = ResumeService()
            svc._index_async("10", "text")
            MockRepo.return_value.set_index_status.assert_called_once_with("10", "error")

    def test_index_async_calls_index_resume_with_correct_args(self):
        with (
            patch("resumes.services.resume_service.IndexingService") as MockIndex,
            patch("resumes.services.resume_service.ResumeRepository") as MockRepo,
            patch("resumes.services.resume_service.S3Service"),
        ):
            from resumes.services.resume_service import ResumeService
            svc = ResumeService()
            svc._index_async("resume_id_7", "some text")
            MockIndex.return_value.index_resume.assert_called_once_with("resume_id_7", "some text")


if __name__ == "__main__":
    unittest.main()
