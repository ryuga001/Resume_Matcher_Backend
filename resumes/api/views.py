from rest_framework.views import APIView
from rest_framework.response import Response

from users.auth import require_auth
from resumes.services.resume_service import ResumeService
from resumes.services.resume_builder_service import ResumeBuilderService
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
                "resumeId":         str(r["_id"]),
                "fileName":         r.get("fileName", "Unnamed"),
                "uploadedAt":       r["uploadedAt"].isoformat() if r.get("uploadedAt") else None,
                "indexStatus":      r.get("indexStatus", "ready"),
                "skills":           r.get("skills", []),
                "hasCustomized":    bool(r.get("customizedS3Key")),
            }
            for r in resumes
        ])


class ResumeDeleteView(APIView):
    @require_auth
    def delete(self, request, resume_id):
        keys = ResumeRepository().delete_resume(resume_id, request.user_id)
        if keys is None:
            return Response({"error": "Resume not found."}, status=404)
        s3 = S3Service()
        if keys.get("s3Key"):
            s3.delete(keys["s3Key"])
        if keys.get("customizedS3Key"):
            s3.delete(keys["customizedS3Key"])
        return Response({"success": True})


# ── Builder views ──────────────────────────────────────────────────────────────

class ResumeViewURLView(APIView):
    """Return a short-lived presigned GET URL for the original resume PDF."""

    @require_auth
    def get(self, request, resume_id):
        resume = ResumeRepository().get_resume_by_id(resume_id, request.user_id)
        if not resume:
            return Response({"error": "Resume not found."}, status=404)
        s3_key = resume.get("s3Key", "")
        if not s3_key:
            return Response({"error": "Original file not available."}, status=404)
        url = S3Service().presign_get(s3_key, expiry=600)
        return Response({"url": url})


class ResumeStructuredView(APIView):
    """
    GET  — return cached structured data (or parse on-the-fly with Gemini).
    """

    @require_auth
    def get(self, request, resume_id):
        repo = ResumeRepository()
        resume = repo.get_resume_by_id(resume_id, request.user_id)
        if not resume:
            return Response({"error": "Resume not found."}, status=404)

        cached = resume.get("structuredData")
        if cached:
            return Response(cached)

        # Parse fresh
        builder = ResumeBuilderService()
        structured = builder.structure(resume.get("resumeText", ""))
        repo.save_structured_data(resume_id, request.user_id, structured)
        return Response(structured)


class ResumeBuildView(APIView):
    """
    POST — apply ATS recommendations via Gemini + decorator chain.

    Body: { recommendations: string[], missingSkills: string[], jobDescription: string }
    """

    @require_auth
    def post(self, request, resume_id):
        repo = ResumeRepository()
        resume = repo.get_resume_by_id(resume_id, request.user_id)
        if not resume:
            return Response({"error": "Resume not found."}, status=404)

        structured = resume.get("structuredData") or ResumeBuilderService().structure(
            resume.get("resumeText", "")
        )

        context = {
            "recommendations": request.data.get("recommendations") or [],
            "missingSkills":   request.data.get("missingSkills") or [],
            "jobDescription":  request.data.get("jobDescription") or "",
        }

        enhanced = ResumeBuilderService().build_enhanced(structured, context)
        return Response(enhanced)


class ResumeExportView(APIView):
    """
    POST — render structured JSON → PDF → upload to a temporary S3 key → return presigned URL.

    Body: { data: StructuredResume }
    """

    @require_auth
    def post(self, request, resume_id):
        resume = ResumeRepository().get_resume_by_id(resume_id, request.user_id)
        if not resume:
            return Response({"error": "Resume not found."}, status=404)

        data = request.data.get("data")
        if not data:
            return Response({"error": "data is required."}, status=400)

        builder = ResumeBuilderService()
        key = builder.render_and_upload(data, folder="resumes/export")
        url = S3Service().presign_get(key, expiry=600)
        return Response({"url": url, "key": key})


class ResumeCustomizedView(APIView):
    """
    POST — save a customized resume: render PDF → upload to permanent S3 key → persist key.
    GET  — return presigned URL for the existing customized PDF.
    """

    @require_auth
    def get(self, request, resume_id):
        resume = ResumeRepository().get_resume_by_id(resume_id, request.user_id)
        if not resume:
            return Response({"error": "Resume not found."}, status=404)
        key = resume.get("customizedS3Key", "")
        if not key:
            return Response({"error": "No customized resume saved yet."}, status=404)
        url = S3Service().presign_get(key, expiry=600)
        return Response({"url": url})

    @require_auth
    def post(self, request, resume_id):
        repo = ResumeRepository()
        resume = repo.get_resume_by_id(resume_id, request.user_id)
        if not resume:
            return Response({"error": "Resume not found."}, status=404)

        data = request.data.get("data")
        if not data:
            return Response({"error": "data is required."}, status=400)

        builder = ResumeBuilderService()
        key = builder.render_and_upload(data, folder="resumes/customized")

        # Delete old customized file from S3 to avoid orphans
        old_key = resume.get("customizedS3Key", "")
        if old_key and old_key != key:
            S3Service().delete(old_key)

        repo.save_customized_key(resume_id, request.user_id, key)
        repo.save_structured_data(resume_id, request.user_id, data)

        url = S3Service().presign_get(key, expiry=600)
        return Response({"url": url, "key": key})
