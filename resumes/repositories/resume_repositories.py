from __future__ import annotations

from resumes.models import Resume


class ResumeRepository:
    """Data-access layer for Resume."""

    def save_resume(self, data: dict) -> str:
        resume = Resume.objects.create(
            user_id=int(data["userId"]),
            file_name=data["fileName"],
            resume_text=data.get("resumeText", ""),
            skills=data.get("skills", []),
            s3_key=data.get("s3Key", ""),
            index_status="processing",
        )
        return str(resume.id)

    def get_resume_by_id(self, resume_id: str, user_id: str | None = None) -> dict | None:
        try:
            qs = Resume.objects.filter(id=int(resume_id))
            if user_id is not None:
                qs = qs.filter(user_id=int(user_id))
            r = qs.first()
            return self._serialize(r) if r else None
        except (ValueError, TypeError):
            return None

    def get_all_resumes(self, user_id: str) -> list[dict]:
        return [self._serialize(r) for r in Resume.objects.filter(user_id=int(user_id))]

    def set_index_status(self, resume_id: str, status: str) -> None:
        Resume.objects.filter(id=int(resume_id)).update(index_status=status)

    def delete_resume(self, resume_id: str, user_id: str) -> str | None:
        """Delete the record and return the s3_key (if any) so the caller can clean S3."""
        try:
            resume = Resume.objects.get(id=int(resume_id), user_id=int(user_id))
        except Resume.DoesNotExist:
            return None
        s3_key = resume.s3_key or ""
        resume.delete()
        return s3_key

    @staticmethod
    def _serialize(r: Resume) -> dict:
        return {
            "_id":         str(r.id),
            "resumeId":    str(r.id),
            "userId":      str(r.user_id),
            "fileName":    r.file_name,
            "resumeText":  r.resume_text,
            "skills":      r.skills,
            "s3Key":       r.s3_key,
            "uploadedAt":  r.uploaded_at,
            "indexStatus": r.index_status,
        }
