import os
import jwt
from datetime import datetime, timedelta, timezone
from django.contrib.auth.hashers import make_password, check_password

from users.repository import UserRepository

SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
EXPIRY_HOURS = 24 * 7  # 7 days


class AuthService:
    def __init__(self):
        self.repo = UserRepository()

    def register(self, email: str, password: str, name: str) -> dict:
        existing = self.repo.find_by_email(email)
        if existing:
            raise ValueError("An account with this email already exists.")
        hashed = make_password(password)
        user_id = self.repo.create_user(email, hashed, name)
        return self._build_token_response(user_id, email, name)

    def login(self, email: str, password: str) -> dict:
        user = self.repo.find_by_email(email)
        if not user or not check_password(password, user["password"]):
            raise ValueError("Invalid email or password.")
        return self._build_token_response(str(user["_id"]), email, user.get("name", ""))

    def verify_token(self, token: str) -> dict:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return payload

    def _build_token_response(self, user_id: str, email: str, name: str) -> dict:
        payload = {
            "sub": user_id,
            "email": email,
            "name": name,
            "exp": datetime.now(timezone.utc) + timedelta(hours=EXPIRY_HOURS),
        }
        token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)
        return {
            "token": token,
            "user": {"id": user_id, "email": email, "name": name},
        }
