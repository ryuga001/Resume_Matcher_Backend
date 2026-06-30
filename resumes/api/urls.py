from django.urls import path
from resumes.api.views import (
    ResumeUploadView,
    ResumeListView,
    ResumeDeleteView,
    ResumeViewURLView,
    ResumeStructuredView,
    ResumeBuildView,
    ResumeExportView,
    ResumeCustomizedView,
)

urlpatterns = [
    path("upload", ResumeUploadView.as_view()),
    path("list", ResumeListView.as_view()),
    # builder endpoints — must come before the catch-all delete route
    path("<str:resume_id>/view", ResumeViewURLView.as_view()),
    path("<str:resume_id>/structured", ResumeStructuredView.as_view()),
    path("<str:resume_id>/build", ResumeBuildView.as_view()),
    path("<str:resume_id>/export", ResumeExportView.as_view()),
    path("<str:resume_id>/customized", ResumeCustomizedView.as_view()),
    # catch-all DELETE
    path("<str:resume_id>", ResumeDeleteView.as_view()),
]
