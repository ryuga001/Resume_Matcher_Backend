"""Unit tests — resume formatter strategy + factory."""

import unittest

from resumes.services.formatters.factory import ResumeFormatterFactory
from resumes.services.formatters.pdf_formatter import PDFResumeFormatter


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _full_resume():
    return {
        "contact": {
            "name": "Jane Dev",
            "email": "jane@example.com",
            "phone": "+1 555-0100",
            "location": "San Francisco, CA",
            "linkedin": "linkedin.com/in/janedev",
            "github": "github.com/janedev",
        },
        "summary": "Full-stack engineer with 5 years of experience.",
        "experience": [
            {
                "id": "e1",
                "company": "Acme Corp",
                "title": "Senior Engineer",
                "startDate": "Jan 2021",
                "endDate": "Present",
                "bullets": [
                    "Reduced latency by 40% through caching.",
                    "Led migration to microservices.",
                ],
            }
        ],
        "education": [
            {
                "id": "edu1",
                "institution": "MIT",
                "degree": "BS",
                "field": "Computer Science",
                "graduationDate": "May 2019",
                "gpa": "3.9",
            }
        ],
        "skills": ["Python", "React", "PostgreSQL", "Docker"],
        "projects": [
            {
                "id": "p1",
                "name": "OpenCV Pipeline",
                "description": "Real-time video processing pipeline.",
                "technologies": ["Python", "OpenCV"],
                "url": "https://github.com/janedev/pipeline",
            }
        ],
        "certifications": ["AWS Solutions Architect"],
    }


def _empty_resume():
    return {
        "contact": {},
        "summary": "",
        "experience": [],
        "education": [],
        "skills": [],
        "projects": [],
        "certifications": [],
    }


# ── PDFResumeFormatter ─────────────────────────────────────────────────────────

class TestPDFResumeFormatter(unittest.TestCase):

    def setUp(self):
        self.formatter = PDFResumeFormatter()

    def test_content_type_is_pdf(self):
        self.assertEqual(self.formatter.content_type, "application/pdf")

    def test_extension_is_pdf(self):
        self.assertEqual(self.formatter.extension, "pdf")

    def test_format_returns_bytes(self):
        result = self.formatter.format(_full_resume())
        self.assertIsInstance(result, bytes)

    def test_output_starts_with_pdf_magic_bytes(self):
        result = self.formatter.format(_full_resume())
        self.assertTrue(result.startswith(b"%PDF"), "Output must be a valid PDF")

    def test_format_empty_resume_does_not_raise(self):
        result = self.formatter.format(_empty_resume())
        self.assertIsInstance(result, bytes)
        self.assertTrue(result.startswith(b"%PDF"))

    def test_format_missing_optional_sections_does_not_raise(self):
        data = _full_resume()
        data["projects"] = []
        data["certifications"] = []
        result = self.formatter.format(data)
        self.assertIsInstance(result, bytes)

    def test_format_none_fields_do_not_raise(self):
        data = _full_resume()
        data["summary"] = None
        data["skills"] = None
        result = self.formatter.format(data)
        self.assertIsInstance(result, bytes)

    def test_long_content_produces_larger_output(self):
        short = self.formatter.format(_empty_resume())
        full  = self.formatter.format(_full_resume())
        self.assertGreater(len(full), len(short))


# ── ResumeFormatterFactory ─────────────────────────────────────────────────────

class TestResumeFormatterFactory(unittest.TestCase):

    def test_creates_pdf_formatter(self):
        formatter = ResumeFormatterFactory.create("pdf")
        self.assertIsInstance(formatter, PDFResumeFormatter)

    def test_case_insensitive_lookup(self):
        formatter = ResumeFormatterFactory.create("PDF")
        self.assertIsInstance(formatter, PDFResumeFormatter)

    def test_unknown_format_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            ResumeFormatterFactory.create("docx")
        self.assertIn("docx", str(ctx.exception))

    def test_empty_format_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            ResumeFormatterFactory.create("")

    def test_each_call_returns_new_instance(self):
        a = ResumeFormatterFactory.create("pdf")
        b = ResumeFormatterFactory.create("pdf")
        self.assertIsNot(a, b)


if __name__ == "__main__":
    unittest.main()
