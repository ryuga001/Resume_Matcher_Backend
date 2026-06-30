"""Unit tests — resume enhancer decorator chain."""

import copy
import unittest

from resumes.services.enhancers.base_enhancer import ResumeEnhancer
from resumes.services.enhancers.skills_enhancer import SkillsEnhancer
from resumes.services.enhancers.keyword_enhancer import KeywordEnhancer
from resumes.services.enhancers.summary_enhancer import SummaryEnhancer


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _base_data():
    return {
        "contact": {"name": "Jane Dev"},
        "summary": "Experienced backend engineer.",
        "experience": [
            {
                "id": "abc1",
                "company": "Acme",
                "title": "Engineer",
                "startDate": "Jan 2022",
                "endDate": "Present",
                "bullets": ["Built REST APIs using Python and Django."],
            }
        ],
        "skills": ["Python", "Django"],
        "projects": [],
        "education": [],
        "certifications": [],
    }


# ── SkillsEnhancer ─────────────────────────────────────────────────────────────

class TestSkillsEnhancer(unittest.TestCase):

    def test_adds_missing_skills(self):
        data = _base_data()
        ctx = {"missingSkills": ["Docker", "Kubernetes"]}
        result = SkillsEnhancer().enhance(data, ctx)
        self.assertIn("Docker", result["skills"])
        self.assertIn("Kubernetes", result["skills"])

    def test_does_not_duplicate_existing_skill(self):
        data = _base_data()
        ctx = {"missingSkills": ["Python"]}   # already present
        result = SkillsEnhancer().enhance(data, ctx)
        self.assertEqual(result["skills"].count("Python"), 1)

    def test_case_insensitive_dedup(self):
        data = _base_data()
        ctx = {"missingSkills": ["python"]}   # lowercase duplicate
        result = SkillsEnhancer().enhance(data, ctx)
        self.assertEqual(result["skills"].count("Python") + result["skills"].count("python"), 1)

    def test_no_change_when_context_empty(self):
        data = _base_data()
        result = SkillsEnhancer().enhance(data, {})
        self.assertEqual(result["skills"], ["Python", "Django"])

    def test_does_not_mutate_original(self):
        data = _base_data()
        original_skills = copy.deepcopy(data["skills"])
        SkillsEnhancer().enhance(data, {"missingSkills": ["Docker"]})
        self.assertEqual(data["skills"], original_skills)

    def test_empty_missing_skills_list(self):
        data = _base_data()
        result = SkillsEnhancer().enhance(data, {"missingSkills": []})
        self.assertEqual(result["skills"], ["Python", "Django"])


# ── KeywordEnhancer ────────────────────────────────────────────────────────────

class TestKeywordEnhancer(unittest.TestCase):

    def test_appends_bullet_for_missing_keywords(self):
        data = _base_data()
        ctx = {
            "missingSkills": ["Kubernetes", "Terraform"],
            "jobDescription": "We need Kubernetes and Terraform expertise.",
        }
        result = KeywordEnhancer().enhance(data, ctx)
        bullets = result["experience"][0]["bullets"]
        self.assertGreater(len(bullets), 1)
        last_bullet = bullets[-1].lower()
        self.assertTrue("kubernetes" in last_bullet or "terraform" in last_bullet)

    def test_no_bullet_when_keyword_already_in_resume(self):
        data = _base_data()
        ctx = {
            "missingSkills": ["Python"],   # already in experience bullets
            "jobDescription": "Python developer needed.",
        }
        original_count = len(data["experience"][0]["bullets"])
        result = KeywordEnhancer().enhance(data, ctx)
        self.assertEqual(len(result["experience"][0]["bullets"]), original_count)

    def test_no_change_when_no_missing_skills(self):
        data = _base_data()
        ctx = {"missingSkills": [], "jobDescription": "Any job."}
        result = KeywordEnhancer().enhance(data, ctx)
        self.assertEqual(result["experience"][0]["bullets"], data["experience"][0]["bullets"])

    def test_no_change_when_no_job_description(self):
        data = _base_data()
        ctx = {"missingSkills": ["Docker"], "jobDescription": ""}
        original_count = len(data["experience"][0]["bullets"])
        result = KeywordEnhancer().enhance(data, ctx)
        self.assertEqual(len(result["experience"][0]["bullets"]), original_count)

    def test_no_change_when_no_experience_entries(self):
        data = _base_data()
        data["experience"] = []
        ctx = {"missingSkills": ["Docker"], "jobDescription": "Docker needed."}
        result = KeywordEnhancer().enhance(data, ctx)
        self.assertEqual(result["experience"], [])

    def test_does_not_mutate_original(self):
        data = _base_data()
        original_bullets = copy.deepcopy(data["experience"][0]["bullets"])
        KeywordEnhancer().enhance(data, {"missingSkills": ["Terraform"], "jobDescription": "Terraform."})
        self.assertEqual(data["experience"][0]["bullets"], original_bullets)


# ── SummaryEnhancer ────────────────────────────────────────────────────────────

class TestSummaryEnhancer(unittest.TestCase):

    def test_prepends_recommendation_to_existing_summary(self):
        data = _base_data()
        ctx = {"recommendations": ["Add Docker experience to your profile."]}
        result = SummaryEnhancer().enhance(data, ctx)
        self.assertTrue(result["summary"].startswith("Add Docker experience to your profile."))
        self.assertIn("Experienced backend engineer.", result["summary"])

    def test_creates_summary_from_recommendation_when_none_exists(self):
        data = _base_data()
        data["summary"] = ""
        ctx = {"recommendations": ["Highlight cloud certifications."]}
        result = SummaryEnhancer().enhance(data, ctx)
        self.assertIn("Highlight cloud certifications.", result["summary"])

    def test_no_change_when_no_recommendations(self):
        data = _base_data()
        original = data["summary"]
        result = SummaryEnhancer().enhance(data, {"recommendations": []})
        self.assertEqual(result["summary"], original)

    def test_no_change_when_context_missing_key(self):
        data = _base_data()
        original = data["summary"]
        result = SummaryEnhancer().enhance(data, {})
        self.assertEqual(result["summary"], original)

    def test_does_not_mutate_original(self):
        data = _base_data()
        original_summary = data["summary"]
        SummaryEnhancer().enhance(data, {"recommendations": ["Something."]})
        self.assertEqual(data["summary"], original_summary)


# ── Decorator chain ────────────────────────────────────────────────────────────

class TestDecoratorChain(unittest.TestCase):

    def test_chain_applies_all_three_enhancers(self):
        data = _base_data()
        ctx = {
            "missingSkills": ["Docker"],
            "jobDescription": "Docker expertise required.",
            "recommendations": ["Quantify your achievements."],
        }
        chain = SummaryEnhancer(KeywordEnhancer(SkillsEnhancer()))
        result = chain.enhance(data, ctx)

        # SkillsEnhancer ran
        self.assertIn("Docker", result["skills"])
        # SummaryEnhancer ran
        self.assertTrue(result["summary"].startswith("Quantify your achievements."))

    def test_wrapped_enhancer_runs_before_outer(self):
        call_order: list[str] = []

        class First(ResumeEnhancer):
            def _apply(self, data, context):
                call_order.append("first")
                return data

        class Second(ResumeEnhancer):
            def _apply(self, data, context):
                call_order.append("second")
                return data

        Second(First()).enhance({}, {})
        self.assertEqual(call_order, ["first", "second"])

    def test_single_enhancer_without_wrapped(self):
        data = _base_data()
        result = SkillsEnhancer().enhance(data, {"missingSkills": ["Go"]})
        self.assertIn("Go", result["skills"])

    def test_chain_output_is_independent_copy(self):
        data = _base_data()
        ctx = {"missingSkills": ["Rust"]}
        result = SkillsEnhancer().enhance(data, ctx)
        self.assertIsNot(result, data)


if __name__ == "__main__":
    unittest.main()
