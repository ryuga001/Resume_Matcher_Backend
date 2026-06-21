from rest_framework.views import APIView
from rest_framework.response import Response

from analysis.service.analysis_service import AnalysisService

class ResumeAnalysisView(APIView):

    def post(self,request):
        resume_id = request.data.get("resumeId")
        job_description = request.data.get("jobDescription")
        result = AnalysisService().analyze(resume_id,job_description)

        return Response(result)