from __future__ import annotations

from analysis.models import Analysis


class AnalysisRepository:
    """Data-access layer for Analysis."""

    def save(
        self,
        user_id: str,
        resume_id: str,
        resume_name: str,
        job_description: str,
        result: dict,
    ) -> str:
        a = Analysis.objects.create(
            user_id=int(user_id),
            resume_id=int(resume_id),
            resume_name=resume_name,
            job_description=job_description[:500],
            result=result,
        )
        return str(a.id)

    def get_history(self, user_id: str, limit: int = 20) -> list[dict]:
        return [
            self._serialize(a)
            for a in Analysis.objects.filter(user_id=int(user_id))[:limit]
        ]

    def get_by_id(self, analysis_id: str, user_id: str) -> dict | None:
        try:
            a = Analysis.objects.get(id=int(analysis_id), user_id=int(user_id))
            return self._serialize(a)
        except (Analysis.DoesNotExist, ValueError, TypeError):
            return None

    @staticmethod
    def _serialize(a: Analysis) -> dict:
        return {
            "_id":            str(a.id),
            "userId":         str(a.user_id),
            "resumeId":       str(a.resume_id),
            "resumeName":     a.resume_name,
            "jobDescription": a.job_description,
            "result":         a.result,
            "createdAt":      a.created_at,
        }
