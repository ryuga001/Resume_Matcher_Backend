from django.urls import path
from resumes.api.views import ResumeUploadView, ResumeListView, ResumeDeleteView

urlpatterns = [
    path("upload", ResumeUploadView.as_view()),
    path("list", ResumeListView.as_view()),
    path("<str:resume_id>", ResumeDeleteView.as_view()),
]
