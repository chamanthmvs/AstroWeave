from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from astroweave.common.config import get_logger
from astroweave.graphs.orchestrator.orchestrator_graph import build_orchestrator_graph

logger = get_logger(__name__)

app = FastAPI(
    title="AstroWeave API",
    description="HTTP boundary for the AstroWeave astrology system.",
    version="0.1.0",
)

_orchestrator_graph = build_orchestrator_graph()


class BirthDetails(BaseModel):
    date: str = Field(..., description="Birth date as YYYY-MM-DD")
    time: str = Field(..., description="Birth time as HH:MM:SS (24-hour, local)")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    utc_offset_hours: float = Field(..., description="e.g. 5.5 for IST")
    place_name: str | None = Field(default=None)


class RunRequest(BaseModel):
    query: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    methodology: str = Field(default="Let the system decide", min_length=1)
    birth_details: BirthDetails | None = None


@app.get("/health")
def health() -> dict[str, str]:
    logger.debug("Health check requested")
    return {"status": "ok", "service": "astroweave-api"}


@app.post("/run")
def run(request: RunRequest) -> dict[str, object]:
    logger.info(
        "Run requested conversation_id=%s session_id=%s username=%s methodology=%s query_length=%d",
        request.conversation_id,
        request.session_id,
        request.username,
        request.methodology,
        len(request.query),
    )

    context = {
        "conversation_id": request.conversation_id,
        "session_id": request.session_id,
        "username": request.username,
        "methodology": request.methodology,
        "birth_details": request.birth_details.model_dump() if request.birth_details else None,
    }

    try:
        final_state = _orchestrator_graph.invoke({"user_query": request.query}, context=context)
    except Exception as error:  # noqa: BLE001 - surface as a clean 502 instead of a 500 traceback
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
