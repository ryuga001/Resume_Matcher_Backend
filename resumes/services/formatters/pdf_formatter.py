from __future__ import annotations

import io
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    ListFlowable,
    ListItem,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

from resumes.services.formatters.base_formatter import ResumeFormatter


# ── Style constants ────────────────────────────────────────────────────────────

_DARK   = colors.HexColor("#1a1917")
_MUTED  = colors.HexColor("#5a5550")
_ACCENT = colors.HexColor("#c2652a")
_RULE   = colors.HexColor("#e4dcd6")

_NAME = ParagraphStyle(
    "Name",
    fontName="Helvetica-Bold",
    fontSize=22,
    leading=26,
    textColor=_DARK,
    alignment=TA_CENTER,
    spaceAfter=2,
)
_CONTACT = ParagraphStyle(
    "Contact",
    fontName="Helvetica",
    fontSize=9,
    leading=12,
    textColor=_MUTED,
    alignment=TA_CENTER,
    spaceAfter=4,
)
_SECTION = ParagraphStyle(
    "Section",
    fontName="Helvetica-Bold",
    fontSize=10,
    leading=13,
    textColor=_ACCENT,
    spaceAfter=3,
    spaceBefore=10,
    textTransform="uppercase",
    letterSpacing=1,
)
_ENTRY_TITLE = ParagraphStyle(
    "EntryTitle",
    fontName="Helvetica-Bold",
    fontSize=10,
    leading=13,
    textColor=_DARK,
    spaceAfter=1,
)
_ENTRY_META = ParagraphStyle(
    "EntryMeta",
    fontName="Helvetica-Oblique",
    fontSize=9,
    leading=12,
    textColor=_MUTED,
    spaceAfter=3,
)
_BODY = ParagraphStyle(
    "Body",
    fontName="Helvetica",
    fontSize=9,
    leading=13,
    textColor=_DARK,
    spaceAfter=2,
)
_BULLET = ParagraphStyle(
    "Bullet",
    fontName="Helvetica",
    fontSize=9,
    leading=13,
    textColor=_DARK,
    leftIndent=10,
    spaceAfter=1,
)
_SKILL = ParagraphStyle(
    "Skill",
    fontName="Helvetica",
    fontSize=9,
    leading=13,
    textColor=_DARK,
    spaceAfter=2,
)


class PDFResumeFormatter(ResumeFormatter):
    """Concrete strategy — renders structured resume data as a PDF using ReportLab."""

    @property
    def content_type(self) -> str:
        return "application/pdf"

    @property
    def extension(self) -> str:
        return "pdf"

    def format(self, data: dict[str, Any]) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
        )
        story: list = []

        self._header(story, data)
        self._section_summary(story, data)
        self._section_experience(story, data)
        self._section_education(story, data)
        self._section_skills(story, data)
        self._section_projects(story, data)
        self._section_certifications(story, data)

        doc.build(story)
        return buf.getvalue()

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _rule(story: list) -> None:
        story.append(HRFlowable(width="100%", thickness=0.5, color=_RULE, spaceAfter=4))

    def _section_heading(self, story: list, title: str) -> None:
        story.append(Paragraph(title, _SECTION))
        self._rule(story)

    def _header(self, story: list, data: dict) -> None:
        c = data.get("contact", {})
        name = c.get("name", "").strip() or "Resume"
        story.append(Paragraph(name, _NAME))

        parts = [
            c.get("email", ""),
            c.get("phone", ""),
            c.get("location", ""),
            c.get("linkedin", ""),
            c.get("github", ""),
        ]
        contact_line = "  ·  ".join(p.strip() for p in parts if p.strip())
        if contact_line:
            story.append(Paragraph(contact_line, _CONTACT))

        self._rule(story)

    def _section_summary(self, story: list, data: dict) -> None:
        summary = (data.get("summary") or "").strip()
        if not summary:
            return
        self._section_heading(story, "Summary")
        story.append(Paragraph(summary, _BODY))

    def _section_experience(self, story: list, data: dict) -> None:
        entries = data.get("experience") or []
        if not entries:
            return
        self._section_heading(story, "Experience")
        for exp in entries:
            title = f"{exp.get('title', '')} — {exp.get('company', '')}"
            dates = f"{exp.get('startDate', '')} – {exp.get('endDate', 'Present')}"
            story.append(Paragraph(title.strip(" —"), _ENTRY_TITLE))
            story.append(Paragraph(dates, _ENTRY_META))
            for bullet in exp.get("bullets") or []:
                story.append(Paragraph(f"• {bullet}", _BULLET))
            story.append(Spacer(1, 3))

    def _section_education(self, story: list, data: dict) -> None:
        entries = data.get("education") or []
        if not entries:
            return
        self._section_heading(story, "Education")
        for edu in entries:
            heading = f"{edu.get('degree', '')} in {edu.get('field', '')}".strip(" in")
            story.append(Paragraph(heading, _ENTRY_TITLE))
            meta_parts = [edu.get("institution", ""), edu.get("graduationDate", "")]
            if edu.get("gpa"):
                meta_parts.append(f"GPA: {edu['gpa']}")
            story.append(Paragraph("  ·  ".join(p for p in meta_parts if p), _ENTRY_META))
            story.append(Spacer(1, 3))

    def _section_skills(self, story: list, data: dict) -> None:
        skills = data.get("skills") or []
        if not skills:
            return
        self._section_heading(story, "Skills")
        story.append(Paragraph(",  ".join(skills), _SKILL))

    def _section_projects(self, story: list, data: dict) -> None:
        projects = data.get("projects") or []
        if not projects:
            return
        self._section_heading(story, "Projects")
        for proj in projects:
            name = proj.get("name", "")
            url = proj.get("url", "")
            title_text = f"{name}  <font color='#c2652a'>{url}</font>" if url else name
            story.append(Paragraph(title_text, _ENTRY_TITLE))
            if proj.get("description"):
                story.append(Paragraph(proj["description"], _BODY))
            tech = proj.get("technologies") or []
            if tech:
                story.append(Paragraph(f"Technologies: {', '.join(tech)}", _ENTRY_META))
            story.append(Spacer(1, 3))

    def _section_certifications(self, story: list, data: dict) -> None:
        certs = data.get("certifications") or []
        if not certs:
            return
        self._section_heading(story, "Certifications")
        for cert in certs:
            story.append(Paragraph(f"• {cert}", _BULLET))
