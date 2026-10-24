from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import time

from astroweave.common.config import get_logger

logger = get_logger(__name__)

_DEVELOPMENT_SECRET = "astroweave-local-development-only"
_TOKEN_LIFETIME_SECONDS = 12 * 60 * 60
_RESET_TOKEN_LIFETIME_SECONDS = 30 * 60
_VERIFICATION_TOKEN_LIFETIME_SECONDS = 24 * 60 * 60


def _secret() -> bytes:
    value = os.environ.get("ASTROWEAVE_AUTH_SECRET")
    if value:
        return value.encode("utf-8")
    if os.environ.get("ASTROWEAVE_ENV", "development").lower() == "production":
        raise RuntimeError("ASTROWEAVE_AUTH_SECRET is required in production")
    logger.warning(
        "ASTROWEAVE_AUTH_SECRET is unset; using an insecure development-only secret"
    )
    return _DEVELOPMENT_SECRET.encode("utf-8")


def create_user_token(username: str, *, expires_at: int | None = None) -> str:
    encoded_username = base64.urlsafe_b64encode(username.encode("utf-8")).decode("ascii")
    expiration = expires_at or int(time.time()) + _TOKEN_LIFETIME_SECONDS
    payload = f"{encoded_username}.{expiration}"
    signature = hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256)
    return f"{payload}.{signature.hexdigest()}"


def verify_user_token(token: str) -> str | None:
    try:
        encoded_username, expiration_raw, supplied_signature = token.split(".", 2)
        payload = f"{encoded_username}.{expiration_raw}"
        expected_signature = hmac.new(
            _secret(), payload.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        if int(expiration_raw) < int(time.time()):
            return None
        return base64.urlsafe_b64decode(encoded_username.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def _password_binding(password_hash: str) -> str:
    """Short digest of the current password hash, folded into a reset token.

    Because it changes the moment the password is reset, a used reset token
    stops verifying - that makes reset tokens single-use and invalidates any
    outstanding ones whenever the password changes, with no DB column."""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def create_reset_token(email: str, password_hash: str, *, expires_at: int | None = None) -> str:
    """Mint a short-lived, single-use password-reset token bound to the current hash."""
    encoded_email = base64.urlsafe_b64encode(email.encode("utf-8")).decode("ascii")
    expiration = expires_at or int(time.time()) + _RESET_TOKEN_LIFETIME_SECONDS
    payload = f"reset.{encoded_email}.{_password_binding(password_hash)}.{expiration}"
    signature = hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_reset_token(token: str, password_hash: str) -> str | None:
    """Return the email if the reset token is valid for the current hash, else None."""
    try:
        purpose, encoded_email, binding, expiration_raw, supplied_signature = token.split(".", 4)
        if purpose != "reset":
            return None
        payload = f"{purpose}.{encoded_email}.{binding}.{expiration_raw}"
        expected_signature = hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        if int(expiration_raw) < int(time.time()):
            return None
        if not hmac.compare_digest(binding, _password_binding(password_hash)):
            return None  # password already changed -> token spent
        return base64.urlsafe_b64decode(encoded_email.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def create_verification_token(email: str, *, expires_at: int | None = None) -> str:
    """Mint an email-ownership verification token (stateless HMAC, 24h default).

    Verifying is idempotent (it just flips a flag), so this need not be bound to
    the password or marked single-use the way a reset token is.
    """
    encoded_email = base64.urlsafe_b64encode(email.encode("utf-8")).decode("ascii")
    expiration = expires_at or int(time.time()) + _VERIFICATION_TOKEN_LIFETIME_SECONDS
    payload = f"verify.{encoded_email}.{expiration}"
    signature = hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_verification_token(token: str) -> str | None:
    """Return the email if the verification token is valid and unexpired, else None."""
    try:
        purpose, encoded_email, expiration_raw, supplied_signature = token.split(".", 3)
        if purpose != "verify":
            return None
        payload = f"{purpose}.{encoded_email}.{expiration_raw}"
        expected_signature = hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        if int(expiration_raw) < int(time.time()):
            return None
        return base64.urlsafe_b64decode(encoded_email.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None