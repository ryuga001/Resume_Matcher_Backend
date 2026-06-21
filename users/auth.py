from functools import wraps
from rest_framework.response import Response
from users.service import AuthService


def require_auth(view_func):
    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return Response({"error": "Authentication required."}, status=401)
        token = auth_header[7:]
        try:
            payload = AuthService().verify_token(token)
            request.user_id = payload["sub"]
            request.user_email = payload["email"]
            request.user_name = payload.get("name", "")
        except Exception:
            return Response({"error": "Invalid or expired token."}, status=401)
        return view_func(self, request, *args, **kwargs)
    return wrapper
