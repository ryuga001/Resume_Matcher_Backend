from django.urls import path
from analysis.api.views import ResumeAnalysisView, AnalysisHistoryView, AnalysisDetailView

urlpatterns = [
    path("", ResumeAnalysisView.as_view()),
    path("/history", AnalysisHistoryView.as_view()),
    path("/<str:analysis_id>", AnalysisDetailView.as_view()),
]
