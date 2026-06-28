from django.urls import path
from courses.api.views import PresignView, CourseListView, CourseDetailView

urlpatterns = [
    path("/presign", PresignView.as_view()),
    path("", CourseListView.as_view()),
    path("/<str:course_id>", CourseDetailView.as_view()),
]
