import tempfile
import unittest
from pathlib import Path

from app import auth


_BIRTH_DETAILS = {
    "date": "1990-01-01",
    "time": "10:00:00",
    "place_name": "Chennai, India",
    "latitude": 13.08,
    "longitude": 80.27,
    "utc_offset_hours": 5.5,
    "date_known": True,
}


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.connection = auth.get_connection(Path(self._tempdir.name) / "test.db")
        self.addCleanup(self.connection.close)

    def test_create_user_hashes_password_and_stores_birth_details(self) -> None:
        password = "correct horse battery staple"

        created = auth.create_user(
            self.connection, "maya@example.com", "Maya Patel", password, _BIRTH_DETAILS
        )

        self.assertEqual(created["email"], "maya@example.com")
        self.assertEqual(created["birth_details"], _BIRTH_DETAILS)
        row = self.connection.execute(
            "SELECT password_hash FROM users WHERE email = ?", ("maya@example.com",)
        ).fetchone()
        self.assertTrue(row["password_hash"].startswith("scrypt$"))
        self.assertNotIn(password, row["password_hash"])

    def test_authenticate_user_succeeds_and_fails_correctly(self) -> None:
        password = "correct horse battery staple"
        auth.create_user(self.connection, "maya@example.com", "Maya Patel", password, _BIRTH_DETAILS)

        authenticated = auth.authenticate_user(self.connection, "maya@example.com", password)
        self.assertEqual(authenticated["email"], "maya@example.com")
        self.assertEqual(authenticated["birth_details"], _BIRTH_DETAILS)

        self.assertIsNone(
            auth.authenticate_user(self.connection, "maya@example.com", "wrong password")
        )
        self.assertIsNone(auth.authenticate_user(self.connection, "nobody@example.com", password))

    def test_duplicate_email_raises_value_error(self) -> None:
        auth.create_user(
            self.connection, "maya@example.com", "Maya Patel", "password1234", _BIRTH_DETAILS
        )

        with self.assertRaises(ValueError):
            auth.create_user(
                self.connection, "maya@example.com", "Someone Else", "password5678", _BIRTH_DETAILS
            )


if __name__ == "__main__":
    unittest.main()