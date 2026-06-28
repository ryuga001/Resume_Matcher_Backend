from django.urls import path
from courses.api.views import (
    PresignView,
    CourseListView,
    CourseDetailView,
    SubtopicsGenerateView,
    SubtopicsTaskStatusView,
    SubtopicsView,
    ContentGenerateView,
    ContentStatusView,
    SubtopicContentView,
)

urlpatterns = [
    path("/presign",                                              PresignView.as_view()),
    path("/<str:course_id>/subtopics/generate",                   SubtopicsGenerateView.as_view()),
    path("/<str:course_id>/subtopics/status/<str:task_id>",       SubtopicsTaskStatusView.as_view()),
    path("/<str:course_id>/subtopics",                            SubtopicsView.as_view()),
    path("/<str:course_id>/content/generate",                     ContentGenerateView.as_view()),
    path("/<str:course_id>/content/status",                       ContentStatusView.as_view()),
    path("/<str:course_id>/content/<int:order>",                  SubtopicContentView.as_view()),
    path("/<str:course_id>",                                      CourseDetailView.as_view()),
    path("",                                                      CourseListView.as_view()),
]
