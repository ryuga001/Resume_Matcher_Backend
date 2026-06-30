"""Unit tests — SkillExtractionService (pure logic, no mocking needed)."""

import unittest

from resumes.services.skill_extraction_service import SkillExtrationService


class TestSkillExtractionService(unittest.TestCase):

    def test_extracts_known_skill_exact_case(self):
        result = SkillExtrationService.extract("I have experience with Python and Django.")
        self.assertIn("Python", result)
        self.assertIn("Django", result)

    def test_extraction_is_case_insensitive(self):
        result = SkillExtrationService.extract("Expert in PYTHON, react, and docker.")
        self.assertIn("Python", result)
        self.assertIn("React", result)
        self.assertIn("Docker", result)

    def test_unknown_term_not_extracted(self):
        result = SkillExtrationService.extract("I use FooBarLang and QuantumScript.")
        self.assertNotIn("FooBarLang", result)

    def test_returns_canonical_casing(self):
        result = SkillExtrationService.extract("postgresql and react and next.js")
        self.assertIn("PostgreSQL", result)
        self.assertIn("React", result)
        self.assertIn("Next.js", result)

    def test_empty_string_returns_empty_list(self):
        result = SkillExtrationService.extract("")
        self.assertEqual(result, [])

    def test_no_duplicates_in_output(self):
        result = SkillExtrationService.extract("Python python PYTHON")
        self.assertEqual(result.count("Python"), 1)

    def test_multiple_skills_extracted_from_long_text(self):
        text = (
            "Led a team building a React frontend with TypeScript. "
            "Backend was Django + PostgreSQL deployed on AWS with Docker and Kubernetes."
        )
        result = SkillExtrationService.extract(text)
        for expected in ["React", "TypeScript", "Django", "PostgreSQL", "AWS", "Docker", "Kubernetes"]:
            self.assertIn(expected, result, f"Expected '{expected}' to be extracted")

    def test_returns_list(self):
        result = SkillExtrationService.extract("Python developer")
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
