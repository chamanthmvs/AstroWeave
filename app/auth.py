from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


logger = logging.getLogger(__name__)

USERS_FILE = Path(
    os.environ.get(
        "ASTROWEAVE_USERS_FILE",
        str(Path(__file__).resolve().parent / "data" / "users.json"),
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


def load_users() -> dict[str, dict[str, str]]:
    if not USERS_FILE.exists():
        logger.info("Users file not found at %s; starting with no users", USERS_FILE)
        return {}
    try:
        with USERS_FILE.open(encoding="utf-8") as file:
            users = json.load(file)
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to load users file at %s", USERS_FILE)
        return {}
    if not isinstance(users, dict):
        logger.warning("Users file at %s has unexpected format; ignoring contents", USERS_FILE)
        return {}
    return {
        email: record
        for email, record in users.items()
        if isinstance(email, str)
        and isinstance(record, dict)
        and isinstance(record.get("name"), str)
        and isinstance(record.get("password_hash"), str)
    }


def save_users(users: dict[str, dict[str, str]]) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=USERS_FILE.parent, delete=False
    ) as temporary_file:
        json.dump(users, temporary_file, indent=2)
        temporary_file.write("\n")
        temporary_path = Path(temporary_file.name)
    os.chmod(temporary_path, 0o600)
    os.replace(temporary_path, USERS_FILE)
    os.chmod(USERS_FILE, 0o600)


def create_user(users: dict[str, dict[str, str]], email: str, name: str, password: str) -> None:
    users[email] = {"name": name, "password_hash": _password_hash(password)}
    save_users(users)
    logger.info("Created new user account email=%s", email)


def authenticate_user(
    users: dict[str, dict[str, str]], email: str, password: str
) -> dict[str, str] | None:
    record: dict[str, Any] | None = users.get(email)
    if record is None or not _password_matches(password, record["password_hash"]):
        logger.warning("Authentication failed email=%s", email)
        return None
    logger.info("Authentication succeeded email=%s", email)
    return {"email": email, "name": record["name"]}
