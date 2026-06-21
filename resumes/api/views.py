from rest_framework.views import APIView
from rest_framework.response import Response

from resumes.services.resume_service import ResumeService

class ResumeUploadView(APIView):

    def post(self, request):
        file = request.FILES['file']
        resume_id = ResumeService().process_resume(file)

        return Response({
            "resumeId":resume_id
        })