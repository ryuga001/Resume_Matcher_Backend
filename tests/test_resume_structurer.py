"""Unit tests — ResumeStructurerService (Gemini fully mocked)."""

import json
import unittest
from unittest.mock import MagicMock, patch


VALID_STRUCTURED = {
    "contact": {"name": "Alice", "email": "alice@example.com", "phone": "", "location": "", "linkedin": "", "github": ""},
    "summary": "Software engineer.",
    "experience": [{"id": "e1", "company": "Acme", "title": "SWE", "startDate": "2020", "endDate": "Present", "bullets": []}],
    "education":  [{"id": "edu1", "institution": "MIT", "degree": "BS", "field": "CS", "graduationDate": "2019", "gpa": ""}],
    "skills": ["Python", "Django"],
    "projects": [],
    "certifications": [],
}


class TestResumeStructurerService(unittest.TestCase):

    def _make_service(self, llm_return: str):
        with patch("resumes.services.resume_structurer_service.LLMService") as MockLLM:
            MockLLM.return_value.generate.return_value = llm_return
            from resumes.services.resume_structurer_service import ResumeStructurerService
            svc = ResumeStructurerService()
            svc._llm = MockLLM.return_value
        return svc

    # ── structure() ───────────────────────────────────────────────────────────

    def test_structure_returns_parsed_dict_on_valid_json(self):
        svc = self._make_service(json.dumps(VALID_STRUCTURED))
        result = svc.structure("Alice's resume text")
        self.assertEqual(result["contact"]["name"], "Alice")
        self.assertEqual(result["skills"], ["Python", "Django"])

    def test_structure_calls_llm_with_resume_text(self):
        svc = self._make_service(json.dumps(VALID_STRUCTURED))
        svc.structure("unique resume content here")
        call_args = svc._llm.generate.call_args[0][0]
        self.assertIn("unique resume content here", call_args)

    def test_structure_returns_empty_dict_on_invalid_json(self):
        svc = self._make_service("this is not json at all")
        result = svc.structure("some text")
        self.assertIsInstance(result, dict)

    def test_structure_ensures_ids_on_entries(self):
        data_no_ids = {
            **VALID_STRUCTURED,
            "experience": [{"company": "X", "title": "Y", "startDate": "", "endDate": "", "bullets": []}],
        }
        svc = self._make_service(json.dumps(data_no_ids))
        result = svc.structure("text")
        self.assertTrue(result["experience"][0].get("id"), "id must be injected when missing")

    def test_structure_preserves_existing_ids(self):
        svc = self._make_service(json.dumps(VALID_STRUCTURED))
        result = svc.structure("text")
        self.assertEqual(result["experience"][0]["id"], "e1")

    # ── build() ───────────────────────────────────────────────────────────────

    def test_build_calls_llm_with_recommendations(self):
        svc = self._make_service(json.dumps(VALID_STRUCTURED))
        svc.build(VALID_STRUCTURED, ["Add Docker"], ["Docker"], "We need Docker")
        prompt = svc._llm.generate.call_args[0][0]
        self.assertIn("Add Docker", prompt)

    def test_build_calls_llm_with_missing_skills(self):
        svc = self._make_service(json.dumps(VALID_STRUCTURED))
        svc.build(VALID_STRUCTURED, [], ["Kubernetes"], "")
        prompt = svc._llm.generate.call_args[0][0]
        self.assertIn("Kubernetes", prompt)

    def test_build_returns_parsed_enhanced_json(self):
        enhanced = {**VALID_STRUCTURED, "summary": "Enhanced summary."}
        svc = self._make_service(json.dumps(enhanced))
        result = svc.build(VALID_STRUCTURED, [], [], "")
        self.assertEqual(result["summary"], "Enhanced summary.")

    def test_build_falls_back_to_original_on_parse_error(self):
        svc = self._make_service("not valid json")
        result = svc.build(VALID_STRUCTURED, [], [], "")
        self.assertEqual(result["contact"]["name"], "Alice")

    def test_build_includes_job_description_in_prompt(self):
        svc = self._make_service(json.dumps(VALID_STRUCTURED))
        svc.build(VALID_STRUCTURED, [], [], "Senior Python engineer at a fintech startup")
        prompt = svc._llm.generate.call_args[0][0]
        self.assertIn("Senior Python engineer at a fintech startup", prompt)

    # ── _ensure_ids() ─────────────────────────────────────────────────────────

    def test_ensure_ids_adds_id_to_all_sections(self):
        from resumes.services.resume_structurer_service import ResumeStructurerService
        data = {
            "experience": [{"company": "A"}],
            "education":  [{"institution": "B"}],
            "projects":   [{"name": "C"}],
        }
        result = ResumeStructurerService._ensure_ids(data)
        self.assertTrue(result["experience"][0].get("id"))
        self.assertTrue(result["education"][0].get("id"))
        self.assertTrue(result["projects"][0].get("id"))

    def test_ensure_ids_does_not_overwrite_existing_id(self):
        from resumes.services.resume_structurer_service import ResumeStructurerService
        data = {"experience": [{"id": "original_id", "company": "A"}], "education": [], "projects": []}
        result = ResumeStructurerService._ensure_ids(data)
        self.assertEqual(result["experience"][0]["id"], "original_id")

    def test_ensure_ids_handles_missing_sections_gracefully(self):
        from resumes.services.resume_structurer_service import ResumeStructurerService
        result = ResumeStructurerService._ensure_ids({})
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
