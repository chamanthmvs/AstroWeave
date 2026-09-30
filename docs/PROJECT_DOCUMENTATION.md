# AstroWeave Project Documentation

**Document status:** Living engineering reference<br>
**Application generation:** connector-owned requests and dependency-stage orchestrator<br>
**Last verified:** 2026-09-26<br>
**Production readiness:** Prototype; not production-ready

## 1. Purpose of This Document

This is the canonical functional and technical reference for AstroWeave. It is
intended for product planning, engineering, testing, operations, security
review, onboarding, and future agent-assisted development.

This document distinguishes among:

- **Implemented:** behavior present in the current source code.
- **Placeholder:** a named architectural boundary that exists but does not yet
  provide its intended behavior.
- **Planned:** a direction represented in the repository or product design but
  not implemented.

When this document conflicts with the source code, the source code is the
runtime authority and this document must be corrected in the same change.

Readers new to Python, agents, and the project can start with the visual,
chapter-by-chapter [AstroWeave beginner's book](ASTROWEAVE_BOOK.md). It follows
the request lifecycle and introduces Python, graphs, LLMs, tools, chart
calculations, persistence, tests, and source navigation in learning order.

## 2. Product Overview

AstroWeave is a hierarchical, multi-agent astrology application. A user asks a
natural-language question, and a top-level LangGraph orchestrator selects one
or more domain specialists, runs each specialist against a computed birth
chart, collects their structured findings, and synthesizes one final response.

### 2.1 Product goals

- Hide orchestration complexity from the user.
- Separate question domains from astrology methodologies.
- Allow multiple specialists to contribute to one answer.
- Keep chart calculation isolated from the main application.
- Make routing and specialist reasoning observable through consistent text logs.
- Allow LLM providers and models to change through configuration.
- Degrade gracefully when one specialist fails.

### 2.2 Current users

The current Streamlit application is designed for individual users in India.
Users create a local account, save birth details, sign in, choose a methodology
preference, and submit astrology questions.

### 2.3 Current specialist domains

| Specialist | Intended questions |
|---|---|
| `career` | Jobs, promotions, business ventures, professional growth |
| `finance` | Wealth, income, investments, and financial timing |
| `love` | Relationships, marriage, compatibility, and romantic timing |
| `sports` | Athletic performance, competition, and sporting-event timing |

Education is mentioned in some public-facing copy but does not currently have
a registered specialist.

### 2.4 Methodologies

AstroWeave distinguishes a question's **domain** from the **methodology** used
to analyze it. Current methodology values are:

- `vedic`
- `kp`
- `both`
- system-selected, represented in the UI as `Let the system decide`

Methodology values are required by prompts but are not yet enforced by a
runtime schema. Specialist names are different: the orchestrator filters
classifier output through `SPECIALIST_REGISTRY`, so an unregistered name is
discarded before task planning. If no registered specialist remains, planning
records an error and no specialist is dispatched.

Methodology selection is passed to specialist prompts. The
`methodologies/vedic` and `methodologies/kp` packages do not yet contain
separate deterministic analysis engines or retrieval pipelines.

## 3. Functional Scope

### 3.1 Registration

Implemented registration behavior:

1. The user enters a name, email address, password, birth date, birth time, and
   birth place.
2. Passwords must contain at least eight characters at the UI boundary.
3. The user may mark the exact birth date as unknown.
4. Birth place is resolved through Nominatim with `country_codes="in"` and a
  certifi-backed verified TLS context.
5. The application uses a fixed UTC offset of `+5.5` hours.
6. The account and birth details are stored in a local SQLite database.
7. The user is signed in immediately after successful registration.

If the birth date is unknown, the application stores an empty date string and
`date_known=false`. The UI warns that accuracy is reduced. The chart service
cannot currently calculate a chart from an empty date, so unknown-date support
is incomplete beyond account storage and display.

### 3.2 Sign-in and sign-out

- Email addresses are normalized to lowercase by the UI before authentication.
- Password verification uses scrypt and constant-time hash comparison.
- Successful authentication stores the user record in Streamlit session state.
- Sign-out clears the session-state user and reruns the application.
- There are no password-reset, email-verification, account-lockout, multi-factor
  authentication, or remote identity-provider flows.

### 3.3 Birth details

Birth details are captured at registration and displayed read-only in the
workspace sidebar. There is currently no edit workflow.

Stored fields:

| Field | Meaning |
|---|---|
| `date` | Birth date in `YYYY-MM-DD`, or empty when unknown |
| `date_known` | Whether the exact date is known |
| `time` | Local birth time in `HH:MM:SS` |
| `place_name` | User-entered place name |
| `latitude` | Geocoded latitude |
| `longitude` | Geocoded longitude |
| `utc_offset_hours` | Fixed to `5.5` in the current UI |

### 3.4 Requesting a reading

1. The signed-in user enters one question.
2. The user chooses `Let the system decide`, `Vedic`, `KP`, or `Both`.
3. The UI sends the question and methodology to the connector's `POST /run`.
4. The connector loads the authenticated profile and history, then invokes the
  DAG orchestrator (or a configured direct specialist).
5. The UI renders the final answer as Markdown.
6. An always-available expander exposes the final orchestration state after a
  successful reading. It is not currently restricted to development mode.

The connector issues UUID-based conversation and session IDs on the first run
and returns them in the response. The UI retains these opaque IDs for follow-ups. Users can start,
resume, and delete recent conversations, inspect the current IDs, and read the
stored transcript. Conversation IDs identify durable threads; session IDs
separate messages created during the current signed-in workspace session from
messages saved during prior sessions.

### 3.5 Multi-domain questions

The classifier selects specialists and optional `tasks` with `depends_on` edges.
The planner validates references, duplicates, and cycles, then computes
topological stages. Specialists within a stage run concurrently; the next stage
starts only after all tasks in the current stage finish. When no task edges are
returned, all selected specialists are independent. The chart is fetched once
and shared across stages. Only the requested upstream findings are handed to a
dependent specialist; its own output is collected separately.

An unrelated specialist continues after a failure. A dependent task is skipped
when a required predecessor produced no result. If at least one result succeeds,
synthesis uses successful findings; otherwise the answer reports errors.

### 3.6 Conversation history

AstroWeave implements two bounded context scopes over one durable transcript:

- **Session history:** up to 12 recent messages in the current conversation
  written with the current session ID.
- **Conversation history:** up to 8 recent messages in the same conversation
  written during previous sessions.

Both limits are configurable. The complete transcript remains in SQLite even
though only bounded windows are sent to LLMs. The current user question and
final assistant answer are persisted atomically by the connector after synthesis
(or a direct specialist run). Reusing a
`message_id` and the same request content return the previously stored answer
without rerunning the graph. Reusing the ID for different request data is a
conflict.

Conversation summaries and cross-conversation user memories are not yet
implemented.

## 4. System Architecture

### 4.1 Runtime components

| Component | Technology | Default address | Responsibility |
|---|---|---|---|
| Web UI | Streamlit | `127.0.0.1:8501` | Account flow and reading workspace |
| Connector API | FastAPI | `127.0.0.1:8000` | Account access, IDs, history, persistence, app routing |
| Orchestrator | LangGraph | In connector process | Routing, dependency stages, synthesis; no database access |
| Agent registry | Python registry | In main API process | Registered agent definitions and lookup |
| Specialist graph | LangGraph | In main API process | Domain-specific LLM analysis |
| Optional specialist HTTP service | FastAPI | Operator-selected port | Independently deployable specialist graph, no database access |
| Chart service | FastAPI + PyJHora | `127.0.0.1:8100` | Deterministic chart calculations |
| User store | SQLite | `app/data/astroweave.db` | Local accounts and birth details |
| LLM provider | Configurable | External | Classification, specialist analysis, synthesis |
| Geocoder | Nominatim via geopy | External | Indian place-name resolution |

### 4.2 Component diagram

```mermaid
flowchart LR
    User[User] --> UI[Streamlit UI]
    UI --> Geo[Nominatim geocoding]
    UI --> API[FastAPI connector]
    API --> DB[("SQLite accounts and conversations")]
    API --> Orchestrator[LangGraph DAG orchestrator]
    Orchestrator --> LLM[Configured LLM provider]
    Orchestrator --> AgentRegistry[Specialist agent registry]
    AgentRegistry --> ToolRegistry[Per-agent tool registries]
    API -->|configured app ID| Specialist[Specialist subgraph or HTTP service]
    Orchestrator --> Specialist
    Specialist --> AgentRegistry
    Specialist --> LLM
    Orchestrator --> ChartClient[Chart HTTP client]
    ChartClient --> ChartService[PyJHora chart service]
```

### 4.3 Repository layout

| Path | Responsibility |
|---|---|
| `app/` | Streamlit application, authentication, and geocoding |
| `chart_service/` | Isolated chart-calculation API and dependencies |
| `src/astroweave/api/` | Main FastAPI boundary |
| `src/astroweave/graphs/orchestrator/` | v2 top-level graph and prompts |
| `src/astroweave/graphs/specialist/` | Shared specialist graph |
| `src/astroweave/agents/registry.py` | Agent definition and registry abstractions |
| `src/astroweave/agents/specialists/` | Registered specialist definitions and prompts |
| `src/astroweave/common/tools/` | Tool contracts, decorator, per-agent registry, and chart client |
| `src/astroweave/common/` | State, context, LLM, logging, and shared infrastructure |
| `src/astroweave/orchestration/` | Manager and specialist dispatch helpers |
| `src/astroweave/methodologies/` | Methodology normalization and future engines |
| `tests/unit/` | Unit tests for auth, config, graphs, and dispatcher |
| `tests/integration/` | HTTP-boundary tests with mocked graph execution |
| `docs/` | GitHub Pages site and this canonical project document |

## 5. End-to-End Reading Sequence

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit
    participant API as Connector API
    participant O as DAG Orchestrator
    participant D as Specialist dispatcher
    participant CC as Chart HTTP client
    participant C as Chart Service
    participant S as Specialist Graph
    participant L as LLM Provider

    User->>UI: Submit question and methodology
    UI->>API: POST /run with query, optional IDs
    API->>API: Authenticate, resolve IDs, claim request, load profile and history
    API->>O: invoke(query, bounded history, birth details)
    O->>L: Classify request
    L-->>O: Specialists, dependencies, methodology
    O->>O: Validate DAG and derive stages
    O->>D: Run stage and dispatch ready tasks
    D->>CC: Get or reuse chart data
    CC->>C: POST /chart
    C-->>CC: Full chart payload
    CC-->>O: Decoded chart dictionary
    loop For each dependency stage
      O->>S: Invoke ready specialists concurrently (local or HTTP)
        S->>L: Structured analysis request
        L-->>S: Analysis, conclusion, confidence
        S-->>O: Specialist result
        O->>O: Collect results before next stage
    end
    O->>L: Synthesize collected findings
    L-->>O: Plain-text final answer
    O-->>API: Final state
    API->>API: Persist turn and release/complete claim
    API-->>UI: Answer, issued IDs, state, empty execution trace
    UI-->>User: Render reading
```

## 6. Dependency-Stage Orchestrator

### 6.1 Graph topology

```mermaid
flowchart TD
    START((Start)) --> RCC[Validate Query]
    RCC --> V{Request valid?}
    V -->|No| SR[Synthesize Response]
    V -->|Yes| CR[Classify Request]
    CR --> PST[Plan Specialist Tasks]
    PST --> R{Stages remain?}
    R -->|No| SR
    R -->|Yes| RS[Run Stage Concurrently]
    RS --> R
    SR --> END((End))
```

### 6.2 Node responsibilities

#### `resolve-conversation-context`

- Calls the current manager validation helper.
- Rejects an empty query by recording an error.
- Uses bounded history already supplied in `state.messages` by the connector;
  it does not open the database.
- Routes errors directly to response synthesis.

#### `classify-request`

- Calls the orchestrator LLM with the routing prompt.
- Tells the classifier whether birth details are available without sending the
  full birth-details payload.
- Expects JSON containing `specialists`, `tasks` (`specialist`, `depends_on`),
  `methodology`, and `reasoning`. Legacy responses without `tasks` run selected
  specialists as one independent stage.
- Keeps only specialist names present in `SPECIALIST_REGISTRY` and logs ignored
  names. This prevents model-generated agent names from entering execution.
- Honors a valid user-forced methodology over the model-selected methodology.
- Defaults methodology to `vedic` when neither source provides one.
- Appends routing reasoning to `state.plan`.

#### `plan-specialist-tasks`

- Removes duplicate selections, validates every dependency and rejects cycles.
- Computes `task_stages` by repeatedly selecting tasks whose dependencies are
  already in earlier stages; `pending_tasks` and `completed_tasks` track progress.
- Records an error when no specialist was selected.

#### `run-stage`

- Loads the full chart once (or uses cached state) and invokes ready specialists
  with a bounded thread pool within each stage.
- Supplies only required prior findings in `dependency_results`, separate from
  the additive `specialist_results` output.
- Skips dependents whose required predecessor produced no result. Independent
  tasks can succeed even when another task fails.
- Collects results and errors in deterministic task order and advances to the
  next stage. `completed_tasks` includes skipped tasks.

#### `synthesize-response`

- Combines successful specialist results with the original question.
- Calls the orchestrator LLM for a concise plain-text response.
- Preserves meaningful disagreement through the synthesis prompt.
- Falls back to concatenated conclusions if the optional context limit is
  exceeded.
- Returns recorded errors as the answer when there are no successful results.

### 6.3 Stage semantics

- No dependency: same stage and concurrent execution. Dependency: later stage.
- Stages run in order; tasks in one stage finish before the next starts.
- A completed task means the task was attempted, not necessarily successful.
- Errors use an additive state reducer and do not stop independent tasks.
- Specialist results use an additive reducer and accumulate across tasks.
- The birth chart is stored in state after first retrieval and reused.

## 7. Specialist Graph

Each registered domain uses the same specialist graph implementation. The
executor resolves its `AgentDefinition` from `SPECIALIST_REGISTRY` and uses
the prompt stored on that definition.

```mermaid
flowchart TD
    START((Start)) --> P[Planner]
    P --> E[Executor]
    E --> C[Collector]
    C --> V[Evaluator]
    V -->|Sufficient| S[Synthesizer]
    V -->|Insufficient| P
    S --> END((End))
```

Current implementation details:

- `planner`, `collector`, and `synthesizer` are no-op nodes.
- `executor` performs the actual specialist LLM call.
- `evaluator` always marks the result sufficient.
- The graph therefore executes exactly one analysis attempt per invocation,
  apart from the JSON-level retry described later.
- A real specialist tool loop or replanning policy is not implemented.

### 7.1 Specialist input

The executor sends:

- User question
- Selected methodology
- Full chart data serialized as JSON
- Domain-specific system prompt

### 7.2 Specialist output contract

The following shape is a prompt contract, not a runtime-validated schema.
Current parsing verifies JSON syntax only. Missing fields receive permissive
defaults, and confidence values are not restricted to the documented set.

```json
{
  "analysis": "Astrological reasoning grounded in the supplied chart",
  "conclusion": "Direct answer to the user's question",
  "confidence": "low|medium|high"
}
```

The graph stores the result as:

```json
{
  "specialist": "career",
  "analysis": "...",
  "conclusion": "...",
  "confidence": "high"
}
```

Unknown specialist names produce an error and no result.

### 7.3 Agent registry

`src/astroweave/agents/registry.py` defines the orchestrator-facing agent
catalog:

- `AgentDefinition` is an immutable dataclass containing `name`,
  `description`, `prompt`, and a `ToolRegistry` owned by that agent.
- `AgentRegistry` supports `register()`, optional `get()`, strict `require()`,
  membership checks, iteration, and length.
- Duplicate agent names raise `ValueError` rather than silently replacing an
  existing definition.
- `SPECIALIST_REGISTRY` contains the `career`, `finance`, `love`, and `sports`
  definitions. Each owns an independent registry of prompt-only intent
  descriptions (12 entries grouped into four intents per specialist). These
  entries are not executable Python functions, and the current specialist
  executor does not read the registries.

The registry replaces the former `SPECIALIST_PROMPTS` dictionary. This keeps
the prompt and future agent-specific capabilities in one definition, gives the
orchestrator a single source of truth for allowed agents, and avoids adding
special-case imports or conditionals as specialists gain different tools.

### 7.4 Tool contracts and per-agent registry

`src/astroweave/common/tools/base.py` provides the common tool API:

| Type | Purpose |
|---|---|
| `BaseToolReturnType` | Pydantic base response with `success: bool` and optional `error: str` |
| `ToolType` | String enum distinguishing executable `function` wrappers from descriptive `prompt` tools |
| `ToolMetadata` | Pydantic metadata with `name`, `description`, `type`, and `returns` |
| `BaseTool` | Abstract contract requiring `metadata` and `invoke()` |
| `FunctionTool` | Callable adapter around a normal Python function |
| `PromptTool` | Descriptive prompt/intent metadata whose `invoke()` deliberately raises an error |
| `tool()` | Decorator that creates a `FunctionTool` from a function |

`ToolMetadata.returns` stores the response model class, not a response
instance. This lets callers inspect the declared response schema before a tool
runs. `FunctionTool.invoke()` verifies at runtime that the function returned
an instance of that declared model and raises `TypeError` for a contract
violation. The decorator preserves the wrapped function's name, documentation,
and inspectable signature.

Tool responses can add fields while retaining the shared status contract:

```python
from astroweave.common.tools import BaseToolReturnType, tool


class CareerFocusResult(BaseToolReturnType):
    focus: str | None = None


@tool(
    name="career_focus",
    description="Find the strongest career theme.",
    returns=CareerFocusResult,
)
def career_focus(question: str) -> CareerFocusResult:
    return CareerFocusResult(success=True, focus=question)
```

`src/astroweave/common/tools/registry.py` defines `ToolRegistry`. A registry
owns the tools available to one agent and provides `register()`, `get()`,
`require()`, iteration, membership, length, and metadata listing. Duplicate
tool names raise `ValueError` to prevent accidental shadowing.

This design deliberately separates registration from execution. The current
specialist graph does not expose tool schemas to an LLM, parse tool calls, run
tools, append `tool_results`, or replan after a tool response. Those behaviors
remain future work. The existing chart client also remains an orchestrator
dependency rather than being decorated as an agent tool because chart loading
currently happens once before specialist invocation and is reused through
shared state.

For the dedicated chapter explaining how direct function calls, LangGraph
graph invocation, LangChain model invocation, and a future LLM-driven tool loop
differ, see [06. Tools and Handoffs](BEGINNER_GUIDE.md).

## 8. Shared State and Runtime Context

### 8.1 State data dictionary

| Field | Type | Current role |
|---|---|---|
| `user_query` | `str` | Original user question |
| `messages` | additive list | Connector-supplied bounded history |
| `history_persisted` | `bool` | Connector response state: final turn exists durably |
| `history_replayed` | `bool` | Connector response state: idempotent retry |
| `plan` | `list[str]` | Classifier reasoning history |
| `specialists` | `list[str]` | Selected domain specialists |
| `methodology` | `str` | Normalized methodology |
| `task_dependencies` | mapping | Planner-validated predecessor names |
| `task_stages` | `list[list[str]]` | Remaining ready batches |
| `pending_tasks` | `list[str]` | Specialists not yet attempted |
| `completed_tasks` | `list[str]` | Specialists already attempted |
| `current_task` | `str` | Selected task inside a specialist subgraph |
| `dependency_results` | list | Required predecessor findings passed to a specialist |
| `chart_data` | dictionary | Full chart-service response, reused across tasks |
| `specialist_results` | additive list | Structured successful results |
| `errors` | additive list | Recoverable and terminal run errors |
| `iteration_count` | `int` | Number of completed or skipped tasks |
| `answer` | `str` | Final user-facing response |
| `tool_results` | additive list | Reserved for future tools |
| `stage_results` | latest five | Reserved bounded stage outputs |
| `specialist_analysis` | `str` | Latest specialist analysis |
| `evaluation` | `str` | Latest specialist confidence |
| `needs_replanning` | `bool` | Reserved; not used by staged orchestrator |
| `is_sufficient` | `bool` | Used by specialist evaluator |

The `specialist_results` and `errors` reducers use list addition. Replacing
them with ordinary lists would change multi-task merge behavior.

### 8.2 Runtime context

Context is request-scoped and is not treated as mutable graph state.

| Field | Current use |
|---|---|
| `conversation_id` | Connector-issued thread ID, available to downstream services |
| `session_id` | Connector-issued session ID |
| `username` | Authenticated owner identity |
| `methodology` | User-forced methodology input |
| `birth_details` | Chart-service request input |

Only the connector owns history loading, request claims, and persistence.
The username is the ownership partition. A supplied `/run` username must
match the signed bearer-token subject.

## 9. Main API Contract

### 9.1 `GET /health`

Response:

```json
{
  "status": "ok",
  "service": "astroweave-api"
}
```

This confirms process availability only. It does not test the LLM provider,
chart service, SQLite database, or geocoder.

### 9.2 Account endpoints

- `POST /auth/register`: `{ "email", "name", "password", "birth_details" }`;
  birth details include date, time, coordinates, UTC offset, optional place name
  and `date_known`. Returns `{ "user", "token" }` (HTTP `422` for invalid data
  or duplicate account). The connector performs the SQLite insert and scrypt
  password hashing.
- `POST /auth/sign-in`: `{ "email", "password" }`; returns the same user/token
  shape, or HTTP `401` for invalid credentials.
- `GET /auth/me`: authenticated profile lookup. The UI keeps the token in
  session state and sends it as `Authorization: Bearer <token>`.

The UI still geocodes a birth place before registration; it never opens SQLite.
Production deployments should move geocoding and account identity to dedicated
services as appropriate.

### 9.3 `POST /run`

Request body:

```json
{
  "query": "How will a promotion affect my finances?",
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "methodology": "Let the system decide"
}
```

Validation rules:

- `query` and bearer token are required. `conversation_id` and `session_id`
  are optional: the connector creates missing UUIDs and returns both values.
  Send them on subsequent turns to keep the same conversation and session;
  omit `session_id` when resuming a prior conversation in a new session.
- `username`, if supplied for older clients, must equal the token subject.
- `methodology` defaults to `Let the system decide`.
- Birth details come from the connector's account record, not the request body.
  The legacy `birth_details` field is accepted but ignored by execution.
- `message_id` defaults to a UUID; supply the same ID and payload for reliable
  retry. With omitted IDs, the connector recovers the original IDs by message ID.
- Optional `app_id` selects a specialist from the server-side JSON mapping
  `ASTROWEAVE_APP_ROUTES`, e.g. `{"career-app":"career"}`. Unknown app IDs
  return `403`. Without an app ID, the DAG orchestrator runs as usual.
- Direct routing skips classifier, planner, and orchestrator synthesis. Its
  answer is the specialist conclusion; both paths persist the same transcript.

Abridged successful response:

```json
{
  "answer": "Synthesized response",
  "conversation_id": "server-issued-conversation-id",
  "session_id": "server-issued-session-id",
  "state": {
    "specialists": ["career", "finance"],
    "pending_tasks": [],
    "task_stages": [],
    "completed_tasks": ["career", "finance"],
    "specialist_results": [
      {
        "specialist": "career",
        "analysis": "...",
        "conclusion": "...",
        "confidence": "high"
      }
    ],
    "answer": "Synthesized response"
  },
  "execution_trace": []
}
```

Important current behavior:

- The response exposes the complete final state, including full chart data.
- `execution_trace` is always an empty list.
- Duplicate requests with the same owned conversation and `message_id` return
  the stored assistant answer without rerunning the graph.
- The idempotency key is bound to a SHA-256 fingerprint of request fields
  (excluding `message_id` and username). Different data returns `409`.
- A durable pending claim prevents concurrent processes from executing the same
  message ID; concurrent duplicates return `409` while work is in progress.
- Claims abandoned by a crashed process can be reclaimed after a configurable
  lease, 30 minutes by default with a 60-second minimum.
- Each lease has a unique fencing token; stale workers cannot release or
  complete a newer worker's reclaimed claim.
- Validation failures return FastAPI/Pydantic `422` responses.
- Unhandled graph or storage failures are mapped to `502 Bad Gateway` and include the
  exception text in `detail`.
- Recoverable graph errors may still return HTTP `200` with error text in state
  and possibly in the answer.
- `/run` and conversation endpoints require a signed bearer token.

### 9.4 Specialist HTTP service

Run `astroweave.specialist_service:app` in a separate process per specialist
(or one shared specialist process). The connector/orchestrator dispatcher uses
`ASTROWEAVE_SPECIALIST_URLS` to choose remote instead of in-process execution:
`{"career":"http://127.0.0.1:8200"}`. A missing entry uses the local graph.
The dispatcher posts to `<base>/specialists/{name}/run` with a signed bearer
token, user query, prior messages, methodology, shared `chart_data`, and
`dependency_results`. The service validates the specialist against the
registry and returns `specialist_results` and `errors`; it has no database
dependency. Its HTTP `401`/`404` responses become task errors in the dispatcher.
All processes must share `ASTROWEAVE_AUTH_SECRET`; use private service networking
and TLS in deployment. HTTP is the first transport; A2A is not implemented.

### 9.5 Conversation endpoints

`GET /conversations?limit=<1..100>` lists active conversations owned by the
authenticated bearer-token subject, newest first.

`GET /conversations/{conversation_id}/messages?limit=<1..100>`
returns the most recent transcript messages in chronological order.

`DELETE /conversations/{conversation_id}` deletes a conversation owned by the
authenticated subject and cascades deletion to its messages.

Existing IDs owned by another authenticated user return HTTP `403`.

## 10. Chart Service

### 10.1 Isolation boundary

The chart service is a separate FastAPI process because it depends on PyJHora,
an AGPL-3.0 package. The main backend communicates with it only over HTTP and
does not import PyJHora.

This process separation is an architectural boundary, not legal advice. Any
distribution or deployment model should receive an appropriate license review.

### 10.2 Endpoints

#### `GET /health`

```json
{
  "status": "ok",
  "service": "astroweave-chart-service"
}
```

#### `POST /chart`

Required inputs are date, time, latitude, longitude, and UTC offset. Optional
flags control output sections.

Default output includes:

- D1/Rasi chart with ascendant and planetary positions
- KP number and nested lord levels for D1 positions
- Divisional charts D2, D3, D7, D9, D10, D12, D24, and D60
- Vimshottari dasha-bhukti table
- Bhava chart
- Ashtakavarga
- Shadbala
- Detected yogas
- Current transits
- Current maha-dasha, antardasha, and pratyantardasha

Malformed non-numeric date/time parts are mapped to HTTP `422`. Invalid
calendar values and other calculation errors are not explicitly translated
and may surface as server errors.

### 10.3 Main-backend chart client

- Base URL: `ASTROWEAVE_CHART_SERVICE_URL`
- Default: `http://127.0.0.1:8100`
- Default HTTP timeout: 10 seconds
- The dispatcher currently requests the full default chart.
- HTTP failures become state errors instead of crashing the remaining graph.

## 11. LLM Architecture

### 11.1 Provider abstraction

The provider registry includes:

| Provider key | Adapter | Dependency |
|---|---|---|
| `groq` | `ChatOpenAI` with Groq-compatible base URL | `langchain-openai` |
| `openai` | `ChatOpenAI` | `langchain-openai` |
| `anthropic` | `ChatAnthropic` | optional `langchain-anthropic` |

Providers are imported lazily. Selecting a provider whose optional package is
not installed fails when that provider is built.

### 11.2 Configuration precedence

For each setting, the most specific non-empty value wins:

1. Agent-specific, such as `ASTROWEAVE_LLM_MODEL_CAREER`
2. Role-specific, such as `ASTROWEAVE_LLM_MODEL_SPECIALIST`
3. Global, such as `ASTROWEAVE_LLM_MODEL`
4. Built-in default

Supported setting families:

- `ASTROWEAVE_LLM_PROVIDER`
- `ASTROWEAVE_LLM_MODEL`
- `ASTROWEAVE_LLM_TEMPERATURE`
- `ASTROWEAVE_LLM_MAX_TOKENS`

All four values are resolved into `LLMConfig`. The current Groq adapter applies
`max_tokens`; the OpenAI and Anthropic builders currently use provider/model/
temperature but do not pass the resolved maximum-token value.

Built-in defaults:

| Setting | Default |
|---|---|
| Provider | `groq` |
| Model | `openai/gpt-oss-120b` |
| Temperature | `0.2` |
| Maximum completion tokens | `4096` |

`ASTROWEAVE_ENV` selects `.env.<name>`, defaulting to
`.env.development`. If that file does not exist, configuration falls back to
`.env`.

### 11.3 Required provider secrets

- Groq: `GROQ_API_KEY`
- OpenAI: the environment expected by `ChatOpenAI`, normally `OPENAI_API_KEY`
- Anthropic: the environment expected by `ChatAnthropic`, normally
  `ANTHROPIC_API_KEY`

Secrets and `.env*` files are ignored by Git and must be managed by the runtime
environment or deployment secret manager.

### 11.4 Structured JSON reliability

Classification and specialist calls use `invoke_json_response()`:

1. Invoke the model.
2. Log attempt number, response character length, and provider finish reason.
3. Parse JSON syntax. Object shape and allowed values are not schema-validated.
4. Log the model's `reasoning` or `analysis` field.
5. Retry once if JSON parsing fails.
6. Surface a state error if both attempts fail.

The 4096-token default was introduced after real end-to-end testing observed
Groq returning `finish_reason=length` and truncated specialist JSON under the
provider's smaller default completion budget.

### 11.5 Context-size protection

`ASTROWEAVE_CONTEXT_CHAR_LIMIT` is an optional character-count guard. It is
disabled when absent, invalid, zero, or negative.

When enabled, it is enforced:

- Before the dispatcher invokes a specialist subgraph
- Before a specialist invokes its LLM
- Before the orchestrator invokes final synthesis

Specialist over-limit errors are isolated to that task. Synthesis over-limit
errors trigger a fallback that concatenates specialist conclusions.

## 12. Authentication and Persistence

### 12.1 SQLite user schema

The local `users` table contains:

- Numeric primary key
- Unique email
- Name
- Password hash
- Birth date and `date_known` flag
- Birth time and place
- Latitude and longitude
- UTC offset
- Creation timestamp

The default database path is `app/data/astroweave.db` and can be overridden
with `ASTROWEAVE_USERS_DB`.

### 12.2 Password handling

- Passwords are hashed with `hashlib.scrypt`.
- Each password receives a random 16-byte salt.
- Parameters are stored with the encoded hash.
- Verification uses `hmac.compare_digest`.
- Plain-text passwords are not persisted.

### 12.3 Current authentication boundary

The connector authenticates against SQLite and issues an HMAC-SHA256 bearer
token containing the user's email and a 12-hour expiration. The API verifies
the signature and expiry, loads the account profile, and uses the token subject
for conversation ownership. A supplied `/run` username must match that subject.
The specialist HTTP service verifies a connector-signed bearer token.

Connector and specialist processes must share `ASTROWEAVE_AUTH_SECRET`. Development falls back to
a known local-only secret with a warning; production mode refuses to sign or
verify without an explicit secret. Tokens are stateless and cannot currently
be individually revoked before expiry.

### 12.4 Conversation persistence

Conversation records share the existing SQLite database by default. The connector
store creates four tables:

- `conversations`: globally unique ID, owner, title, timestamps, archive field
- `conversation_sessions`: globally unique ID, owner, lifecycle timestamps
- `conversation_messages`: user/assistant content, session, owner, and ordered
  sequence number
- `conversation_requests`: message ID, claim token, payload fingerprint, status,
  and replayable answer

Writes use `BEGIN IMMEDIATE` and store each user/assistant turn in one
transaction. Foreign keys cascade message deletion with conversations. WAL,
foreign-key enforcement, and a 10-second busy timeout are enabled on
conversation-store connections.

The database path precedence is:

1. `ASTROWEAVE_CONVERSATIONS_DB`
2. `ASTROWEAVE_USERS_DB`
3. `app/data/astroweave.db`

The full transcript is durable history. Context loading remains bounded to
avoid sending an ever-growing transcript to every model call.

## 13. Security and Privacy Assessment

### 13.1 Sensitive data processed

- Name and email address
- Password hash
- Exact birth date and time
- Birth place and coordinates
- Astrology questions
- Complete calculated chart
- LLM-generated analysis

### 13.2 Existing protections

- Password hashing with scrypt and random salts
- Parameterized SQLite queries
- Local database and environment files excluded from Git
- Provider API keys loaded from environment variables
- PyJHora isolated behind a separate network service
- Coordinate bounds validated by Pydantic

### 13.3 Material current risks

1. **Development fallback secret:** deployments that do not set production
  mode and a strong `ASTROWEAVE_AUTH_SECRET` use a publicly known local secret.
2. **No token revocation:** signed tokens remain valid until their 12-hour
  expiry even after sign-out.
3. **Sensitive response state:** `/run` returns full chart data and internal
   reasoning state to the client.
4. **PII in logs:** manager logging includes the complete user query; auth logs
   include email addresses; chart logs include birth date and time.
5. **Verbose error disclosure:** unhandled exception text is returned in the
   public `502` response.
6. **No rate limiting:** API, sign-in, and registration attempts are not
   throttled.
7. **Local session model:** Streamlit session state is not a production-grade
   authentication session.
8. **No CSRF/session hardening:** no explicit production web-security controls
   exist around the local auth flow.
9. **Partial data lifecycle controls:** conversation deletion exists, but
  account deletion, export, retention, and consent workflows are not complete.
10. **External processing:** questions and chart data are sent to the configured
   LLM provider; place names are sent to Nominatim during registration.

Production deployment should not proceed until these risks are addressed and
a privacy policy, data-processing basis, retention policy, and threat model are
defined.

## 14. Failure and Degradation Behavior

| Failure | Current behavior |
|---|---|
| Empty query inside graph | Short-circuits to synthesis with an error answer |
| Invalid API request | HTTP `422` |
| Classifier malformed JSON twice | Error recorded; no specialist tasks |
| No specialist selected | Planner records an error |
| Missing birth details | Specialist execution records an error |
| Chart service HTTP failure | Error recorded for specialist execution |
| One specialist raises | Error retained; later tasks continue |
| Specialist malformed JSON twice | No result for that specialist; error retained |
| Synthesis context too large | Raw specialist conclusions returned with error |
| Unhandled graph exception | Main API returns HTTP `502` |
| Streamlit cannot reach API | User-facing connection error |
| Place not found in India | Registration blocked with nearby-city guidance |
| Geocoding provider/TLS failure | Distinct temporary-service error shown |
| Conversation/session owned by another username | HTTP `403` |
| Duplicate owned `message_id` | Stored answer replayed; graph not rerun |
| Same `message_id`, different request | HTTP `409` |
| Same `message_id` already running | HTTP `409` |
| Missing, invalid, or expired bearer token | HTTP `401` |
| Body username differs from token | HTTP `403` |

The system does not currently classify errors into stable machine-readable
codes. Most graph failures are human-readable strings.

## 15. Observability

### 15.1 Log configuration

- Root format: timestamp, level, logger name, message
- Default level: `INFO`
- Main backend override: `ASTROWEAVE_LOG_LEVEL`
- Logging is configured once per process

Streamlit and the chart service currently initialize logging directly at
`INFO`; they do not honor `ASTROWEAVE_LOG_LEVEL`.

### 15.2 Logged orchestration events

- API request metadata and query length
- Connector history loading and request claims
- Every conditional route destination
- Selected specialists and methodology
- Dependency-stage creation and completion
- Chart retrieval and reuse
- Specialist start, completion, result count, and error count
- LLM JSON attempt, content length, and finish reason
- Classifier reasoning and specialist analysis
- Stage progress and synthesis result count

### 15.3 Current observability gaps

- No structured JSON logs
- No correlation ID automatically attached to every log record
- No metrics, tracing backend, dashboards, or alerting
- `execution_trace` in the API response is empty
- No token usage, latency, or cost aggregation
- Full reasoning logs may be too sensitive and verbose for production

## 16. Testing Strategy

### 16.1 Current automated tests

| Test module | Coverage focus |
|---|---|
| `test_auth.py` | SQLite registration, password hashing, authentication |
| `test_dispatcher.py` | Chart retrieval, local/HTTP specialist invocation, error propagation |
| `test_llm_config.py` | Completion-token defaults and precedence |
| `test_orchestrator_graph.py` | Concurrent stages, dependency handoff, cycles, partial failure |
| `test_specialist_graph.py` | Specialist output, unknown specialist, JSON retry |
| `test_agent_registry.py` | Built-in agents, per-agent tool ownership, duplicate rejection |
| `test_tools.py` | Decorator metadata, invocation contract, tool lookup, duplicate rejection |
| `test_api.py` | Registration, DAG/direct routes, persistence/replay, specialist auth |
| `test_conversation_store.py` | Transactions, scope separation, ownership, replay, deletion |
| `test_security_tokens.py` | Signing, expiry, tampering, and client parity |
| `test_geocoding.py` | Indian place match, no-result, provider failure |

The connector integration test uses temporary SQLite stores and mocks the
external chart and LLM boundaries.

### 16.2 Test boundaries

- Connector integration tests run the real DAG and specialist graph with mocked
  LLM and chart boundaries. HTTP transport is covered with a mocked remote
  response; a deployed multi-process HTTP run is not automated.
- The normal test suite does not require provider keys or the chart service.
- There are no automated chart-service tests in the current repository.
- There are no browser-level Streamlit tests.
- There are no load, security, migration, or deployment tests.

### 16.3 Verified real flow

Real local end-to-end verification has exercised:

- Streamlit and main API health
- Real Groq classification and synthesis
- Real PyJHora chart calculation
- One-specialist career flow
- Two-specialist career and finance flow (historical manual verification)
- Chart reuse between specialists
- Completion with no errors

The real two-specialist verification completed with two high-confidence
results, one chart request, no state errors, and a synthesized answer.

An expanded authenticated matrix on 2026-09-20 also verified:

- Career, love, and sports questions routed to their expected specialists
- An explicit two-part career/finance question executed both specialists
- Same-session follow-up loaded two current-session messages
- New-session continuation loaded four prior-session messages
- Exact request replay returned the canonical answer in approximately 2 ms
- Changed payload with the same message ID returned `409 request_conflict`
- Missing authentication returned `401`; cross-user transcript access returned
  `403`
- All test conversations were deleted after verification

A less explicit question about how changing jobs affects finances selected only
the finance specialist. This is consistent with the classifier's instruction to
choose the smallest sufficient specialist set; explicit multi-part wording is
required when validating multi-specialist execution deterministically.

## 17. Local Development

### 17.1 Main environment

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
```

Configure a local ignored environment file or export variables:

```bash
export ASTROWEAVE_LLM_PROVIDER=groq
export ASTROWEAVE_LLM_MODEL=openai/gpt-oss-120b
export ASTROWEAVE_LLM_MAX_TOKENS=4096
export GROQ_API_KEY=replace-with-local-secret
export ASTROWEAVE_APP_ROUTES='{"career-app":"career"}'
```

### 17.2 Chart-service environment

The chart service should use its own virtual environment.

```bash
cd chart_service
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8100
```

### 17.3 Main API

From the repository root:

```bash
PYTHONPATH=src .venv/bin/uvicorn astroweave.api.main:app \
  --host 127.0.0.1 --port 8000
```

### 17.4 Streamlit UI

```bash
.venv/bin/streamlit run app/streamlit_app.py \
  --server.headless true --server.address 127.0.0.1 --server.port 8501
```

The UI uses `ASTROWEAVE_API_URL` (default `http://127.0.0.1:8000`) for
registration and sign-in before the sidebar is available. The sidebar API URL
setting applies after sign-in.

### 17.5 Optional Specialist Process

From the repository root, start a specialist HTTP process with the same LLM
configuration and `ASTROWEAVE_AUTH_SECRET` as the connector:

```bash
PYTHONPATH=src .venv/bin/uvicorn astroweave.specialist_service:app \
  --host 127.0.0.1 --port 8200
```

Set `ASTROWEAVE_SPECIALIST_URLS='{"career":"http://127.0.0.1:8200"}'`
on the connector. Other specialists continue to run locally. The optional
service authenticates requests but does not access SQLite or calculate charts.
One service per specialist is an operator deployment choice; each instance
exposes the same registry routes.

### 17.6 Health Checks

```bash
curl http://127.0.0.1:8100/health
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8501/
```

### 17.7 Tests

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

## 18. Configuration Reference

| Variable | Default | Purpose |
|---|---|---|
| `ASTROWEAVE_ENV` | `development` | Select `.env.<name>` |
| `ASTROWEAVE_LOG_LEVEL` | `INFO` | Main backend log level |
| `ASTROWEAVE_LLM_PROVIDER` | `groq` | Global provider |
| `ASTROWEAVE_LLM_MODEL` | `openai/gpt-oss-120b` | Global model |
| `ASTROWEAVE_LLM_TEMPERATURE` | `0.2` | Global temperature |
| `ASTROWEAVE_LLM_MAX_TOKENS` | `4096` | Global completion budget |
| `ASTROWEAVE_CONTEXT_CHAR_LIMIT` | disabled | Optional handoff limit |
| `ASTROWEAVE_CHART_SERVICE_URL` | `http://127.0.0.1:8100` | Chart API base URL |
| `ASTROWEAVE_API_URL` | `http://127.0.0.1:8000` | UI auth and initial connector URL |
| `ASTROWEAVE_APP_ROUTES` | `{}` | JSON app ID to specialist registry name mapping |
| `ASTROWEAVE_SPECIALIST_URLS` | `{}` | JSON specialist name to remote service base URL mapping |
| `ASTROWEAVE_USERS_DB` | `app/data/astroweave.db` | SQLite database path |
| `ASTROWEAVE_CONVERSATIONS_DB` | users DB path | Conversation DB override |
| `ASTROWEAVE_SESSION_HISTORY_LIMIT` | `12` | Current-session message window |
| `ASTROWEAVE_CONVERSATION_HISTORY_LIMIT` | `8` | Prior-session message window |
| `ASTROWEAVE_AUTH_SECRET` | insecure development fallback | Bearer-token signing |
| `ASTROWEAVE_REQUEST_CLAIM_TTL_SECONDS` | `1800` | Abandoned claim lease |
| `GROQ_API_KEY` | none | Groq credential |
| `OPENAI_API_KEY` | none | OpenAI credential |
| `ANTHROPIC_API_KEY` | none | Anthropic credential |

LLM provider, model, temperature, and maximum-token variables also support
`_<ROLE>` and `_<AGENT>` suffixes.

## 19. Deployment Considerations

The current repository is optimized for local development. A production design
must address:

- Reverse proxy and TLS termination
- Replace local signed-token auth with a revocable production identity system
- Durable, managed user storage and schema migrations
- Secret management
- Rate limiting and abuse controls
- CORS policy
- Network policy between backend and chart service
- Horizontal scaling and process-safe caching
- LLM timeout, retry, and provider-fallback policy
- Health checks that include dependencies
- Structured logs, traces, metrics, and alerting
- Removal or redaction of sensitive state and reasoning
- Data retention, deletion, consent, and regional compliance
- PyJHora/AGPL deployment and distribution review

The module-level compiled orchestrator and cached specialist graph are reused
within one process. The connector opens short-lived account SQLite connections.
These choices need concurrency and deployment review
before multi-worker production use.

## 20. Implemented, Placeholder, and Planned Matrix

| Capability | Status | Notes |
|---|---|---|
| Local registration and sign-in | Implemented | SQLite + scrypt |
| India-only geocoding | Implemented | Nominatim, fixed IST offset |
| Read-only birth profile | Implemented | No edit workflow |
| Main API health and run endpoints | Implemented | Signed bearer token required |
| DAG staged orchestrator | Implemented | Parallel independent tasks; dependents run later |
| Connector-owned IDs/account/history | Implemented | UI does not open SQLite |
| App ID direct specialist routing | Implemented | Server-side mapping; bypasses planner/synthesis |
| Optional specialist HTTP service | Implemented | Per-specialist URL; A2A not implemented |
| Career, finance, love, sports prompts | Implemented | Shared graph |
| Full chart-service integration | Implemented | PyJHora HTTP service |
| Configurable LLM providers/models | Implemented | Env hierarchy |
| Malformed JSON retry | Implemented | One retry |
| Partial specialist failure | Implemented | Independent tasks continue; dependents skip |
| Orchestrator agent registry | Implemented | Registered agents are the routing source of truth |
| Per-agent tool registry | Implemented | Each agent owns an independent registry |
| Base tool response and metadata models | Implemented | Pydantic v2 contracts |
| Function tool decorator | Implemented | Adapts functions and enforces declared return model |
| Durable conversation transcripts | Implemented | SQLite, owner-filtered |
| Current-session history | Implemented | Bounded to 12 messages by default |
| Prior-session conversation history | Implemented | Bounded to 8 messages by default |
| Conversation list/resume | Implemented | API and Streamlit controls |
| Idempotent turn replay | Implemented | Durable claim + content fingerprint |
| Conversation deletion | Implemented | Owner-checked API endpoint |
| Conversation summaries | Planned | Needed for older long threads |
| Cross-conversation user memory | Planned | Requires explicit consent model |
| Execution trace response | Placeholder | Always empty |
| Specialist tool execution/replanning loop | Placeholder | Registration exists; invocation loop does not |
| Unknown birth-date chart strategy | Placeholder | UI/storage only |
| Vedic/KP deterministic engines | Planned | Packages are stubs |
| RAG and citations | Planned | Retrieval package is empty |
| Education specialist | Planned/undefined | Mentioned in copy, not registered |
| Production identity/security | Planned | Local auth only |
| Birth-detail editing | Planned | Explicitly absent |
| Production deployment automation | Planned | No container/IaC workflow |

## 21. Extension Guides

### 21.1 Add a specialist

1. Create `src/astroweave/agents/specialists/<name>/prompts.py`.
2. Define a prompt that returns `analysis`, `conclusion`, and `confidence`.
3. Export the prompt from that package.
4. Add an `AgentDefinition` to `SPECIALIST_REGISTRY`, including its name,
  description, prompt, and optional `ToolRegistry`.
5. Add it to the orchestrator routing prompt's allowed specialists.
6. Add focused specialist, routing, and multi-task tests.
7. Update this document and public capability copy.

### 21.2 Add a tool to an agent

1. Define a response model extending `BaseToolReturnType` for tool-specific
  output fields.
2. Decorate the implementation with `@tool(description=..., returns=...)`;
  provide `name` only when the function name is not the desired public name.
3. Register the resulting `FunctionTool` in the target agent's `ToolRegistry`.
4. Add tests for metadata, successful output, error output, and invalid return
  types.
5. Do not assume registration makes the tool LLM-callable. Implement and test
  the specialist execution loop before exposing tool instructions in prompts.

### 21.3 Add an LLM provider

1. Implement a builder accepting `LLMConfig`.
2. Keep the provider SDK import inside the builder.
3. Register the provider key with `register_provider()`.
4. Add the optional dependency and document its credential variable.
5. Test configuration resolution and a real structured-response call.

### 21.4 Add a methodology engine

1. Define whether it transforms chart data, retrieves knowledge, changes
   prompts, or performs deterministic calculations.
2. Implement it under `methodologies/<name>/`.
3. Keep domain selection independent from methodology selection.
4. Define structured inputs, outputs, and provenance.
5. Add unit tests and cross-methodology synthesis tests.

### 21.5 Add a chart output

1. Add a request flag and calculation in `chart_service/main.py`.
2. Keep output JSON serializable and explicitly named.
3. Update the main chart client signature if callers need control.
4. Add chart-service tests before exposing the field to prompts.
5. Review payload size and context-token impact.

## 22. Known Technical Debt and Recommended Priorities

### Priority 0: production blockers

1. Replace local signed tokens with a revocable production identity provider.
2. Stop returning full internal state and chart data by default.
3. Redact PII and model reasoning from production logs.
4. Define unknown-birth-date behavior before allowing those accounts to run.
5. Add rate limits, request limits, and safer public error responses.

### Priority 1: correctness and resilience

1. Add chart-service unit and contract tests.
2. Validate specialist confidence and required response fields.
3. Add LLM/network timeout and retry policies with error classification.
4. Implement dependency-aware health/readiness checks.
5. Add a real execution trace or remove it from the API contract.

### Priority 2: product capability

1. Add rolling conversation summaries for older transcript segments.
2. Add explicit, user-approved cross-conversation memory controls.
3. Build methodology-specific Vedic and KP execution paths.
4. Add source-grounded retrieval and citations.
5. Implement birth-detail editing and recalculation policy.
6. Remove or restrict the always-visible final-state panel and replace it with
  user-safe diagnostics.

### Priority 3: scale and operations

1. Add database migrations and a managed database strategy.
2. Add containers, CI, deployment automation, and environment validation.
3. Add structured telemetry, latency metrics, token usage, and cost tracking.
4. Evaluate parallel specialist execution after state and provider limits are
   well-defined.

## 23. Documentation Maintenance Rules

Update this document whenever a change affects:

- User-visible workflows
- API request or response contracts
- Graph topology or routing semantics
- State or context schemas
- Specialist or methodology availability
- Chart inputs or outputs
- Environment variables or defaults
- Security, persistence, or privacy behavior
- Test coverage or production-readiness claims

Public-facing summaries belong in `README.md` and `docs/index.html`. Detailed
functional and technical behavior belongs here. Temporary session notes should
not be treated as a substitute for this document.