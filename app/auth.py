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
import base64
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    inspect,
    text,
)
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from astroweave.common.database import engine_for_path, get_engine


logger = logging.getLogger(__name__)

DB_PATH = Path(
    os.environ.get(
        "ASTROWEAVE_USERS_DB",
        str(Path(__file__).resolve().parent / "data" / "astroweave.db"),
    )
)

_metadata = MetaData()

users = Table(
    "users",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String, nullable=False, unique=True),
    Column("name", String, nullable=False),
    Column("password_hash", String, nullable=False),
    Column("birth_date", String, nullable=False),
    Column("birth_time", String, nullable=False),
    Column("birth_place", String, nullable=False),
    Column("birth_latitude", Float, nullable=False),
    Column("birth_longitude", Float, nullable=False),
    Column("utc_offset_hours", Float, nullable=False),
    Column("date_known", Integer, nullable=False, server_default=text("1")),
    Column("email_verified", Integer, nullable=False, server_default=text("0")),
    Column("created_at", String, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)


def _resolve_engine(db_path: Path | None = None, engine: Engine | None = None) -> Engine:
    """Pick the engine for auth: explicit arg, else DATABASE_URL, else DB_PATH.

    ``DB_PATH`` is consulted (not the generic shared default) so tests that patch
    ``app.auth.DB_PATH`` keep isolating the users table, while production, where
    ``DATABASE_URL`` is set, shares the one Postgres database with every other
    store (so the admin dashboard and the user table live together).
    """
    if engine is not None:
        return engine
    if db_path is not None:
        return engine_for_path(db_path)
    if os.environ.get("DATABASE_URL") or os.environ.get("ASTROWEAVE_DATABASE_URL"):
        return get_engine()
    return engine_for_path(DB_PATH)
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_DEVELOPMENT_API_SECRET = "astroweave-local-development-only"


def create_api_token(email: str, *, expires_at: int | None = None) -> str:
    """Create the backend bearer token for an authenticated local user."""

    secret = os.environ.get("ASTROWEAVE_AUTH_SECRET")
    if not secret:
        if os.environ.get("ASTROWEAVE_ENV", "development").lower() == "production":
            raise RuntimeError("ASTROWEAVE_AUTH_SECRET is required in production")
        secret = _DEVELOPMENT_API_SECRET
    encoded_email = base64.urlsafe_b64encode(email.encode("utf-8")).decode("ascii")
    expiration = expires_at or int(time.time()) + 12 * 60 * 60
    payload = f"{encoded_email}.{expiration}"
    signature = hmac.new(
        secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


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


def get_connection(
    db_path: Path | None = None,
    *,
    check_same_thread: bool = True,  # kept for API compatibility; engines handle threads
    engine: Engine | None = None,
) -> Connection:
    """Open a database connection with the users table ensured.

    Returns a SQLAlchemy ``Connection`` (usable as a context manager, like the
    old sqlite3 one) backed by SQLite locally or Postgres in production.
    """
    resolved = _resolve_engine(db_path, engine)
    init_db(resolved)
    return resolved.connect()


def init_db(engine: Engine) -> None:
    _metadata.create_all(bind=engine, checkfirst=True)
    # Legacy databases created before email_verified existed get it added.
    columns = {col["name"] for col in inspect(engine).get_columns("users")}
    if "email_verified" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
            )


def _row_to_user(row: Any) -> dict[str, Any]:
    return {
        "email": row["email"],
        "name": row["name"],
        "email_verified": bool(row["email_verified"]),
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


def get_user(connection: Connection, email: str) -> dict[str, Any] | None:
    row = connection.execute(
        text("SELECT * FROM users WHERE email = :email"), {"email": email}
    ).mappings().first()
    return _row_to_user(row) if row else None


def create_user(
    connection: Connection,
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
            text(
                """
                INSERT INTO users (
                    email, name, password_hash, birth_date, birth_time, birth_place,
                    birth_latitude, birth_longitude, utc_offset_hours, date_known
                ) VALUES (
                    :email, :name, :password_hash, :birth_date, :birth_time, :birth_place,
                    :birth_latitude, :birth_longitude, :utc_offset_hours, :date_known
                )
                """
            ),
            {
                "email": email,
                "name": name,
                "password_hash": _password_hash(password),
                "birth_date": birth_details["date"],
                "birth_time": birth_details["time"],
                "birth_place": birth_details.get("place_name", ""),
                "birth_latitude": birth_details["latitude"],
                "birth_longitude": birth_details["longitude"],
                "utc_offset_hours": birth_details["utc_offset_hours"],
                "date_known": 1 if birth_details.get("date_known", True) else 0,
            },
        )
        connection.commit()
    except IntegrityError as exc:
        connection.rollback()
        raise ValueError(f"An account with email '{email}' already exists") from exc
    logger.info("Created new user account email=%s", email)
    return get_user(connection, email)  # type: ignore[return-value]


def authenticate_user(
    connection: Connection, email: str, password: str
) -> dict[str, Any] | None:
    row = connection.execute(
        text("SELECT * FROM users WHERE email = :email"), {"email": email}
    ).mappings().first()
    if row is None or not _password_matches(password, row["password_hash"]):
        logger.warning("Authentication failed email=%s", email)
        return None
    logger.info("Authentication succeeded email=%s", email)
    return _row_to_user(row)


def get_password_hash(connection: Connection, email: str) -> str | None:
    """The stored scrypt hash for an account, used to bind/verify reset tokens."""
    value = connection.execute(
        text("SELECT password_hash FROM users WHERE email = :email"), {"email": email}
    ).scalar()
    return value if value is not None else None


def mark_email_verified(connection: Connection, email: str) -> bool:
    """Flag an account's email as verified. Returns False if no such account."""
    result = connection.execute(
        text("UPDATE users SET email_verified = 1 WHERE email = :email"),
        {"email": email},
    )
    connection.commit()
    changed = result.rowcount > 0
    logger.info("Email %s email=%s", "verified" if changed else "verify skipped (no account)", email)
    return changed


def update_password(connection: Connection, email: str, new_password: str) -> bool:
    """Set a new password hash. Returns False if the account doesn't exist."""
    result = connection.execute(
        text("UPDATE users SET password_hash = :password_hash WHERE email = :email"),
        {"password_hash": _password_hash(new_password), "email": email},
    )
    connection.commit()
    changed = result.rowcount > 0
    logger.info("Password %s email=%s", "updated" if changed else "update skipped (no account)", email)
    return changed
