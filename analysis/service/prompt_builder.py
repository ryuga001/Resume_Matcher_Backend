class PromptBuilder:
    @staticmethod
    def build(chunks: list, job_description: str) -> str:
        context = "\n\n---\n\n".join(c["text"] for c in chunks) if chunks else "No resume context available."

        return f"""You are an expert ATS (Applicant Tracking System) analyst and career coach.

RESUME CONTENT:
{context}

JOB DESCRIPTION:
{job_description}

Analyze how well this resume matches the job description. Return ONLY valid JSON in exactly this structure:

{{
  "atsScore": <integer 0-100>,
  "matchingSkills": [<list of skills/keywords from the job description found in the resume>],
  "missingSkills": [<list of important skills/keywords from the job description NOT found in the resume>],
  "recommendations": [<list of 3-5 specific, actionable improvements the candidate should make>],
  "summary": "<2-3 sentence summary of the match quality and main gaps>"
}}

Rules:
- atsScore: 0-100 integer. 85+ = strong match, 70-84 = good, 50-69 = partial, 30-49 = weak, <30 = poor
- matchingSkills: exact phrases from the job description that appear in the resume
- missingSkills: critical requirements from the job description not evidenced in the resume
- recommendations: specific, actionable steps (not generic advice). Reference actual content from both documents.
- summary: honest and specific. Mention the role title if identifiable.
- Return ONLY the JSON object, no markdown, no explanation."""
