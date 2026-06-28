from functools import wraps
from rest_framework.response import Response
from users.service import AuthService


def _extract_token(request) -> str | None:
    token = request.COOKIES.get("rm_access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return token or None


def require_auth(view_func):
    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        token = _extract_token(request)
        if not token:
            return Response({"error": "Authentication required."}, status=401)
        try:
            payload = AuthService().verify_token(token, "access")
            request.user_id = payload["sub"]
            request.user_email = payload["email"]
            request.user_name = payload.get("name", "")
            request.user_role = payload.get("role", "USER")
        except Exception:
            return Response({"error": "Invalid or expired token."}, status=401)
        return view_func(self, request, *args, **kwargs)
    return wrapper


def require_role(*roles):
    """Decorator that enforces both authentication and one of the given roles."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            token = _extract_token(request)
            if not token:
                return Response({"error": "Authentication required."}, status=401)
            try:
                payload = AuthService().verify_token(token, "access")
                request.user_id = payload["sub"]
                request.user_email = payload["email"]
                request.user_name = payload.get("name", "")
                request.user_role = payload.get("role", "USER")
            except Exception:
                return Response({"error": "Invalid or expired token."}, status=401)
            if request.user_role not in roles:
                return Response({"error": "Forbidden."}, status=403)
            return view_func(self, request, *args, **kwargs)
        return wrapper
    return decorator
