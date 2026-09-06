from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel, Field

from astroweave.common.trace import normalized_state, record_event, serializable_config
from astroweave.graphs.orchestrator.orchestrator_graph import build_orchestrator_graph


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
    message_id: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "astroweave-api"}


@app.post("/run")
def run(request: RunRequest) -> dict[str, object]:
    message_id = request.message_id or str(uuid4())
    context = {
        "conversation_id": request.conversation_id,
        "session_id": request.session_id,
        "username": request.username,
        "message_id": message_id,
    }
    runnable_config = {
        "configurable": {"thread_id": request.conversation_id},
        "metadata": {
            "session_id": request.session_id,
            "methodology": request.methodology,
        },
        "tags": ["demo", "no-llm"],
    }
    initial_state = {
        "user_query": request.query,
        "messages": [
            {"message_id": message_id, "role": "user", "content": request.query}
        ],
        "plan": [],
        "current_task": "",
        "tool_results": [],
        "stage_results": [],
        "specialist_analysis": "",
        "evaluation": "",
        "needs_replanning": False,
        "iteration_count": 0,
        "answer": "",
        "errors": [],
        "is_sufficient": False,
        "selected_specialists": [],
        "specialist_results": [],
    }
    initial_trace = record_event(
        initial_state,
        "graph_entry",
        "Accepted the request and initialized the shared state.",
        context,
        runnable_config,
    )
    initial_state["execution_trace"] = initial_trace["execution_trace"]
    state = build_orchestrator_graph().invoke(
        initial_state,
        context=context,
        config=runnable_config,
    )
    return {
        "answer": state.get("answer", ""),
        "state": normalized_state(state),
        "context": context,
        "runnable_config": serializable_config(runnable_config),
        "execution_trace": state.get("execution_trace", []),
    }
