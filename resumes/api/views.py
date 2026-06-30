from rest_framework.views import APIView
from rest_framework.response import Response

from users.auth import require_auth
from resumes.services.resume_service import ResumeService
from resumes.repositories.resume_repositories import ResumeRepository
from common.s3 import S3Service


class ResumeUploadView(APIView):
    @require_auth
    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file provided."}, status=400)
        if not file.name.lower().endswith(".pdf"):
            return Response({"error": "Only PDF files are supported."}, status=400)
        resume_id = ResumeService().process_resume(file, request.user_id)
        return Response({"resumeId": resume_id, "fileName": file.name, "indexStatus": "processing"}, status=201)


class ResumeListView(APIView):
    @require_auth
    def get(self, request):
        resumes = ResumeRepository().get_all_resumes(request.user_id)
        return Response([
            {
                "resumeId":    str(r["_id"]),
                "fileName":    r.get("fileName", "Unnamed"),
                "uploadedAt":  r["uploadedAt"].isoformat() if r.get("uploadedAt") else None,
                "indexStatus": r.get("indexStatus", "ready"),
                "skills":      r.get("skills", []),
            }
            for r in resumes
        ])


class ResumeDeleteView(APIView):
    @require_auth
    def delete(self, request, resume_id):
        s3_key = ResumeRepository().delete_resume(resume_id, request.user_id)
        if s3_key is None:
            return Response({"error": "Resume not found."}, status=404)
        if s3_key:
            S3Service().delete(s3_key)
        return Response({"success": True})
