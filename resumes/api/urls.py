from django.urls import path

from resumes.api.views import ResumeUploadView, ResumeListView

urlpatterns = [
    path("upload", ResumeUploadView.as_view()),
    path("list", ResumeListView.as_view()),
]
