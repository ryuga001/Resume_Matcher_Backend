from django.urls import path

from analysis.api.views import ResumeAnalysisView

urlpatterns = [
    path("",ResumeAnalysisView.as_view())
]