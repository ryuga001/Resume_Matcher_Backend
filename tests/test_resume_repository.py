"""Unit tests — ResumeRepository (Django ORM fully mocked)."""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime


def _mock_resume(**kwargs):
    """Return a Mock that looks like a Resume model instance."""
    r = MagicMock()
    r.id               = kwargs.get("id", 1)
    r.user_id          = kwargs.get("user_id", 42)
    r.file_name        = kwargs.get("file_name", "resume.pdf")
    r.resume_text      = kwargs.get("resume_text", "Python developer")
    r.skills           = kwargs.get("skills", ["Python"])
    r.s3_key           = kwargs.get("s3_key", "resumes/abc.pdf")
    r.customized_s3_key = kwargs.get("customized_s3_key", "")
    r.structured_data  = kwargs.get("structured_data", None)
    r.uploaded_at      = kwargs.get("uploaded_at", datetime(2024, 1, 1))
    r.index_status     = kwargs.get("index_status", "ready")
    return r


class TestResumeRepositorySerialize(unittest.TestCase):
    """Test _serialize() without hitting the database."""

    def test_serialize_returns_expected_keys(self):
        from resumes.repositories.resume_repositories import ResumeRepository
        r = _mock_resume()
        result = ResumeRepository._serialize(r)
        for key in ("_id", "resumeId", "userId", "fileName", "resumeText",
                    "skills", "s3Key", "customizedS3Key", "structuredData",
                    "uploadedAt", "indexStatus"):
            self.assertIn(key, result, f"Missing key: {key}")

    def test_serialize_id_is_string(self):
        from resumes.repositories.resume_repositories import ResumeRepository
        r = _mock_resume(id=99)
        result = ResumeRepository._serialize(r)
        self.assertEqual(result["_id"], "99")
        self.assertEqual(result["resumeId"], "99")

    def test_serialize_user_id_is_string(self):
        from resumes.repositories.resume_repositories import ResumeRepository
        r = _mock_resume(user_id=7)
        result = ResumeRepository._serialize(r)
        self.assertEqual(result["userId"], "7")

    def test_serialize_customized_s3_key_included(self):
        from resumes.repositories.resume_repositories import ResumeRepository
        r = _mock_resume(customized_s3_key="resumes/custom/xyz.pdf")
        result = ResumeRepository._serialize(r)
        self.assertEqual(result["customizedS3Key"], "resumes/custom/xyz.pdf")

    def test_serialize_structured_data_included(self):
        from resumes.repositories.resume_repositories import ResumeRepository
        data = {"contact": {"name": "Alice"}, "skills": ["Python"]}
        r = _mock_resume(structured_data=data)
        result = ResumeRepository._serialize(r)
        self.assertEqual(result["structuredData"], data)

    def test_serialize_structured_data_none_when_absent(self):
        from resumes.repositories.resume_repositories import ResumeRepository
        r = _mock_resume(structured_data=None)
        result = ResumeRepository._serialize(r)
        self.assertIsNone(result["structuredData"])


class TestResumeRepositorySaveResume(unittest.TestCase):

    @patch("resumes.repositories.resume_repositories.Resume")
    def test_save_resume_returns_string_id(self, MockResume):
        mock_instance = _mock_resume(id=5)
        MockResume.objects.create.return_value = mock_instance
        from resumes.repositories.resume_repositories import ResumeRepository
        repo = ResumeRepository()
        result = repo.save_resume({
            "userId": "42", "fileName": "cv.pdf",
            "resumeText": "Engineer", "skills": ["Python"], "s3Key": "r/abc.pdf",
        })
        self.assertEqual(result, "5")

    @patch("resumes.repositories.resume_repositories.Resume")
    def test_save_resume_passes_index_status_processing(self, MockResume):
        mock_instance = _mock_resume(id=10)
        MockResume.objects.create.return_value = mock_instance
        from resumes.repositories.resume_repositories import ResumeRepository
        repo = ResumeRepository()
        repo.save_resume({"userId": "1", "fileName": "f.pdf", "s3Key": "k"})
        kwargs = MockResume.objects.create.call_args[1]
        self.assertEqual(kwargs["index_status"], "processing")


class TestResumeRepositoryDeleteResume(unittest.TestCase):

    @patch("resumes.repositories.resume_repositories.Resume")
    def test_delete_returns_dict_with_both_keys(self, MockResume):
        mock_instance = _mock_resume(s3_key="r/orig.pdf", customized_s3_key="r/cust.pdf")
        MockResume.objects.get.return_value = mock_instance
        from resumes.repositories.resume_repositories import ResumeRepository
        repo = ResumeRepository()
        result = repo.delete_resume("1", "42")
        self.assertEqual(result["s3Key"], "r/orig.pdf")
        self.assertEqual(result["customizedS3Key"], "r/cust.pdf")
        mock_instance.delete.assert_called_once()

    @patch("resumes.repositories.resume_repositories.Resume")
    def test_delete_returns_none_when_not_found(self, MockResume):
        from django.core.exceptions import ObjectDoesNotExist
        MockResume.DoesNotExist = type("DoesNotExist", (Exception,), {})
        MockResume.objects.get.side_effect = MockResume.DoesNotExist
        from resumes.repositories.resume_repositories import ResumeRepository
        repo = ResumeRepository()
        result = repo.delete_resume("999", "42")
        self.assertIsNone(result)

    @patch("resumes.repositories.resume_repositories.Resume")
    def test_delete_empty_customized_key_returned_as_empty_string(self, MockResume):
        mock_instance = _mock_resume(s3_key="r/orig.pdf", customized_s3_key="")
        MockResume.objects.get.return_value = mock_instance
        from resumes.repositories.resume_repositories import ResumeRepository
        repo = ResumeRepository()
        result = repo.delete_resume("1", "42")
        self.assertEqual(result["customizedS3Key"], "")


class TestResumeRepositorySaveStructuredData(unittest.TestCase):

    @patch("resumes.repositories.resume_repositories.Resume")
    def test_save_structured_data_calls_update(self, MockResume):
        qs = MagicMock()
        qs.update.return_value = 1
        MockResume.objects.filter.return_value = qs
        from resumes.repositories.resume_repositories import ResumeRepository
        repo = ResumeRepository()
        data = {"contact": {"name": "Alice"}}
        result = repo.save_structured_data("1", "42", data)
        qs.update.assert_called_once_with(structured_data=data)
        self.assertTrue(result)

    @patch("resumes.repositories.resume_repositories.Resume")
    def test_save_structured_data_returns_false_when_not_found(self, MockResume):
        qs = MagicMock()
        qs.update.return_value = 0
        MockResume.objects.filter.return_value = qs
        from resumes.repositories.resume_repositories import ResumeRepository
        repo = ResumeRepository()
        result = repo.save_structured_data("999", "42", {})
        self.assertFalse(result)


class TestResumeRepositorySaveCustomizedKey(unittest.TestCase):

    @patch("resumes.repositories.resume_repositories.Resume")
    def test_save_customized_key_calls_update(self, MockResume):
        qs = MagicMock()
        qs.update.return_value = 1
        MockResume.objects.filter.return_value = qs
        from resumes.repositories.resume_repositories import ResumeRepository
        repo = ResumeRepository()
        result = repo.save_customized_key("1", "42", "resumes/custom/new.pdf")
        qs.update.assert_called_once_with(customized_s3_key="resumes/custom/new.pdf")
        self.assertTrue(result)

    @patch("resumes.repositories.resume_repositories.Resume")
    def test_save_customized_key_returns_false_when_no_row_updated(self, MockResume):
        qs = MagicMock()
        qs.update.return_value = 0
        MockResume.objects.filter.return_value = qs
        from resumes.repositories.resume_repositories import ResumeRepository
        repo = ResumeRepository()
        result = repo.save_customized_key("999", "42", "key.pdf")
        self.assertFalse(result)


class TestResumeRepositoryGetById(unittest.TestCase):

    @patch("resumes.repositories.resume_repositories.Resume")
    def test_get_by_id_returns_serialized_dict(self, MockResume):
        qs = MagicMock()
        qs.first.return_value = _mock_resume(id=3)
        MockResume.objects.filter.return_value = qs
        from resumes.repositories.resume_repositories import ResumeRepository
        repo = ResumeRepository()
        result = repo.get_resume_by_id("3")
        self.assertEqual(result["resumeId"], "3")

    @patch("resumes.repositories.resume_repositories.Resume")
    def test_get_by_id_returns_none_when_not_found(self, MockResume):
        qs = MagicMock()
        qs.first.return_value = None
        MockResume.objects.filter.return_value = qs
        from resumes.repositories.resume_repositories import ResumeRepository
        repo = ResumeRepository()
        result = repo.get_resume_by_id("999")
        self.assertIsNone(result)

    @patch("resumes.repositories.resume_repositories.Resume")
    def test_get_by_id_returns_none_for_invalid_id(self, MockResume):
        from resumes.repositories.resume_repositories import ResumeRepository
        repo = ResumeRepository()
        result = repo.get_resume_by_id("not-a-number")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
