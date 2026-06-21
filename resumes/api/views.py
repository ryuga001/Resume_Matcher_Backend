from rest_framework.views import APIView
from rest_framework.response import Response

from resumes.services.resume_service import ResumeService
from resumes.repositories.resume_repositories import ResumeRepository

class ResumeUploadView(APIView):

    def post(self, request):
        file = request.FILES['file']
        resume_id = ResumeService().process_resume(file)
        return Response({"resumeId": resume_id})


class ResumeListView(APIView):

    def get(self, request):
        resumes = ResumeRepository().get_all_resumes()
        return Response([
            {"resumeId": str(r["_id"]), "fileName": r.get("fileName", "Unnamed")}
            for r in resumes
        ])