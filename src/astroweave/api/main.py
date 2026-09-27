import hashlib
import json
import os
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from app import auth
from astroweave.agents.specialists import SPECIALIST_REGISTRY
from astroweave.common.config import get_logger
from astroweave.common.conversation import (
    ConversationAccessError,
    ConversationConflictError,
    ConversationInProgressError,
    ConversationStore,
)
from astroweave.common.security import create_user_token, verify_user_token
from astroweave.graphs.orchestrator.orchestrator_graph import build_orchestrator_graph
from astroweave.orchestration.dispatcher.dispatcher import execute_specialist

logger = get_logger(__name__)

app = FastAPI(
    title="AstroWeave API",
    description="HTTP boundary for the AstroWeave astrology system.",
    version="0.2.0",
)

_orchestrator_graph = build_orchestrator_graph()
_conversation_store = ConversationStore()


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


def _user_profile(username: str) -> dict | None:
    with auth.get_connection() as connection:
        return auth.get_user(connection, username)


@app.post("/auth/sign-in")
def sign_in(request: SignInRequest) -> dict:
    with auth.get_connection() as connection:
        user = auth.authenticate_user(connection, request.email.strip().lower(), request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return {"user": user, "token": create_user_token(user["email"])}


@app.post("/auth/register")
def register(request: RegisterRequest) -> dict:
    if len(request.password) < 8 or not request.name.strip():
        raise HTTPException(status_code=422, detail="Name and an 8-character password are required.")
    try:
        with auth.get_connection() as connection:
            user = auth.create_user(
                connection, request.email.strip().lower(), request.name.strip(),
                request.password, request.birth_details.model_dump(),
            )
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"user": user, "token": create_user_token(user["email"])}


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
    return {"user": user}


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
        "execution_trace": [],
    }
