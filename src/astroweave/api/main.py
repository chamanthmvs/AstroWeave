import hashlib
import json
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from astroweave.common.config import get_logger
from astroweave.common.conversation import (
    ConversationAccessError,
    ConversationConflictError,
    ConversationInProgressError,
    ConversationStore,
)
from astroweave.common.security import verify_user_token
from astroweave.graphs.orchestrator.orchestrator_graph import build_orchestrator_graph

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
    conversation_id: str = Field(..., min_length=1, max_length=128)
    session_id: str = Field(..., min_length=1, max_length=128)
    username: str = Field(..., min_length=1, max_length=320)
    message_id: str = Field(
        default_factory=lambda: str(uuid4()), min_length=1, max_length=128
    )
    methodology: str = Field(
        default="Let the system decide", min_length=1, max_length=64
    )
    birth_details: BirthDetails | None = None


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


def _request_fingerprint(request: RunRequest) -> str:
    canonical = request.model_dump(mode="json", exclude={"message_id", "username"})
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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
    if request.username != authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The request username does not match the authenticated user.",
        )
    logger.info(
        "Run requested conversation_id=%s session_id=%s username=%s methodology=%s query_length=%d",
        request.conversation_id,
        request.session_id,
        request.username,
        request.methodology,
        len(request.query),
    )

    request_fingerprint = _request_fingerprint(request)
    try:
        request_claim_token, persisted_answer = _conversation_store.claim_request(
            conversation_id=request.conversation_id,
            session_id=request.session_id,
            owner=request.username,
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
            request.conversation_id,
            request.message_id,
        )
        return {
            "answer": persisted_answer,
            "state": {
                "answer": persisted_answer,
                "history_persisted": True,
                "history_replayed": True,
            },
            "execution_trace": [],
        }

    context = {
        "conversation_id": request.conversation_id,
        "session_id": request.session_id,
        "username": request.username,
        "message_id": request.message_id,
        "methodology": request.methodology,
        "birth_details": request.birth_details.model_dump() if request.birth_details else None,
        "conversation_store": _conversation_store,
        "request_fingerprint": request_fingerprint,
        "request_claim_token": request_claim_token,
    }

    try:
        final_state = _orchestrator_graph.invoke({"user_query": request.query}, context=context)
    except ConversationAccessError as error:
        _conversation_store.release_request(request.message_id, request_claim_token)
        logger.warning(
            "Conversation access denied conversation_id=%s username=%s",
            request.conversation_id,
            request.username,
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
        "state": final_state,
        "execution_trace": [],
    }
