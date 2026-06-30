"""Unit tests — AuthService (UserRepository + JWT + hashers fully mocked)."""

import unittest
from unittest.mock import MagicMock, patch
import os


os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")


FAKE_USER = {
    "_id": 1,
    "email": "alice@example.com",
    "password": "hashed_password",
    "name": "Alice",
    "role": "USER",
}


class TestAuthServiceRegister(unittest.TestCase):

    def test_register_raises_if_email_already_exists(self):
        with (
            patch("users.service.UserRepository") as MockRepo,
            patch("users.service.make_password", return_value="hashed"),
        ):
            MockRepo.return_value.find_by_email.return_value = FAKE_USER
            from users.service import AuthService
            svc = AuthService()
            with self.assertRaises(ValueError):
                svc.register("alice@example.com", "pass123", "Alice")

    def test_register_creates_user_when_email_is_new(self):
        with (
            patch("users.service.UserRepository") as MockRepo,
            patch("users.service.make_password", return_value="hashed_pw"),
        ):
            MockRepo.return_value.find_by_email.return_value = None
            MockRepo.return_value.create_user.return_value = "new_user_id"
            from users.service import AuthService
            svc = AuthService()
            result = svc.register("bob@example.com", "secret", "Bob")
            MockRepo.return_value.create_user.assert_called_once_with(
                "bob@example.com", "hashed_pw", "Bob", role="USER"
            )

    def test_register_hashes_password_before_storing(self):
        with (
            patch("users.service.UserRepository") as MockRepo,
            patch("users.service.make_password", return_value="hashed_pw") as MockHash,
        ):
            MockRepo.return_value.find_by_email.return_value = None
            MockRepo.return_value.create_user.return_value = "1"
            from users.service import AuthService
            svc = AuthService()
            svc.register("x@x.com", "plaintext", "X")
            MockHash.assert_called_once_with("plaintext")

    def test_register_returns_access_token_and_refresh_token(self):
        with (
            patch("users.service.UserRepository") as MockRepo,
            patch("users.service.make_password", return_value="hashed"),
        ):
            MockRepo.return_value.find_by_email.return_value = None
            MockRepo.return_value.create_user.return_value = "5"
            from users.service import AuthService
            svc = AuthService()
            result = svc.register("new@example.com", "pass", "New User")
            self.assertIn("access_token", result)
            self.assertIn("refresh_token", result)
            self.assertIn("user", result)

    def test_register_user_dict_contains_email_and_name(self):
        with (
            patch("users.service.UserRepository") as MockRepo,
            patch("users.service.make_password", return_value="hashed"),
        ):
            MockRepo.return_value.find_by_email.return_value = None
            MockRepo.return_value.create_user.return_value = "5"
            from users.service import AuthService
            svc = AuthService()
            result = svc.register("carol@example.com", "pass", "Carol")
            self.assertEqual(result["user"]["email"], "carol@example.com")
            self.assertEqual(result["user"]["name"], "Carol")


class TestAuthServiceLogin(unittest.TestCase):

    def test_login_raises_for_unknown_email(self):
        with patch("users.service.UserRepository") as MockRepo:
            MockRepo.return_value.find_by_email.return_value = None
            from users.service import AuthService
            svc = AuthService()
            with self.assertRaises(ValueError):
                svc.login("ghost@example.com", "pass")

    def test_login_raises_for_wrong_password(self):
        with (
            patch("users.service.UserRepository") as MockRepo,
            patch("users.service.check_password", return_value=False),
        ):
            MockRepo.return_value.find_by_email.return_value = FAKE_USER
            from users.service import AuthService
            svc = AuthService()
            with self.assertRaises(ValueError):
                svc.login("alice@example.com", "wrong_password")

    def test_login_returns_tokens_on_correct_credentials(self):
        with (
            patch("users.service.UserRepository") as MockRepo,
            patch("users.service.check_password", return_value=True),
        ):
            MockRepo.return_value.find_by_email.return_value = FAKE_USER
            from users.service import AuthService
            svc = AuthService()
            result = svc.login("alice@example.com", "correct_pass")
            self.assertIn("access_token", result)
            self.assertIn("refresh_token", result)

    def test_login_calls_check_password_with_hashed(self):
        with (
            patch("users.service.UserRepository") as MockRepo,
            patch("users.service.check_password", return_value=True) as MockCheck,
        ):
            MockRepo.return_value.find_by_email.return_value = FAKE_USER
            from users.service import AuthService
            svc = AuthService()
            svc.login("alice@example.com", "plaintext")
            MockCheck.assert_called_once_with("plaintext", "hashed_password")

    def test_login_user_dict_contains_correct_email(self):
        with (
            patch("users.service.UserRepository") as MockRepo,
            patch("users.service.check_password", return_value=True),
        ):
            MockRepo.return_value.find_by_email.return_value = FAKE_USER
            from users.service import AuthService
            svc = AuthService()
            result = svc.login("alice@example.com", "pass")
            self.assertEqual(result["user"]["email"], "alice@example.com")


class TestAuthServiceTokens(unittest.TestCase):

    def _service(self):
        with patch("users.service.UserRepository"):
            from users.service import AuthService
            return AuthService()

    def test_create_access_token_returns_string(self):
        svc = self._service()
        token = svc.create_access_token("1", "a@b.com", "Alice", "USER")
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 20)

    def test_create_refresh_token_returns_string(self):
        svc = self._service()
        token = svc.create_refresh_token("1")
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 20)

    def test_verify_access_token_returns_payload(self):
        svc = self._service()
        token = svc.create_access_token("42", "user@x.com", "User", "USER")
        payload = svc.verify_token(token, token_type="access")
        self.assertEqual(payload["sub"], "42")
        self.assertEqual(payload["email"], "user@x.com")

    def test_verify_token_raises_for_wrong_type(self):
        svc = self._service()
        # Create an access token but verify as refresh → should raise
        access_token = svc.create_access_token("1", "a@b.com", "A", "USER")
        with self.assertRaises(ValueError):
            svc.verify_token(access_token, token_type="refresh")

    def test_verify_token_raises_for_invalid_token(self):
        import jwt
        svc = self._service()
        with self.assertRaises(Exception):
            svc.verify_token("this.is.not.a.valid.jwt", token_type="access")

    def test_access_token_contains_name_and_role(self):
        svc = self._service()
        token = svc.create_access_token("7", "u@u.com", "Bob", "ADMIN")
        payload = svc.verify_token(token, token_type="access")
        self.assertEqual(payload["name"], "Bob")
        self.assertEqual(payload["role"], "ADMIN")

    def test_refresh_token_type_field_is_refresh(self):
        svc = self._service()
        token = svc.create_refresh_token("99")
        payload = svc.verify_token(token, token_type="refresh")
        self.assertEqual(payload["type"], "refresh")
        self.assertEqual(payload["sub"], "99")

    def test_access_token_has_exp_claim(self):
        svc = self._service()
        token = svc.create_access_token("1", "a@b.com", "A", "USER")
        payload = svc.verify_token(token)
        self.assertIn("exp", payload)


if __name__ == "__main__":
    unittest.main()
