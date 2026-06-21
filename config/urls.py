from django.urls import include, path

urlpatterns = [
    path("api/auth/", include("users.api.urls")),
    path("api/resumes/", include("resumes.api.urls")),
    path("api/analysis", include("analysis.api.urls")),
]
