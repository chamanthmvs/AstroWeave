from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field


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
    return {"status": "ok", "service": "astroweave-api"}


@app.post("/run", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def run(request: RunRequest) -> None:
    """Reserve the execution endpoint for the next dummy-flow branch."""

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="AstroWeave execution is not implemented in this branch.",
    )
