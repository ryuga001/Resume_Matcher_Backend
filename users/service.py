import os
import jwt
from datetime import datetime, timedelta, timezone
from django.contrib.auth.hashers import make_password, check_password

from users.repository import UserRepository

SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
ACCESS_EXPIRY_MINUTES = 15
REFRESH_EXPIRY_DAYS = 7


class AuthService:
    def __init__(self):
        self.repo = UserRepository()

    def register(self, email: str, password: str, name: str) -> dict:
        existing = self.repo.find_by_email(email)
        if existing:
            raise ValueError("An account with this email already exists.")
        hashed = make_password(password)
        user_id = self.repo.create_user(email, hashed, name, role="USER")
        return self._build_tokens(user_id, email, name, "USER")

    def login(self, email: str, password: str) -> dict:
        user = self.repo.find_by_email(email)
        if not user or not check_password(password, user["password"]):
            raise ValueError("Invalid email or password.")
        role = user.get("role", "USER")
        return self._build_tokens(str(user["_id"]), email, user.get("name", ""), role)

    def create_access_token(self, user_id: str, email: str, name: str, role: str) -> str:
        payload = {
            "sub": user_id,
            "email": email,
            "name": name,
            "role": role,
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_EXPIRY_MINUTES),
        }
        return jwt.encode(payload, SECRET, algorithm=ALGORITHM)

    def create_refresh_token(self, user_id: str) -> str:
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRY_DAYS),
        }
        return jwt.encode(payload, SECRET, algorithm=ALGORITHM)

    def verify_token(self, token: str, token_type: str = "access") -> dict:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            raise ValueError("Invalid token type.")
        return payload

    def _build_tokens(self, user_id: str, email: str, name: str, role: str) -> dict:
        return {
            "access_token": self.create_access_token(user_id, email, name, role),
            "refresh_token": self.create_refresh_token(user_id),
            "user": {"id": user_id, "email": email, "name": name, "role": role},
        }
