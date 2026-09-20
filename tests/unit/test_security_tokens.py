import unittest
import time
from unittest.mock import patch

from astroweave.common.security import create_user_token, verify_user_token


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


if __name__ == "__main__":
    unittest.main()