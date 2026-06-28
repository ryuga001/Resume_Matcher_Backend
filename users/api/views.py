import os
from django.contrib.auth.hashers import check_password, make_password
from rest_framework.views import APIView
from rest_framework.response import Response

from users.service import AuthService
from users.auth import require_auth
from users.repository import UserRepository

_SECURE_COOKIES = os.getenv("COOKIE_SECURE", "false").lower() == "true"


def _set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    response.set_cookie("rm_access_token",  access_token,  max_age=15 * 60,      httponly=True, samesite="Lax", secure=_SECURE_COOKIES, path="/")
    response.set_cookie("rm_refresh_token", refresh_token, max_age=7 * 24 * 3600, httponly=True, samesite="Lax", secure=_SECURE_COOKIES, path="/")


def _clear_auth_cookies(response) -> None:
    response.delete_cookie("rm_access_token",  path="/")
    response.delete_cookie("rm_refresh_token", path="/")


class RegisterView(APIView):
    def post(self, request):
        email    = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")
        name     = request.data.get("name", "").strip()
        if not email or not password or not name:
            return Response({"error": "Name, email and password are required."}, status=400)
        if len(password) < 8:
            return Response({"error": "Password must be at least 8 characters."}, status=400)
        try:
            result = AuthService().register(email, password, name)
            response = Response({"user": result["user"]}, status=201)
            _set_auth_cookies(response, result["access_token"], result["refresh_token"])
            return response
        except ValueError as exc:
            return Response({"error": str(exc)}, status=409)


class LoginView(APIView):
    def post(self, request):
        email    = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")
        if not email or not password:
            return Response({"error": "Email and password are required."}, status=400)
        try:
            result = AuthService().login(email, password)
            response = Response({"user": result["user"]})
            _set_auth_cookies(response, result["access_token"], result["refresh_token"])
            return response
        except ValueError as exc:
            return Response({"error": str(exc)}, status=401)


class LogoutView(APIView):
    def post(self, request):
        response = Response({"ok": True})
        _clear_auth_cookies(response)
        return response


class RefreshView(APIView):
    def post(self, request):
        refresh_token = request.COOKIES.get("rm_refresh_token")
        if not refresh_token:
            return Response({"error": "Refresh token missing."}, status=401)
        try:
            payload = AuthService().verify_token(refresh_token, "refresh")
        except Exception:
            return Response({"error": "Invalid or expired refresh token."}, status=401)

        user = UserRepository().find_by_id(payload["sub"])
        if not user:
            return Response({"error": "User not found."}, status=401)

        svc        = AuthService()
        user_id    = user["id"]
        new_access = svc.create_access_token(user_id, user["email"], user["name"], user["role"])

        response = Response({"user": {"id": user_id, "email": user["email"], "name": user["name"], "role": user["role"]}})
        response.set_cookie("rm_access_token", new_access, max_age=15 * 60, httponly=True, samesite="Lax", secure=_SECURE_COOKIES, path="/")
        return response


class MeView(APIView):
    @require_auth
    def get(self, request):
        uses_left = UserRepository().get_uses_left(request.user_id)
        return Response({
            "id":       request.user_id,
            "email":    request.user_email,
            "name":     request.user_name,
            "role":     request.user_role,
            "usesLeft": uses_left,
        })


class UpdateProfileView(APIView):
    @require_auth
    def patch(self, request):
        repo = UserRepository()
        user = repo.find_by_id(request.user_id)
        if not user:
            return Response({"error": "User not found."}, status=404)

        name             = request.data.get("name", "").strip()
        current_password = request.data.get("currentPassword", "")
        new_password     = request.data.get("newPassword", "")

        updates = {}
        if name and name != user.get("name"):
            updates["name"] = name

        if new_password:
            if len(new_password) < 8:
                return Response({"error": "New password must be at least 8 characters."}, status=400)
            if not current_password or not check_password(current_password, user["password"]):
                return Response({"error": "Current password is incorrect."}, status=400)
            updates["password"] = make_password(new_password)

        if updates:
            repo.update_user(request.user_id, **updates)

        updated_name = updates.get("name", user.get("name", ""))
        role         = user.get("role", "USER")
        svc          = AuthService()
        new_access   = svc.create_access_token(request.user_id, user["email"], updated_name, role)
        new_refresh  = svc.create_refresh_token(request.user_id)

        response = Response({"user": {"id": request.user_id, "email": user["email"], "name": updated_name, "role": role}})
        _set_auth_cookies(response, new_access, new_refresh)
        return response
