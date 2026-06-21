from django.urls import path
from users.api.views import RegisterView, LoginView, MeView, UpdateProfileView

urlpatterns = [
    path("register", RegisterView.as_view()),
    path("login", LoginView.as_view()),
    path("me", MeView.as_view()),
    path("profile", UpdateProfileView.as_view()),
]
