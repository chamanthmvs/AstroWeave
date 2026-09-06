import json
import tempfile
import unittest
from pathlib import Path

from app import auth


class AuthTests(unittest.TestCase):
    def test_user_file_stores_hash_and_authenticates(self) -> None:
        original_users_file = auth.USERS_FILE
        with tempfile.TemporaryDirectory() as directory:
            auth.USERS_FILE = Path(directory) / "users.json"
            users: dict[str, dict[str, str]] = {}
            password = "correct horse battery staple"

            auth.create_user(users, "maya@example.com", "Maya Patel", password)

            stored = json.loads(auth.USERS_FILE.read_text(encoding="utf-8"))
            stored_record = stored["maya@example.com"]
            self.assertTrue(stored_record["password_hash"].startswith("scrypt$"))
            self.assertNotIn(password, auth.USERS_FILE.read_text(encoding="utf-8"))
            self.assertEqual(
                auth.authenticate_user(users, "maya@example.com", password),
                {"email": "maya@example.com", "name": "Maya Patel"},
            )
            self.assertIsNone(
                auth.authenticate_user(users, "maya@example.com", "wrong password")
            )
        auth.USERS_FILE = original_users_file


if __name__ == "__main__":
    unittest.main()