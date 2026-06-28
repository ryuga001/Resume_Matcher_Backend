from __future__ import annotations

from django.db import transaction

from users.models import User

ROLES = ("SUPER_ADMIN", "USER")


class UserRepository:
    """Data-access layer for User. Returns plain dicts — no ORM objects leak out."""

    def create_user(self, email: str, hashed_password: str, name: str, role: str = "USER") -> str:
        if role not in ROLES:
            raise ValueError(f"Invalid role: {role}")
        user = User.objects.create(email=email, password=hashed_password, name=name, role=role)
        return str(user.id)

    def update_user(self, user_id: str, **fields) -> None:
        User.objects.filter(id=int(user_id)).update(**fields)

    def find_by_email(self, email: str) -> dict | None:
        try:
            return self._serialize(User.objects.get(email=email))
        except User.DoesNotExist:
            return None

    def find_by_id(self, user_id: str) -> dict | None:
        try:
            return self._serialize(User.objects.get(id=int(user_id)))
        except (User.DoesNotExist, ValueError, TypeError):
            return None

    def get_uses_left(self, user_id: str) -> int:
        try:
            return User.objects.values_list("uses_left", flat=True).get(id=int(user_id))
        except (User.DoesNotExist, ValueError, TypeError):
            return 0

    def decrement_uses(self, user_id: str) -> int:
        with transaction.atomic():
            user = (
                User.objects
                .select_for_update()
                .filter(id=int(user_id), uses_left__gt=0)
                .first()
            )
            if not user:
                return 0
            user.uses_left -= 1
            user.save(update_fields=["uses_left"])
            return user.uses_left

    @staticmethod
    def _serialize(user: User) -> dict:
        return {
            "_id":      str(user.id),   # legacy key kept for AuthService compat
            "id":       str(user.id),
            "email":    user.email,
            "password": user.password,
            "name":     user.name,
            "role":     user.role,
            "usesLeft": user.uses_left,
        }
