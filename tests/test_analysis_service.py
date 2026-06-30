"""Unit tests — AnalysisService + PromptBuilder (all dependencies mocked)."""

import json
import unittest
from unittest.mock import MagicMock, patch

from analysis.service.prompt_builder import PromptBuilder


# ── PromptBuilder ──────────────────────────────────────────────────────────────

class TestPromptBuilder(unittest.TestCase):

    def test_includes_job_description_in_prompt(self):
        chunks = [{"text": "I know Python."}]
        prompt = PromptBuilder.build(chunks, "Senior Python Developer at Acme")
        self.assertIn("Senior Python Developer at Acme", prompt)

    def test_includes_resume_chunks_in_prompt(self):
        chunks = [{"text": "Led a team of 5 engineers."}, {"text": "Built ML pipeline."}]
        prompt = PromptBuilder.build(chunks, "some job")
        self.assertIn("Led a team of 5 engineers.", prompt)
        self.assertIn("Built ML pipeline.", prompt)

    def test_chunks_joined_by_separator(self):
        chunks = [{"text": "chunk A"}, {"text": "chunk B"}]
        prompt = PromptBuilder.build(chunks, "jd")
        self.assertIn("---", prompt)

    def test_empty_chunks_uses_fallback_text(self):
        prompt = PromptBuilder.build([], "some job")
        self.assertIn("No resume context available.", prompt)

    def test_prompt_requests_json_response(self):
        prompt = PromptBuilder.build([], "jd")
        self.assertIn("atsScore", prompt)
        self.assertIn("matchingSkills", prompt)
        self.assertIn("missingSkills", prompt)
        self.assertIn("recommendations", prompt)
        self.assertIn("summary", prompt)

    def test_returns_string(self):
        prompt = PromptBuilder.build([{"text": "text"}], "jd")
        self.assertIsInstance(prompt, str)


# ── AnalysisService ────────────────────────────────────────────────────────────

class TestAnalysisService(unittest.TestCase):

    VALID_RESULT = {
        "atsScore": 72,
        "matchingSkills": ["Python"],
        "missingSkills": ["Docker"],
        "recommendations": ["Add Docker to your skill set."],
        "summary": "Good match overall.",
    }

    def _make_service(self, llm_return):
        with (
            patch("analysis.service.analysis_service.RetrievalService") as MockRetrieval,
            patch("analysis.service.analysis_service.PromptBuilder")     as MockPB,
            patch("analysis.service.analysis_service.LLMService")        as MockLLM,
        ):
            MockRetrieval.return_value.retrieve.return_value = [{"text": "relevant chunk"}]
            MockPB.return_value.build.return_value = "built prompt"
            MockLLM.return_value.generate.return_value = llm_return

            from analysis.service.analysis_service import AnalysisService
            svc = AnalysisService()
            svc._retrieval = MockRetrieval.return_value
            svc._pb        = MockPB.return_value
            svc._llm       = MockLLM.return_value
        return svc

    def test_analyze_calls_retrieval_service(self):
        with (
            patch("analysis.service.analysis_service.RetrievalService") as MockRetrieval,
            patch("analysis.service.analysis_service.PromptBuilder"),
            patch("analysis.service.analysis_service.LLMService") as MockLLM,
        ):
            MockRetrieval.return_value.retrieve.return_value = []
            MockLLM.return_value.generate.return_value = json.dumps(self.VALID_RESULT)
            from analysis.service.analysis_service import AnalysisService
            AnalysisService.analyze("resume_1", "Backend role")
            MockRetrieval.return_value.retrieve.assert_called_once_with(
                resume_id="resume_1", job_description="Backend role", top_k=5
            )

    def test_analyze_returns_parsed_json(self):
        with (
            patch("analysis.service.analysis_service.RetrievalService") as MockR,
            patch("analysis.service.analysis_service.PromptBuilder"),
            patch("analysis.service.analysis_service.LLMService") as MockLLM,
        ):
            MockR.return_value.retrieve.return_value = []
            MockLLM.return_value.generate.return_value = json.dumps(self.VALID_RESULT)
            from analysis.service.analysis_service import AnalysisService
            result = AnalysisService.analyze("r1", "jd")
            self.assertEqual(result["atsScore"], 72)
            self.assertIn("Python", result["matchingSkills"])

    def test_analyze_returns_raw_response_on_json_parse_error(self):
        with (
            patch("analysis.service.analysis_service.RetrievalService") as MockR,
            patch("analysis.service.analysis_service.PromptBuilder"),
            patch("analysis.service.analysis_service.LLMService") as MockLLM,
        ):
            MockR.return_value.retrieve.return_value = []
            MockLLM.return_value.generate.return_value = "not valid json at all"
            from analysis.service.analysis_service import AnalysisService
            result = AnalysisService.analyze("r1", "jd")
            self.assertIn("rawResponse", result)
            self.assertEqual(result["rawResponse"], "not valid json at all")

    def test_analyze_passes_chunks_to_prompt_builder(self):
        with (
            patch("analysis.service.analysis_service.RetrievalService") as MockR,
            patch("analysis.service.analysis_service.PromptBuilder")     as MockPB,
            patch("analysis.service.analysis_service.LLMService") as MockLLM,
        ):
            chunks = [{"text": "chunk1"}, {"text": "chunk2"}]
            MockR.return_value.retrieve.return_value = chunks
            MockPB.return_value.build.return_value = "built prompt"
            MockLLM.return_value.generate.return_value = json.dumps(self.VALID_RESULT)
            from analysis.service.analysis_service import AnalysisService
            AnalysisService.analyze("r1", "jd text")
            MockPB.return_value.build.assert_called_once_with(chunks, "jd text")


if __name__ == "__main__":
    unittest.main()
