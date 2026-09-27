from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from astroweave.agents.specialists import SPECIALIST_REGISTRY
from astroweave.common.security import verify_user_token
from astroweave.graphs.specialist.specialist_graph import build_specialist_graph

app = FastAPI(title="AstroWeave Specialist Service")
graph = build_specialist_graph()


class SpecialistRequest(BaseModel):
    user_query: str
    messages: list[dict] = Field(default_factory=list)
    methodology: str = "vedic"
    chart_data: dict
    dependency_results: list[dict] = Field(default_factory=list)


def authenticated_user(authorization: str | None = Header(default=None)) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    username = verify_user_token(token) if scheme.lower() == "bearer" else None
    if username is None:
        raise HTTPException(status_code=401, detail="A valid user token is required.")
    return username


@app.post("/specialists/{specialist_name}/run")
def run_specialist(
    specialist_name: str,
    request: SpecialistRequest,
    username: str = Depends(authenticated_user),
) -> dict:
    if specialist_name not in SPECIALIST_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown specialist.")
    return graph.invoke(
        {**request.model_dump(), "current_task": specialist_name},
        context={"username": username},
    )