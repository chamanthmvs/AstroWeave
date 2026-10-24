import unittest
import time
from unittest.mock import patch

from astroweave.common.security import (
    create_reset_token,
    create_user_token,
    create_verification_token,
    verify_reset_token,
    verify_user_token,
    verify_verification_token,
)

_HASH = "scrypt$16384$8$1$abc$deadbeef"  # a stand-in stored password hash


class SecurityTokenTests(unittest.TestCase):
    @patch.dict("os.environ", {"ASTROWEAVE_AUTH_SECRET": "test-secret"})
    def test_round_trip(self):
        token = create_user_token("user@example.com")

        self.assertEqual(verify_user_token(token), "user@example.com")

    @patch.dict("os.environ", {"ASTROWEAVE_AUTH_SECRET": "test-secret"})
    def test_rejects_tampering(self):
        token = create_user_token("user@example.com")

        self.assertIsNone(verify_user_token(token + "tampered"))

    def test_rejects_malformed_base64(self):
        self.assertIsNone(verify_user_token("%%%.123.signature"))

    @patch.dict("os.environ", {"ASTROWEAVE_AUTH_SECRET": "test-secret"})
    def test_rejects_expired_token(self):
        token = create_user_token("user@example.com", expires_at=int(time.time()) - 1)

        self.assertIsNone(verify_user_token(token))

    @patch.dict("os.environ", {"ASTROWEAVE_AUTH_SECRET": "test-secret"})
    def test_streamlit_and_backend_token_implementations_match(self):
        from app.auth import create_api_token

        expiration = int(time.time()) + 60
        token = create_api_token("user@example.com", expires_at=expiration)

        self.assertEqual(verify_user_token(token), "user@example.com")


class ResetTokenTests(unittest.TestCase):
    @patch.dict("os.environ", {"ASTROWEAVE_AUTH_SECRET": "test-secret"})
    def test_round_trip_against_current_hash(self):
        token = create_reset_token("user@example.com", _HASH)
        self.assertEqual(verify_reset_token(token, _HASH), "user@example.com")

    @patch.dict("os.environ", {"ASTROWEAVE_AUTH_SECRET": "test-secret"})
    def test_single_use_once_the_hash_changes(self):
        token = create_reset_token("user@example.com", _HASH)
        # After a reset the stored hash differs, so the token no longer verifies.
        self.assertIsNone(verify_reset_token(token, "scrypt$16384$8$1$abc$f00dface"))

    @patch.dict("os.environ", {"ASTROWEAVE_AUTH_SECRET": "test-secret"})
    def test_rejects_expiry_tampering_and_wrong_purpose(self):
        self.assertIsNone(verify_reset_token(create_reset_token("u@x.com", _HASH, expires_at=int(time.time()) - 1), _HASH))
        self.assertIsNone(verify_reset_token(create_reset_token("u@x.com", _HASH) + "x", _HASH))
        # A normal auth token must not pass as a reset token.
        self.assertIsNone(verify_reset_token(create_user_token("u@x.com"), _HASH))

    @patch.dict("os.environ", {"ASTROWEAVE_AUTH_SECRET": "test-secret"})
    def test_reset_token_is_not_a_valid_auth_token(self):
        self.assertIsNone(verify_user_token(create_reset_token("u@x.com", _HASH)))


class VerificationTokenTests(unittest.TestCase):
    @patch.dict("os.environ", {"ASTROWEAVE_AUTH_SECRET": "test-secret"})
    def test_round_trip(self):
        token = create_verification_token("user@example.com")
        self.assertEqual(verify_verification_token(token), "user@example.com")

    @patch.dict("os.environ", {"ASTROWEAVE_AUTH_SECRET": "test-secret"})
    def test_rejects_expiry_and_tampering(self):
        self.assertIsNone(verify_verification_token(create_verification_token("u@x.com", expires_at=int(time.time()) - 1)))
        self.assertIsNone(verify_verification_token(create_verification_token("u@x.com") + "x"))

    @patch.dict("os.environ", {"ASTROWEAVE_AUTH_SECRET": "test-secret"})
    def test_not_interchangeable_with_other_token_types(self):
        # A verification token must not pass as an auth or reset token, and vice versa.
        verification = create_verification_token("u@x.com")
        self.assertIsNone(verify_user_token(verification))
        self.assertIsNone(verify_reset_token(verification, _HASH))
        self.assertIsNone(verify_verification_token(create_user_token("u@x.com")))
        self.assertIsNone(verify_verification_token(create_reset_token("u@x.com", _HASH)))


if __name__ == "__main__":
    unittest.main()