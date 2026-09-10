from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from astroweave.common.config import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="AstroWeave API",
    description="HTTP boundary for the AstroWeave astrology system.",
    version="0.1.0",
)


class RunRequest(BaseModel):
    query: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    methodology: str = Field(default="Let the system decide", min_length=1)


@app.get("/health")
def health() -> dict[str, str]:
    logger.debug("Health check requested")
    return {"status": "ok", "service": "astroweave-api"}


@app.post("/run", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def run(request: RunRequest) -> None:
    """Reserve the execution endpoint for the next dummy-flow branch."""

    logger.info(
        "Run requested conversation_id=%s session_id=%s username=%s methodology=%s query_length=%d",
        request.conversation_id,
        request.session_id,
        request.username,
        request.methodology,
        len(request.query),
    )
    logger.warning("Run endpoint is not implemented yet; returning 501")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="AstroWeave execution is not implemented in this branch.",
    )
