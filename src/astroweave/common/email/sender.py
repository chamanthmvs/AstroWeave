"""Pluggable, zero-cost-by-default email sending.

Email verification and password reset need a way to deliver a link. Standing up
a paid email service is explicitly out of scope, and we never want signup or
reset to *depend* on an email provider being configured. So this module has two
backends chosen by ``ASTROWEAVE_EMAIL_BACKEND``:

* ``console`` (the default): the message is logged, not sent. The verification /
  reset link is therefore always available to the operator (and, for reset, to
  an admin via ``/admin/reset-token``). Nothing is blocked; nothing costs money.
* ``smtp``: a real email is sent over SMTP. A free Gmail account with an "app
  password" works — set ``ASTROWEAVE_SMTP_HOST=smtp.gmail.com`` (port 587),
  ``ASTROWEAVE_SMTP_USER`` / ``ASTROWEAVE_SMTP_PASSWORD`` and
  ``ASTROWEAVE_EMAIL_FROM``. No code change is needed to turn it on.

``send_email`` returns whether a real message was dispatched, so callers can
tell the user "check your email" only when that is actually true.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

from astroweave.common.config import get_logger

logger = get_logger(__name__)


def email_backend() -> str:
    return (os.environ.get("ASTROWEAVE_EMAIL_BACKEND") or "console").strip().lower()


def smtp_configured() -> bool:
    """True when the SMTP backend is selected and a host is set."""
    return email_backend() == "smtp" and bool(os.environ.get("ASTROWEAVE_SMTP_HOST"))


def public_web_url() -> str:
    """Base URL of the user-facing web app, used to build links in emails."""
    return (os.environ.get("ASTROWEAVE_PUBLIC_WEB_URL") or "http://localhost:3000").rstrip("/")


def _send_smtp(to: str, subject: str, body: str) -> bool:
    host = os.environ["ASTROWEAVE_SMTP_HOST"]
    port = int(os.environ.get("ASTROWEAVE_SMTP_PORT", "587"))
    user = os.environ.get("ASTROWEAVE_SMTP_USER")
    password = os.environ.get("ASTROWEAVE_SMTP_PASSWORD")
    sender = os.environ.get("ASTROWEAVE_EMAIL_FROM") or user or "no-reply@astroweave.local"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to
    message.set_content(body)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as server:
                if user and password:
                    server.login(user, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.starttls(context=ssl.create_default_context())
                if user and password:
                    server.login(user, password)
                server.send_message(message)
    except Exception:  # noqa: BLE001 - never let a mail failure break the request
        logger.exception("SMTP send failed to=%s subject=%s", to, subject)
        return False
    logger.info("Email sent to=%s subject=%s", to, subject)
    return True


def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email, or log it in console mode. Returns True iff really sent."""
    if smtp_configured():
        return _send_smtp(to, subject, body)
    logger.info("[email:console] to=%s subject=%s\n%s", to, subject, body)
    return False
