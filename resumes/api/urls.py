from django.urls import path

from resumes.api.views import ResumeUploadView

urlpatterns = [
    path("upload",ResumeUploadView.as_view())
]
