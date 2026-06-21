from django.contrib.auth.hashers import check_password, make_password
from rest_framework.views import APIView
from rest_framework.response import Response

from users.service import AuthService
from users.auth import require_auth
from users.repository import UserRepository


class RegisterView(APIView):
    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")
        name = request.data.get("name", "").strip()
        if not email or not password or not name:
            return Response({"error": "Name, email and password are required."}, status=400)
        if len(password) < 8:
            return Response({"error": "Password must be at least 8 characters."}, status=400)
        try:
            result = AuthService().register(email, password, name)
            return Response(result, status=201)
        except ValueError as e:
            return Response({"error": str(e)}, status=409)


class LoginView(APIView):
    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")
        if not email or not password:
            return Response({"error": "Email and password are required."}, status=400)
        try:
            result = AuthService().login(email, password)
            return Response(result)
        except ValueError as e:
            return Response({"error": str(e)}, status=401)


class MeView(APIView):
    @require_auth
    def get(self, request):
        uses_left = UserRepository().get_uses_left(request.user_id)
        return Response({
            "id": request.user_id,
            "email": request.user_email,
            "name": request.user_name,
            "usesLeft": uses_left,
        })


class UpdateProfileView(APIView):
    @require_auth
    def patch(self, request):
        repo = UserRepository()
        user = repo.find_by_id(request.user_id)
        if not user:
            return Response({"error": "User not found."}, status=404)

        name = request.data.get("name", "").strip()
        current_password = request.data.get("currentPassword", "")
        new_password = request.data.get("newPassword", "")

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
            repo.collection.update_one({"_id": user["_id"]}, {"$set": updates})

        updated_name = updates.get("name", user.get("name", ""))
        result = AuthService()._build_token_response(request.user_id, user["email"], updated_name)
        return Response(result)
