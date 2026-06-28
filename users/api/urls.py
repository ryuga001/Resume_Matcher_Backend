from django.urls import path
from users.api.views import RegisterView, LoginView, LogoutView, RefreshView, MeView, UpdateProfileView

urlpatterns = [
    path("register", RegisterView.as_view()),
    path("login", LoginView.as_view()),
    path("logout", LogoutView.as_view()),
    path("refresh", RefreshView.as_view()),
    path("me", MeView.as_view()),
    path("profile", UpdateProfileView.as_view()),
]
