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