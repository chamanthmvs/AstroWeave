"""SQLite-backed user registration and authentication.

Birth details (date, time, place, coordinates, UTC offset) are captured once
at registration and stored with the account. They are immutable from the
chat workspace's point of view - nothing here or in the multi-agent backend
can change them; editing birth details is intentionally a separate,
not-yet-built workflow.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

DB_PATH = Path(
    os.environ.get(
        "ASTROWEAVE_USERS_DB",
        str(Path(__file__).resolve().parent / "data" / "astroweave.db"),
    )
)
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${derived_key.hex()}"


def _password_matches(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, key_hex = encoded_hash.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        actual_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_key),
        )
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(actual_key, expected_key)


def get_connection(db_path: Path | None = None, *, check_same_thread: bool = True) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=check_same_thread)
    connection.row_factory = sqlite3.Row
    init_db(connection)
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            birth_time TEXT NOT NULL,
            birth_place TEXT NOT NULL,
            birth_latitude REAL NOT NULL,
            birth_longitude REAL NOT NULL,
            utc_offset_hours REAL NOT NULL,
            date_known INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    connection.commit()


def _row_to_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "email": row["email"],
        "name": row["name"],
        "birth_details": {
            "date": row["birth_date"],
            "time": row["birth_time"],
            "place_name": row["birth_place"],
            "latitude": row["birth_latitude"],
            "longitude": row["birth_longitude"],
            "utc_offset_hours": row["utc_offset_hours"],
            "date_known": bool(row["date_known"]),
        },
    }


def get_user(connection: sqlite3.Connection, email: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return _row_to_user(row) if row else None


def create_user(
    connection: sqlite3.Connection,
    email: str,
    name: str,
    password: str,
    birth_details: dict[str, Any],
) -> dict[str, Any]:
    """Register a new user with their birth details, captured once for good.

    Raises ValueError if the email is already registered.
    """
    try:
        connection.execute(
            """
            INSERT INTO users (
                email, name, password_hash, birth_date, birth_time, birth_place,
                birth_latitude, birth_longitude, utc_offset_hours, date_known
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email,
                name,
                _password_hash(password),
                birth_details["date"],
                birth_details["time"],
                birth_details.get("place_name", ""),
                birth_details["latitude"],
                birth_details["longitude"],
                birth_details["utc_offset_hours"],
                1 if birth_details.get("date_known", True) else 0,
            ),
        )
        connection.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"An account with email '{email}' already exists") from exc
    logger.info("Created new user account email=%s", email)
    return get_user(connection, email)  # type: ignore[return-value]


def authenticate_user(
    connection: sqlite3.Connection, email: str, password: str
) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None or not _password_matches(password, row["password_hash"]):
        logger.warning("Authentication failed email=%s", email)
        return None
    logger.info("Authentication succeeded email=%s", email)
    return _row_to_user(row)
