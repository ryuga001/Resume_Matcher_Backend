from rest_framework.views import APIView
from rest_framework.response import Response

from users.auth import require_auth
from users.repository import UserRepository
from analysis.service.analysis_service import AnalysisService
from analysis.repository.analysis_repository import AnalysisRepository
from resumes.repositories.resume_repositories import ResumeRepository


class ResumeAnalysisView(APIView):
    @require_auth
    def post(self, request):
        resume_id       = request.data.get("resumeId")
        job_description = request.data.get("jobDescription", "").strip()
        if not resume_id or not job_description:
            return Response({"error": "resumeId and jobDescription are required."}, status=400)

        user_repo = UserRepository()
        uses_left = user_repo.get_uses_left(request.user_id)
        if uses_left <= 0:
            return Response({"error": "No analysis credits remaining."}, status=429)

        resume = ResumeRepository().get_resume_by_id(resume_id, request.user_id)
        if not resume:
            return Response({"error": "Resume not found."}, status=404)

        remaining = user_repo.decrement_uses(request.user_id)
        result    = AnalysisService().analyze(resume_id, job_description)

        AnalysisRepository().save(
            user_id=request.user_id,
            resume_id=resume_id,
            resume_name=resume.get("fileName", "Unnamed"),
            job_description=job_description,
            result=result,
        )
        return Response({**result, "usesLeft": remaining})


class AnalysisHistoryView(APIView):
    @require_auth
    def get(self, request):
        history = AnalysisRepository().get_history(request.user_id)
        return Response([
            {
                "id":             h["_id"],
                "resumeId":       h.get("resumeId"),
                "resumeName":     h.get("resumeName", "Unnamed"),
                "jobDescription": h.get("jobDescription", ""),
                "atsScore":       h.get("result", {}).get("atsScore"),
                "createdAt":      h["createdAt"].isoformat() if h.get("createdAt") else None,
            }
            for h in history
        ])


class AnalysisDetailView(APIView):
    @require_auth
    def get(self, request, analysis_id):
        item = AnalysisRepository().get_by_id(analysis_id, request.user_id)
        if not item:
            return Response({"error": "Analysis not found."}, status=404)
        return Response({
            "id":             item["_id"],
            "resumeName":     item.get("resumeName", "Unnamed"),
            "jobDescription": item.get("jobDescription", ""),
            "createdAt":      item["createdAt"].isoformat() if item.get("createdAt") else None,
            **item.get("result", {}),
        })
