import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from app import auth
from app import geocoding
from astroweave.agents.specialists import SPECIALIST_REGISTRY
from astroweave.common.config import get_logger
from astroweave.common.conversation import (
    ConversationAccessError,
    ConversationConflictError,
    ConversationInProgressError,
    ConversationStore,
)
from astroweave.common.ratelimit import RateLimiter
from astroweave.common.email import public_web_url, send_email
from astroweave.common.security import (
    create_reset_token,
    create_user_token,
    create_verification_token,
    verify_reset_token,
    verify_user_token,
    verify_verification_token,
)
from astroweave.common.usage import UsageStore
from astroweave.common.astro import build_chart_view, build_profile, nakshatra_catalog
from astroweave.common.tools.chart_client import (
    ChartServiceUnavailable,
    get_birth_chart,
    match_charts,
)
from astroweave.graphs.orchestrator.orchestrator_graph import build_orchestrator_graph
from astroweave.orchestration.dispatcher.dispatcher import execute_specialist

logger = get_logger(__name__)

app = FastAPI(
    title="AstroWeave API",
    description="HTTP boundary for the AstroWeave astrology system.",
    version="0.2.0",
)


def _cors_origins() -> list[str]:
    """Allowed browser origins for a separately-hosted frontend (e.g. Vercel).

    The SPA served from this same origin needs no CORS; this is for the Next.js
    app deployed on another domain. Set ``ASTROWEAVE_CORS_ORIGINS`` to a
    comma-separated list in production. Defaults cover local Next.js/Vite dev.
    """
    raw = os.environ.get("ASTROWEAVE_CORS_ORIGINS", "")
    configured = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if configured:
        return configured
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


# A regex is the practical way to allow Vercel's per-deploy preview URLs
# (e.g. https://astroweave-git-branch-user.vercel.app) without listing each one.
_cors_origin_regex = os.environ.get("ASTROWEAVE_CORS_ORIGIN_REGEX") or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_orchestrator_graph = build_orchestrator_graph()
_conversation_store = ConversationStore()
_rate_limiter = RateLimiter()
_usage_store = UsageStore()


class BirthDetails(BaseModel):
    date: str = Field(..., description="Birth date as YYYY-MM-DD")
    time: str = Field(..., description="Birth time as HH:MM:SS (24-hour, local)")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    utc_offset_hours: float = Field(..., description="e.g. 5.5 for IST")
    place_name: str | None = Field(default=None)


class RunRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10_000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=128)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    username: str | None = Field(default=None, min_length=1, max_length=320)
    app_id: str | None = Field(default=None, min_length=1, max_length=128)
    message_id: str = Field(
        default_factory=lambda: str(uuid4()), min_length=1, max_length=128
    )
    methodology: str = Field(
        default="Let the system decide", min_length=1, max_length=64
    )
    birth_details: BirthDetails | None = None


class SignInRequest(BaseModel):
    email: str
    password: str


class RegistrationBirthDetails(BirthDetails):
    date_known: bool = True


class RegisterRequest(SignInRequest):
    name: str
    birth_details: RegistrationBirthDetails


class RequestResetRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


class AllowlistRequest(BaseModel):
    email: str


class AccessRequestRequest(BaseModel):
    email: str
    name: str | None = None
    note: str | None = None


_MIN_PASSWORD_LENGTH = 8


def _require_email_verification() -> bool:
    """Whether a verified email is required to use /run. Off by default, so
    signup works end-to-end before any email sender is configured."""
    return (os.environ.get("ASTROWEAVE_REQUIRE_EMAIL_VERIFICATION", "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _signup_mode() -> str:
    """'invite' (default) = only allowlisted/admin emails may register; 'open' = anyone."""
    return (os.environ.get("ASTROWEAVE_SIGNUP_MODE", "invite") or "invite").strip().lower()


def _signup_permitted(email: str) -> bool:
    """Invite-only by default: admins may always register (bootstrap), plus any
    email an admin has added to the allowlist."""
    if _signup_mode() == "open":
        return True
    if email in _admin_emails():
        return True
    with auth.get_connection() as connection:
        return auth.is_signup_allowed(connection, email)


def _allowed_email_domains() -> set[str]:
    """Domains permitted to register/request access. Default: gmail.com only.
    Set ASTROWEAVE_ALLOWED_EMAIL_DOMAINS (comma-separated) to change, or empty to allow any."""
    raw = os.environ.get("ASTROWEAVE_ALLOWED_EMAIL_DOMAINS", "gmail.com")
    return {domain.strip().lower() for domain in raw.split(",") if domain.strip()}


def _require_gmail(email: str) -> None:
    """Enforce the allowed-domain policy (Gmail-only by default)."""
    domains = _allowed_email_domains()
    if not domains:
        return
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    if domain not in domains:
        pretty = " or ".join(f"@{d}" for d in sorted(domains))
        raise HTTPException(status_code=422, detail=f"For now, only {pretty} email addresses are supported.")


def _with_admin(user: dict) -> dict:
    """Tag a user payload with whether they are an admin (drives the admin tab)."""
    return {**user, "is_admin": user.get("email", "").strip().lower() in _admin_emails()}


def _send_verification_email(email: str) -> bool:
    """Mint a verification link and send it (or log it in console mode)."""
    token = create_verification_token(email)
    link = f"{public_web_url()}/verify?token={token}"
    body = (
        "Welcome to AstroWeave.\n\n"
        "Please confirm your email address by opening this link:\n"
        f"{link}\n\n"
        "This link expires in 24 hours. If you did not create this account, ignore this email."
    )
    logger.info("Email verification requested email=%s verify_token=%s", email, token)
    return send_email(email, "Confirm your AstroWeave email", body)


def _user_profile(username: str) -> dict | None:
    with auth.get_connection() as connection:
        return auth.get_user(connection, username)


@app.post("/auth/sign-in")
def sign_in(request: SignInRequest) -> dict:
    with auth.get_connection() as connection:
        user = auth.authenticate_user(connection, request.email.strip().lower(), request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return {"user": _with_admin(user), "token": create_user_token(user["email"])}


@app.post("/auth/register")
def register(request: RegisterRequest) -> dict:
    if len(request.password) < 8 or not request.name.strip():
        raise HTTPException(status_code=422, detail="Name and an 8-character password are required.")
    email = request.email.strip().lower()
    _require_gmail(email)
    if not _signup_permitted(email):
        raise HTTPException(
            status_code=403,
            detail="Signups are by invitation only. Please ask the AstroWeave team to grant your email access.",
        )
    try:
        with auth.get_connection() as connection:
            user = auth.create_user(
                connection, email, request.name.strip(),
                request.password, request.birth_details.model_dump(),
            )
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    sent = _send_verification_email(user["email"])
    return {
        "user": _with_admin(user),
        "token": create_user_token(user["email"]),
        "email_verification": {"sent": sent, "required": _require_email_verification()},
    }


@app.post("/auth/request-access")
def request_access(request: AccessRequestRequest) -> dict:
    """A not-yet-invited person asks the admin for access (shown on the admin tab).

    Always returns the same friendly response, so it can't be used to probe which
    emails exist. Restricted to Gmail for now."""
    email = request.email.strip().lower()
    _require_gmail(email)
    with auth.get_connection() as connection:
        auth.create_access_request(
            connection, email,
            (request.name or "").strip() or None,
            (request.note or "").strip() or None,
        )
    return {
        "status": "ok",
        "message": "Thanks! Your request has been sent to the AstroWeave team. You'll be able to sign up once it's approved.",
    }


@app.post("/auth/verify")
def verify_email(request: VerifyEmailRequest) -> dict:
    """Confirm an email address from the link sent at registration."""
    email = verify_verification_token(request.token)
    if email is None:
        raise HTTPException(status_code=400, detail="This verification link is invalid or has expired.")
    with auth.get_connection() as connection:
        if not auth.mark_email_verified(connection, email):
            raise HTTPException(status_code=400, detail="This verification link is invalid or has expired.")
    return {"status": "ok", "message": "Your email is verified. Welcome to AstroWeave."}


def _issue_reset_token(email: str) -> str | None:
    """Mint a reset token for an email if the account exists (else None)."""
    with auth.get_connection() as connection:
        password_hash = auth.get_password_hash(connection, email)
    if password_hash is None:
        return None
    return create_reset_token(email, password_hash)


@app.post("/auth/request-reset")
def request_reset(request: RequestResetRequest) -> dict:
    """Start a password reset. Always returns the same response so the endpoint
    can't be used to discover which emails have accounts. With no email provider
    wired up, the token is logged for the operator / available to an admin."""
    email = request.email.strip().lower()
    token = _issue_reset_token(email)
    if token is not None:
        logger.info("Password reset requested email=%s reset_token=%s", email, token)
        link = f"{public_web_url()}/reset?token={token}"
        body = (
            "A password reset was requested for your AstroWeave account.\n\n"
            f"Reset your password here:\n{link}\n\n"
            "This link expires in 30 minutes. If you did not request this, you can ignore this email."
        )
        send_email(email, "Reset your AstroWeave password", body)
    else:
        logger.info("Password reset requested for unknown email=%s (no token issued)", email)
    return {"status": "ok", "message": "If that account exists, a password reset has been created."}


@app.post("/auth/reset")
def reset_password(request: ResetPasswordRequest) -> dict:
    if len(request.new_password) < _MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters.")
    with auth.get_connection() as connection:
        # The token encodes the email; verify it against each candidate's current hash.
        # (Decode the email from the token to look up the one account it targets.)
        email = _reset_email_from_token(connection, request.token)
        if email is None:
            raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
        auth.update_password(connection, email, request.new_password)
    return {"status": "ok", "message": "Your password has been reset. You can now sign in."}


def _reset_email_from_token(connection, token: str) -> str | None:
    """Resolve a reset token to its account by verifying against that account's hash."""
    import base64

    try:
        encoded_email = token.split(".", 2)[1]
        email = base64.urlsafe_b64decode(encoded_email.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    password_hash = auth.get_password_hash(connection, email)
    if password_hash is None:
        return None
    return verify_reset_token(token, password_hash)


def authenticated_username(
    authorization: str | None = Header(default=None),
) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    username = verify_user_token(token) if scheme.lower() == "bearer" else None
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid user token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username


@app.get("/auth/me")
def current_user(username: str = Depends(authenticated_username)) -> dict:
    user = _user_profile(username)
    if user is None:
        raise HTTPException(status_code=401, detail="Account not found.")
    return {"user": _with_admin(user)}


@app.post("/auth/request-verification")
def request_verification(username: str = Depends(authenticated_username)) -> dict:
    """Resend the verification email for the signed-in (but unverified) user."""
    user = _user_profile(username)
    if user is None:
        raise HTTPException(status_code=401, detail="Account not found.")
    if user.get("email_verified"):
        return {"status": "ok", "message": "Your email is already verified.", "sent": False}
    sent = _send_verification_email(user["email"])
    return {
        "status": "ok",
        "message": "A verification email has been sent." if sent else "A verification link has been generated.",
        "sent": sent,
    }


def _birth_for(username: str) -> dict:
    """The signed-in user's stored birth details (minus the date_known flag)."""
    profile = _user_profile(username)
    birth = (profile or {}).get("birth_details")
    if not birth:
        raise HTTPException(status_code=404, detail="No birth details on file for this account.")
    return {key: value for key, value in birth.items() if key != "date_known"}


@app.get("/me/chart")
def my_chart_summary(username: str = Depends(authenticated_username)) -> dict:
    """The signed-in user's Rasi (Moon sign), Nakshatra, and Lagna for the side panel."""
    birth = _birth_for(username)
    try:
        summary = build_chart_view(get_birth_chart(**birth), "general", "both").get("summary", {})
    except ChartServiceUnavailable as error:
        raise HTTPException(status_code=503, detail={"code": "chart_service_unavailable", "message": str(error)}) from error
    return {
        "rasi": summary.get("moon_sign"),
        "nakshatra": summary.get("janma_nakshatra"),
        "lagna": summary.get("lagna"),
        "lagna_degree": summary.get("lagna_degree"),
        "sun_sign": summary.get("sun_sign"),
    }


@app.get("/me/profile")
def my_profile(username: str = Depends(authenticated_username)) -> dict:
    """Deterministic classical profile (Nakshatra/Rasi/Lagna attributes) for the user."""
    birth = _birth_for(username)
    try:
        return build_profile(get_birth_chart(**birth))
    except ChartServiceUnavailable as error:
        raise HTTPException(status_code=503, detail={"code": "chart_service_unavailable", "message": str(error)}) from error


class MatchRequest(BaseModel):
    partner: BirthDetails
    person_is_groom: bool = True


@app.post("/match")
def kundli_match(request: MatchRequest, username: str = Depends(authenticated_username)) -> dict:
    """Kundli Milan between the signed-in user and a partner (North + South + Manglik)."""
    person = _birth_for(username)
    partner = {key: value for key, value in request.partner.model_dump().items()}
    try:
        return match_charts(person, partner, person_is_groom=request.person_is_groom)
    except ChartServiceUnavailable as error:
        raise HTTPException(status_code=503, detail={"code": "chart_service_unavailable", "message": str(error)}) from error


@app.post("/auth/change-password")
def change_password(request: ChangePasswordRequest, username: str = Depends(authenticated_username)) -> dict:
    if len(request.new_password) < _MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters.")
    with auth.get_connection() as connection:
        if auth.authenticate_user(connection, username, request.current_password) is None:
            raise HTTPException(status_code=403, detail="Current password is incorrect.")
        auth.update_password(connection, username, request.new_password)
    return {"status": "ok", "message": "Password changed."}


@app.get("/usage")
def usage(username: str = Depends(authenticated_username)) -> dict:
    """Today's run count and remaining daily quota for the signed-in user."""
    return _rate_limiter.usage_today(username)


def _admin_emails() -> set[str]:
    """Admins are operator-controlled via ASTROWEAVE_ADMIN_EMAILS (comma-separated),
    so there is no in-app way to grant admin and no default admin."""
    raw = os.environ.get("ASTROWEAVE_ADMIN_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def authenticated_admin(username: str = Depends(authenticated_username)) -> str:
    if username.strip().lower() not in _admin_emails():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return username


@app.get("/admin/summary")
def admin_summary(_admin: str = Depends(authenticated_admin)) -> dict:
    """Usage and cost analytics across all users (admin only)."""
    return _usage_store.summary()


@app.post("/admin/reset-token")
def admin_reset_token(request: RequestResetRequest, _admin: str = Depends(authenticated_admin)) -> dict:
    """Mint a reset token for a locked-out user that an admin can hand over
    (the no-email delivery path). 404 if the account doesn't exist."""
    email = request.email.strip().lower()
    token = _issue_reset_token(email)
    if token is None:
        raise HTTPException(status_code=404, detail="No account with that email.")
    return {"email": email, "reset_token": token, "expires_in_seconds": 30 * 60}


@app.get("/admin/allowlist")
def admin_list_allowlist(_admin: str = Depends(authenticated_admin)) -> dict:
    """Emails currently permitted to register (invite-only signup)."""
    with auth.get_connection() as connection:
        return {"allowed": auth.list_allowed_emails(connection), "signup_mode": _signup_mode()}


@app.post("/admin/allowlist")
def admin_add_allowlist(request: AllowlistRequest, admin: str = Depends(authenticated_admin)) -> dict:
    """Grant an email permission to register."""
    email = request.email.strip().lower()
    if not email:
        raise HTTPException(status_code=422, detail="An email is required.")
    with auth.get_connection() as connection:
        auth.add_allowed_email(connection, email, invited_by=admin)
    return {"status": "ok", "email": email}


@app.delete("/admin/allowlist/{email}")
def admin_remove_allowlist(email: str, _admin: str = Depends(authenticated_admin)) -> dict:
    """Revoke a pending invitation (does not affect already-registered users)."""
    normalized = email.strip().lower()
    with auth.get_connection() as connection:
        removed = auth.remove_allowed_email(connection, normalized)
    return {"status": "ok", "email": normalized, "removed": removed}


@app.get("/admin/access-requests")
def admin_access_requests(_admin: str = Depends(authenticated_admin)) -> dict:
    """People who have asked for access but aren't invited yet."""
    with auth.get_connection() as connection:
        return {"requests": auth.list_access_requests(connection)}


@app.post("/admin/access-requests/{email}/approve")
def admin_approve_access(email: str, admin: str = Depends(authenticated_admin)) -> dict:
    """Approve a request: add the email to the allowlist and clear the request."""
    normalized = email.strip().lower()
    with auth.get_connection() as connection:
        auth.add_allowed_email(connection, normalized, invited_by=admin)
        auth.delete_access_request(connection, normalized)
    return {"status": "ok", "email": normalized}


@app.delete("/admin/access-requests/{email}")
def admin_decline_access(email: str, _admin: str = Depends(authenticated_admin)) -> dict:
    """Decline (remove) a pending access request."""
    normalized = email.strip().lower()
    with auth.get_connection() as connection:
        removed = auth.delete_access_request(connection, normalized)
    return {"status": "ok", "email": normalized, "removed": removed}


def _request_fingerprint(request: RunRequest) -> str:
    canonical = request.model_dump(mode="json", exclude={"message_id", "username"})
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _direct_specialist(app_id: str | None) -> str | None:
    if app_id is None:
        return None
    try:
        configured = json.loads(os.environ.get("ASTROWEAVE_APP_ROUTES", "{}"))
    except ValueError as error:
        raise HTTPException(status_code=500, detail="Invalid app route configuration.") from error
    if not isinstance(configured, dict) or configured.get(app_id) not in SPECIALIST_REGISTRY:
        raise HTTPException(status_code=403, detail="App ID is not authorized for a specialist.")
    return configured[app_id]


@app.get("/health")
def health() -> dict[str, str]:
    logger.debug("Health check requested")
    return {"status": "ok", "service": "astroweave-api"}


@app.get("/nakshatras")
def nakshatras() -> dict[str, object]:
    """The 27 nakshatras with canonical attributes for the Star Atlas tab.

    Deterministic classical reference (names, symbol, deity, ruling planet,
    gana, yoni, nadi, theme, sidereal span). Public: no auth, no chart needed.
    """
    return {"nakshatras": nakshatra_catalog()}


@app.get("/geocode")
def geocode(place: str = Query(..., min_length=1, max_length=256)) -> dict[str, object]:
    """Resolve an Indian place name to coordinates for the registration form."""
    try:
        location = geocoding.geocode_indian_place(place)
    except geocoding.GeocodingServiceError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if location is None:
        raise HTTPException(
            status_code=404,
            detail="Could not find that place in India. Try a nearby city name.",
        )
    return {**location, "utc_offset_hours": geocoding.INDIA_UTC_OFFSET_HOURS}


@app.get("/conversations")
def list_conversations(
    username: str = Depends(authenticated_username),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, object]:
    return {"conversations": _conversation_store.list_conversations(username, limit)}


@app.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: str,
    username: str = Depends(authenticated_username),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, object]:
    try:
        messages = _conversation_store.load_recent_messages(
            conversation_id, username, limit
        )
    except ConversationAccessError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    return {"conversation_id": conversation_id, "messages": messages}


@app.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    username: str = Depends(authenticated_username),
) -> dict[str, object]:
    try:
        deleted = _conversation_store.delete_conversation(conversation_id, username)
    except ConversationAccessError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    return {"conversation_id": conversation_id, "deleted": deleted}


@app.post("/run")
def run(
    request: RunRequest,
    authenticated_user: str = Depends(authenticated_username),
) -> dict[str, object]:
    if request.username is not None and request.username != authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The request username does not match the authenticated user.",
        )
    profile = _user_profile(authenticated_user)
    if profile is None:
        raise HTTPException(status_code=401, detail="Account not found.")
    if _require_email_verification() and not profile.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "email_unverified", "message": "Please verify your email address before using AstroWeave."},
        )
    specialist = _direct_specialist(request.app_id)
    try:
        previous_ids = _conversation_store.request_ids(request.message_id, authenticated_user)
    except ConversationAccessError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    conversation_id = request.conversation_id or (previous_ids[0] if previous_ids else str(uuid4()))
    session_id = request.session_id or (previous_ids[1] if previous_ids else str(uuid4()))
    if previous_ids and previous_ids != (conversation_id, session_id):
        raise HTTPException(status_code=409, detail="Message ID belongs to another conversation or session.")
    logger.info(
        "Run requested conversation_id=%s session_id=%s username=%s methodology=%s query_length=%d",
        conversation_id,
        session_id,
        authenticated_user,
        request.methodology,
        len(request.query),
    )

    request_fingerprint = _request_fingerprint(request)
    try:
        request_claim_token, persisted_answer = _conversation_store.claim_request(
            conversation_id=conversation_id,
            session_id=session_id,
            owner=authenticated_user,
            message_id=request.message_id,
            request_fingerprint=request_fingerprint,
        )
    except ConversationAccessError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except ConversationConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "request_conflict", "message": str(error)},
        ) from error
    except ConversationInProgressError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "request_in_progress", "message": str(error)},
        ) from error
    if persisted_answer is not None:
        logger.info(
            "Replaying persisted response conversation_id=%s message_id=%s",
            conversation_id,
            request.message_id,
        )
        return {
            "answer": persisted_answer,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "state": {
                "answer": persisted_answer,
                "history_persisted": True,
                "history_replayed": True,
            },
            "execution_trace": [],
        }

    # Past the replay check this run will call the paid model, so it consumes a
    # daily budget slot. Over the cap, release the claim (so the same message_id
    # can be retried tomorrow) and refuse with 429.
    budget = _rate_limiter.check_and_consume(authenticated_user)
    if not budget.allowed:
        _conversation_store.release_request(request.message_id, request_claim_token)
        logger.warning(
            "Run refused by rate limit scope=%s owner=%s used=%s limit=%s",
            budget.scope, authenticated_user, budget.used, budget.limit,
        )
        message = (
            "Your daily quota is full. Each reading costs us real money to run, so "
            "questions are limited per day — please come back tomorrow."
            if budget.scope == "user"
            else "AstroWeave has reached its daily capacity. Please try again tomorrow."
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "scope": budget.scope, "limit": budget.limit, "message": message},
            headers={"Retry-After": str(budget.retry_after_seconds or 3600)},
        )

    context = {
        "conversation_id": conversation_id,
        "session_id": session_id,
        "username": authenticated_user,
        "methodology": request.methodology,
    }

    try:
        conversation_history, session_history = _conversation_store.load_context_messages(
            conversation_id=conversation_id, session_id=session_id, owner=authenticated_user,
        )
        birth_details = profile["birth_details"]
        if birth_details:
            context["birth_details"] = {key: value for key, value in birth_details.items() if key != "date_known"}
        initial_state = {"user_query": request.query, "messages": conversation_history + session_history}
        if specialist is None:
            final_state = _orchestrator_graph.invoke(initial_state, context=context)
        else:
            update = execute_specialist(
                {**initial_state, "methodology": request.methodology.lower(), "specialists": [specialist]},
                Runtime(context=context), specialist,
            )
            results = update.get("specialist_results") or []
            answer = " ".join(result.get("conclusion", "") for result in results)
            final_state = {**initial_state, **update, "answer": answer or " ".join(update.get("errors") or [])}
        final_state["history_persisted"] = _conversation_store.persist_turn(
            conversation_id=conversation_id, session_id=session_id, owner=authenticated_user,
            user_message_id=request.message_id, user_content=request.query,
            assistant_content=final_state.get("answer", ""),
            request_fingerprint=request_fingerprint, claim_token=request_claim_token,
        )
        # Record token usage/cost for this run; never let accounting fail the request.
        try:
            _usage_store.record_run(
                authenticated_user, conversation_id, request.message_id,
                final_state.get("token_usage") or [],
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to record usage for message_id=%s", request.message_id)
    except ConversationAccessError as error:
        _conversation_store.release_request(request.message_id, request_claim_token)
        logger.warning(
            "Conversation access denied conversation_id=%s username=%s",
            conversation_id,
            authenticated_user,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except ChartServiceUnavailable as error:
        _conversation_store.release_request(request.message_id, request_claim_token)
        logger.error("Chart service unavailable during run: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "chart_service_unavailable", "message": str(error)},
        ) from error
    except Exception as error:  # noqa: BLE001 - surface as a clean 502 instead of a 500 traceback
        _conversation_store.release_request(request.message_id, request_claim_token)
        logger.exception("Orchestrator run failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AstroWeave could not complete this run: {error}",
        ) from error

    return {
        "answer": final_state.get("answer", ""),
        "conversation_id": conversation_id,
        "session_id": session_id,
        "state": final_state,
        "execution_trace": _execution_trace(final_state),
    }


def _execution_trace(state: dict) -> list[dict]:
    """Summarise what the orchestrator actually did, for UI and observability.

    Derived from the final graph state: which specialists were planned, what
    each one concluded, and any errors that surfaced along the way.
    """
    trace: list[dict] = []
    specialists = state.get("specialists") or []
    if specialists:
        trace.append({
            "step": "plan",
            "methodology": state.get("methodology"),
            "specialists": specialists,
        })
    for result in state.get("specialist_results") or []:
        trace.append({
            "step": "specialist",
            "specialist": result.get("specialist"),
            "confidence": result.get("confidence"),
            "conclusion": result.get("conclusion"),
            "timing": result.get("timing") or "",
            "confidence_reason": result.get("confidence_reason") or "",
        })
    for message in state.get("errors") or []:
        trace.append({"step": "error", "message": message})
    return trace


# --- Static single-page frontend -------------------------------------------
# The SPA lives in <repo>/frontend and is served from the same origin as the
# API, so the browser needs no CORS configuration. Mounting is guarded so the
# API (and its tests) still boot when the frontend directory is absent.
_FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"
if _FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def spa_index() -> FileResponse:
        return FileResponse(_FRONTEND_DIR / "index.html")

    @app.get("/admin", include_in_schema=False)
    def admin_page() -> FileResponse:
        # The shell is public; the data it loads from /admin/summary is admin-gated.
        return FileResponse(_FRONTEND_DIR / "admin.html")
