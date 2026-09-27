# A2A for Beginners: A Practical AstroWeave Walkthrough

This document starts from zero assumed knowledge. It explains agent-to-agent communication, the formal A2A protocol, how AstroWeave currently sends work to a separate specialist service, and what happens when that service is not used. A real project execution is included so the ideas connect to code and observable input/output.

> **Important distinction:** AstroWeave currently has a custom authenticated HTTP handoff between its backend and specialist service. That is agent-to-agent communication in a general sense, but it is **not currently an implementation of the formal A2A protocol**. This guide explains both the general idea and the exact project implementation without calling one the other.

## 1. Start With the Simplest Picture

Imagine a person asks a travel desk: “Plan me a trip to Tokyo.” The travel desk does not do every job itself. It asks:

- a flight specialist to find flights,
- a hotel specialist to find accommodation,
- a local guide specialist to suggest places to visit.

Each specialist has a different job. They need a way to receive a request, understand what is being asked, and send useful results back. In software, a message crosses a boundary from one independently running agent or service to another. That pattern is called **agent-to-agent communication**, often shortened to **A2A**.

An agent does not have to be a robot or a special kind of server. For this explanation, an agent is a software component that uses instructions, logic, and possibly an AI model to work on a task. A service is a program that can receive network requests. An agent can be hosted inside a service.

The word **protocol** means the agreed rules for communicating: where to send a request, what information it must contain, how the receiver reports success or failure, and how follow-up work is identified. HTTP is one protocol computers use to send requests. A2A is a higher-level protocol designed around communication between agents.

### A Helpful Analogy

Suppose two companies want their employees to work together:

- Without a shared process, Company A writes a custom email for Company B, Company B writes a custom spreadsheet reply, and both sides manually translate every field. A new company requires another custom integration.
- With an agreed business protocol, each side knows how to describe capabilities, submit work, identify the work later, report progress, ask questions, and return deliverables.

The formal A2A protocol is a shared software contract for the second situation. It does not make agents intelligent by itself. It gives independently built agents a common way to communicate.

## 2. Three Things That Sound Similar

People often use “A2A” to refer to several different things. Keep these separate:

| Phrase | What it means |
| --- | --- |
| Agent-to-agent collaboration | One software agent asks another software agent to do some work. This is a broad architecture pattern. |
| HTTP service call | One program sends an HTTP request to another program. This is a network transport pattern. The endpoint and JSON format may be custom. |
| A2A Protocol | A published open standard for agent interoperability, with defined discovery information, message/task structures, methods, and interaction rules. |

An HTTP `POST` from one agent to another is not automatically the A2A Protocol. It becomes an A2A Protocol implementation only when both sides follow the standard's contracts. AstroWeave currently implements the first two rows, not the third.

## 3. Why Have A2A At All?

If one program already has all the code it needs, another agent is not automatically useful. A2A becomes useful when work is split across independently owned, deployed, or built agents.

For example, a company may have:

- its own scheduling agent,
- a vendor's payment agent,
- a third-party travel agent,
- an internal compliance agent.

Those agents may use different programming languages, model providers, frameworks, databases, and hosting platforms. A shared protocol can reduce the number of custom integrations each team has to maintain.

### What a Shared Protocol Can Provide

- **A common request shape:** clients do not need to invent a new JSON schema for every remote agent.
- **Capability discovery:** a client can learn what a remote agent says it can do before sending work.
- **Trackable work:** longer tasks can have IDs and report states such as working, completed, failed, or waiting for input.
- **A common way to return results:** messages and structured artifacts can represent text, JSON data, files, images, or other output.
- **Different communication styles:** a simple request/response can be used for quick work; streaming or later notifications can be used for longer work.
- **Framework independence:** the caller and remote agent do not have to use the same agent framework.

These are protocol capabilities, not automatic guarantees. Teams still need to authenticate callers, authorize access, protect data, monitor failures, and decide which agents they trust.

### What A2A Does Not Do

A2A does not:

- build the agent's reasoning or decide which model it should use;
- replace the agent framework, such as LangGraph;
- make an unsafe agent safe just because it uses the protocol;
- replace agent-to-tool interfaces such as MCP;
- guarantee that two agents understand a task identically just because they can exchange messages.

The remote agent remains responsible for its own internal logic. The caller interacts with the remote agent through the agreed external interface.

## 4. The Main Roles

The formal A2A model can be understood using three roles:

1. **User:** the person or program with a goal.
2. **Client agent:** the agent or application acting for the user. It chooses which remote agent to contact and sends the request.
3. **Remote agent / A2A server:** the independent agent that receives the request and performs work.

For one AstroWeave run, a useful analogy is:

| A2A concept | Closest AstroWeave role |
| --- | --- |
| User | The account holder asking the astrology question. |
| Client/orchestrating side | AstroWeave's FastAPI connector, orchestrator graph, and dispatcher acting together. |
| Remote agent side | `astroweave.specialist_service:app` when the specialist is configured to run separately. |
| Specialist capability | One of career, finance, love, or sports. |

The mapping is approximate because the current AstroWeave remote interface is not the formal protocol.

## 5. Formal A2A Building Blocks in Plain Language

The formal protocol has more structure than “send JSON and get JSON.” The following concepts explain why.

### Agent Card: A Digital Capability Card

An **Agent Card** is a JSON description of a remote agent. It acts like a service's public business card. It can tell a client:

- the agent's name and description;
- the endpoint URL to contact;
- the skills or kinds of work it offers;
- the input and output content types it accepts;
- which protocol features it supports, such as streaming;
- what authentication scheme is required.

The client can inspect the card before deciding whether that agent is appropriate. The formal A2A discovery convention includes a well-known URL such as `/.well-known/agent-card.json`; a system can also use a private registry or direct configuration, depending on its deployment.

**AstroWeave today:** it does not publish or fetch an Agent Card. Its connector already knows the specialist names from `SPECIALIST_REGISTRY`, and a server administrator maps a name to a base URL in `ASTROWEAVE_SPECIALIST_URLS`.

### Skill: A Named Capability

A **Skill** describes a particular kind of work offered by an agent. A career agent might advertise “career guidance from chart data.” A client can use that description to choose the agent.

**AstroWeave today:** the specialist registry has names and descriptions in Python code, but it does not expose formal A2A `AgentSkill` records to remote clients.

### Message and Part: The Communication

A **Message** is one turn of communication. It has a sender role and content. The content is divided into **Parts**, which can represent text, structured JSON, or file data. Parts allow the protocol to carry more than a single plain-text prompt.

**AstroWeave today:** it sends one application-specific JSON object with fields like `user_query`, `messages`, and `chart_data`. It does not wrap those fields in a formal A2A `Message` and `Part` structure.

### Task: A Trackable Piece of Work

A formal A2A **Task** is a unit of work with an ID, status, and possibly output artifacts. It is helpful when work takes time, can be resumed, can ask for more input, or needs to be checked later.

The remote agent may respond immediately for simple work or create a task for longer work. A task can move through states such as submitted, working, input-required, completed, failed, canceled, or rejected. Exact state names and transitions are defined by the protocol version.

**AstroWeave today:** the `/specialists/{specialist_name}/run` request waits for the specialist graph to finish and then returns its state in one HTTP response. It does not create or expose an A2A Task ID, task-status endpoint, streaming updates, or an A2A task lifecycle.

### Artifact: The Deliverable

An **Artifact** is a concrete output from a task, such as a report, document, image, or structured result. A task can return one or more artifacts, and an artifact can contain multiple parts.

**AstroWeave today:** the specialist returns a `specialist_results` list containing `analysis`, `conclusion`, and `confidence`. Those are ordinary JSON fields, not formal A2A Artifacts.

### Context and Task IDs

In formal A2A, a context identifier can group related interactions, while task identifiers identify individual units of work. A client can use them to refer to a conversation and to a particular task without asking the server to expose its internal memory.

**AstroWeave today:** the connector has conversation/session/message IDs for its own API and durable conversation store. It does not send formal A2A `contextId` or `taskId` fields to the specialist service.

### Transport and Interaction Pattern

The A2A specification defines how protocol requests and responses are represented over supported transports. The current protocol uses JSON-RPC-style method calls over HTTP(S); the standard includes message submission and options for synchronous responses, streaming updates, and longer-running work patterns.

**AstroWeave today:** it uses a normal custom HTTP `POST` with a JSON body. It does not use the formal A2A JSON-RPC envelope or standard method names.

## 6. A2A and MCP Are Different Jobs

These two terms are related but not interchangeable:

| Question | A2A | MCP |
| --- | --- | --- |
| Main connection | Agent to another agent | Agent/model to a tool or data source |
| Example | “Career agent, analyze this request and return your specialist findings.” | “Call the chart calculation tool with these birth details.” |
| Remote side | Another agent that can reason and manage its own work | A defined tool/resource interface |
| Typical project use | Delegate a substantial or independently owned capability | Give an agent access to a specific function, API, or resource |

An agent may use MCP tools internally and also communicate with another agent through A2A. The standards solve different boundaries.

**AstroWeave today:** the dispatcher calls the chart service through its own HTTP client. The chart service is a calculation service, not one of the A2A-style specialist agents. The code also defines tool registry abstractions, but the current specialist tools are empty and there is no LLM tool-calling loop.

## 7. What AstroWeave Implements Today

The relevant code is:

- [`src/astroweave/orchestration/dispatcher/dispatcher.py`](../src/astroweave/orchestration/dispatcher/dispatcher.py): builds specialist input and chooses local versus remote execution.
- [`src/astroweave/specialist_service.py`](../src/astroweave/specialist_service.py): exposes the remote specialist HTTP endpoint and validates/dispatches its request.
- [`src/astroweave/graphs/specialist/specialist_graph.py`](../src/astroweave/graphs/specialist/specialist_graph.py): runs the specialist workflow.
- [`src/astroweave/agents/specialists/__init__.py`](../src/astroweave/agents/specialists/__init__.py): lists registered specialist names and prompts.
- [`src/astroweave/common/security/tokens.py`](../src/astroweave/common/security/tokens.py): creates and verifies signed bearer tokens.
- [`tests/unit/test_dispatcher.py`](../tests/unit/test_dispatcher.py) and [`tests/integration/test_api.py`](../tests/integration/test_api.py): exercise remote dispatch and the specialist service.

The dispatcher supports two execution modes:

| Mode | Setting | What Python does |
| --- | --- | --- |
| In-process | No URL for the specialist in `ASTROWEAVE_SPECIALIST_URLS` | Calls `_get_specialist_graph().invoke(...)` directly. The graph runs in the connector's process. |
| Remote HTTP | A URL exists for the specialist in `ASTROWEAVE_SPECIALIST_URLS` | Sends an HTTP `POST` to that service's `/specialists/{name}/run` endpoint and waits for its JSON response. |

This selection is per specialist. For example, `career` can run remotely while `finance` still runs in-process.

The word “A2A” in this guide's project discussion means the remote HTTP handoff pattern unless explicitly called **formal A2A**. More precisely, the current code is a custom remote specialist API inspired by the need for agent-to-agent communication.

## 8. What Changes With and Without the Remote Handoff?

The application can obtain the same specialist result either way. What changes is where the specialist graph executes and whether a network boundary is crossed.

| Concern | Without remote handoff | With AstroWeave's remote handoff |
| --- | --- | --- |
| Specialist location | Same Python process as the connector | Separate HTTP service/process, possibly another host |
| Call mechanism | Python function / graph invocation | HTTP request, JSON serialization, network response |
| Deployment | One backend process can run everything | Connector and specialist service can be deployed separately |
| Failure modes | Python exceptions and local resource failures | Also network timeout, DNS/connectivity, HTTP error status, authentication mismatch, and remote process failure |
| Scaling | Scale the connector and all its specialist work together | Scale a specialist service independently, subject to deployment setup |
| Framework boundary | Same Python code and installed dependencies | Can become a framework/language boundary, though this current custom JSON contract still needs both sides to follow AstroWeave's schema |
| Protocol discovery | Not applicable | Still static configuration; the current code does not discover remote capabilities dynamically |
| Task progress | Wait for local graph call to finish | Wait for HTTP response; no streaming or task polling in current implementation |

Remote execution does not inherently make the answer better. It is an architectural choice for process separation, deployment, ownership, or scaling. If one application owns all the agents and has no need to separate them, the in-process path is simpler and avoids network overhead.

## 9. The Actual AstroWeave Call, Step by Step

Here is the path when an ordinary `/run` request is classified as a career question and the career service URL is configured:

1. **The connector receives the user's question.** `POST /run` in [`src/astroweave/api/main.py`](../src/astroweave/api/main.py) validates the request, checks the user's bearer token, loads the user's profile and conversation history, and invokes the orchestrator graph.
2. **The orchestrator chooses a specialist.** `classify-request` asks the configured orchestrator LLM to choose from registered specialists. In this example it selects `career`. The task planner forms the task stage.
3. **The dispatcher prepares specialist input.** `execute_specialist()` in `dispatcher.py` ensures there is chart data, then builds `handoff` with the question, history, task name, methodology, chart, and prior dependency findings.
4. **The dispatcher checks its routing configuration.** It parses `ASTROWEAVE_SPECIALIST_URLS`. If there is a `career` URL, it uses HTTP. If not, it invokes the local specialist graph directly.
5. **The connector signs an identity token.** It creates a short bearer token for the authenticated username using the shared secret configured for the services.
6. **The specialist service receives the HTTP request.** `specialist_service.py` validates the request body, verifies the bearer token, and checks that `career` is in `SPECIALIST_REGISTRY`.
7. **The specialist graph executes.** The service sets `current_task` from the URL path and invokes the graph, passing the verified user in runtime context. Its executor selects the career prompt, calls that specialist's LLM, parses its JSON, and returns `specialist_results` or `errors`.
8. **The dispatcher receives the JSON.** It checks the HTTP status, parses the JSON response, and extracts the result/error arrays. Any remote exception becomes an error for that specialist rather than automatically crashing the entire request.
9. **The orchestrator finishes.** It collects the specialist result, asks its own synthesizer for a final answer, and returns final state to the API. The API persists the user/assistant turn and sends the response to the caller.

For the direct `app_id` fastpath, the API skips the orchestrator classifier/planner/synthesizer and calls `execute_specialist()` directly. The URL configuration still controls whether that specialist runs locally or through the remote service. **Fastpath and remote HTTP are separate switches that can be combined.**

## 10. Exact AstroWeave HTTP Contract

The connector's configuration looks like this:

```sh
ASTROWEAVE_SPECIALIST_URLS='{"career":"http://127.0.0.1:8200"}'
```

The dispatcher constructs a request like this:

```http
POST /specialists/career/run HTTP/1.1
Host: 127.0.0.1:8200
Authorization: Bearer <signed-token-for-authenticated-user>
Content-Type: application/json
```

The handoff body from `execute_specialist()` has this shape:

```json
{
  "user_query": "How should I approach my next career move?",
  "messages": [],
  "current_task": "career",
  "methodology": "vedic",
  "chart_data": {
    "d1": {
      "sample": "chart"
    }
  },
  "dependency_results": []
}
```

These are the request fields built by the dispatcher. `messages` may contain prior turns, `chart_data` is normally the chart service response, and `dependency_results` can contain findings from prerequisite specialists. The example values above come from the executed demonstration and are test data, not an actual person's chart.

There is an implementation detail worth noticing: `current_task` is included in the dispatched JSON, but `SpecialistRequest` in `specialist_service.py` does not declare it. Pydantic ignores the extra field under its current default settings. The service instead treats the URL's `{specialist_name}` as authoritative and inserts that value as `current_task` before invoking the graph. This prevents a body field from changing which registered specialist the route runs.

The remote endpoint's direct response is the specialist graph's state. A simplified excerpt is:

```json
{
  "specialist_results": [
    {
      "specialist": "career",
      "analysis": "The sample chart indicates a period for careful planning.",
      "conclusion": "Review options before making a major move.",
      "confidence": "medium"
    }
  ],
  "errors": []
}
```

The API's final `/run` response is a different, outer response. It includes the synthesized `answer`, the conversation/session IDs, graph `state`, and `execution_trace` (currently an empty list). The specialist's JSON result is nested inside that final state.

### What the Receiver Validates

`SpecialistRequest` requires:

| Field | Type / default | Purpose |
| --- | --- | --- |
| `user_query` | string, required | The question assigned to the specialist. |
| `messages` | list of dictionaries, default `[]` | Prior conversational messages. |
| `methodology` | string, default `vedic` | Analytical method selected by the caller. |
| `chart_data` | dictionary, required | Chart data already fetched by the connector. |
| `dependency_results` | list of dictionaries, default `[]` | Relevant results from prerequisite specialists. |

The HTTP route also validates the bearer token and registered specialist name. Missing/invalid authentication returns `401`; an unregistered name returns `404`; invalid or incomplete request JSON is rejected by FastAPI with `422`.

## 11. A Real Executed Comparison: Remote vs Local

I ran the same question through both modes using the workspace's selected Python environment. The run used:

```text
Question: How should I approach my next career move?
Selected specialist: career
Methodology: vedic
Sample chart: {"d1": {"sample": "chart"}}
Specialist result: Review options before making a major move. (medium confidence)
Synthesized answer: A practical career reading.
```

### Remote Mode: What Actually Crossed HTTP

For the first `/run`, I configured the dispatcher to use a temporary local specialist-service URL. The log showed a real request to:

```text
POST http://127.0.0.1:<temporary-port>/specialists/career/run
```

The temporary service received the question, task name `career`, methodology `vedic`, an empty history list, the sample chart dictionary, and an empty dependency-results list. It accepted the signed bearer token and returned a `200` response. The dispatcher then returned the specialist result to the orchestrator, which synthesized the final answer.

Observed connector response excerpt:

```json
{
  "answer": "A practical career reading.",
  "state": {
    "specialist_results": [
      {
        "specialist": "career",
        "analysis": "The sample chart indicates a period for careful planning.",
        "conclusion": "Review options before making a major move.",
        "confidence": "medium"
      }
    ],
    "history_persisted": true
  },
  "execution_trace": []
}
```

The bearer token itself is deliberately not printed or documented. The example used a temporary secret and temporary user/conversation databases, all removed when the execution ended.

### Local Mode: Same Work Without the Network Call

For the second `/run`, I removed the `career` entry from `ASTROWEAVE_SPECIALIST_URLS`. The dispatcher then used `_get_specialist_graph().invoke(...)` inside the connector process. It did not send a request to the temporary specialist service.

The response was also HTTP `200`, and the user-visible answer and specialist result were the same:

```json
{
  "answer": "A practical career reading.",
  "specialist_results": [
    {
      "specialist": "career",
      "conclusion": "Review options before making a major move.",
      "confidence": "medium"
    }
  ]
}
```

The capture showed **one specialist-service request** across the two runs: one for remote mode and zero for local mode. The chart client stub was called once per separate `/run`, because each request is a separate graph run and each began without chart data in its graph state.

### What Was Real and What Was Simulated

The following pieces ran as real project code:

- FastAPI `/auth/register` and `/run` routes;
- a real temporary SQLite account database and conversation store;
- bearer-token creation and verification using a temporary shared secret;
- orchestrator graph classification, task planning, and synthesis nodes;
- dispatcher branch selection;
- a real temporary Uvicorn specialist service on an ephemeral loopback port;
- a real HTTP POST from the dispatcher to the specialist service;
- remote route validation and specialist graph invocation;
- in-process specialist graph invocation for the comparison run;
- response assembly and conversation persistence.

To make the test deterministic and independent of commercial credentials, the orchestrator/specialist LLM responses and chart calculation were replaced with fixed test doubles. So the network boundary, auth flow, request contract, graph paths, and persistence were exercised, while the actual AI-generated reasoning and astronomical chart calculation were not. This is a practical end-to-end transport test, not a live astrology reading.

## 12. How to Run the Remote Service Locally

The repository README contains the standard development setup. At a high level, run the specialist service separately and configure the connector with its URL.

### Terminal A: Start a Specialist Service

```sh
export ASTROWEAVE_AUTH_SECRET='use-the-same-long-random-secret-in-both-processes'
PYTHONPATH=src uvicorn astroweave.specialist_service:app --host 127.0.0.1 --port 8200
```

### Terminal B: Configure and Start the Connector

```sh
export ASTROWEAVE_AUTH_SECRET='use-the-same-long-random-secret-in-both-processes'
export ASTROWEAVE_SPECIALIST_URLS='{"career":"http://127.0.0.1:8200"}'
PYTHONPATH=src uvicorn astroweave.api.main:app --host 127.0.0.1 --port 8000
```

Both processes must use the same authentication secret. In a real deployment, use HTTPS between machines and store the secret in a secrets manager. Do not use AstroWeave's known development-only fallback secret in production.

This setup assumes the account/profile, LLM provider, and chart service requirements for `/run` are already configured. The minimal specialist-service endpoint can be tested separately with an authenticated JSON request, but a full `/run` also needs the normal connector prerequisites.

### What Changes When You Add the URL?

Adding a URL does not change which specialist the orchestrator selects. It changes only the dispatch location:

```text
No career URL: career graph runs inside connector process.
Career URL set: connector POSTs to remote career service and waits for JSON.
```

The environment variable is a routing map, not a list of enabled capabilities. The specialist must still exist in the connector's registry, and the remote service must also have that specialist registered.

## 13. Failure Cases to Understand

Remote execution introduces extra ways for a request to fail:

- **Bad URL map JSON:** the connector cannot parse `ASTROWEAVE_SPECIALIST_URLS`; that specialist returns an error through dispatcher handling.
- **Configured service is unavailable:** connection errors and the 90-second timeout are caught and recorded as a specialist failure.
- **Remote service returns an HTTP error:** `raise_for_status()` converts it into a caught specialist failure.
- **Authentication secret mismatch:** the remote service rejects the connector's token with `401`.
- **Unknown specialist at receiver:** the remote service returns `404`.
- **Invalid handoff fields:** FastAPI request validation returns `422`.
- **Remote model call fails or returns malformed JSON twice:** the specialist graph records an error; the dispatcher returns it to orchestration.

The dispatcher catches remote-call exceptions so one remote specialist failing need not fail unrelated specialists. The orchestrator can synthesize from successful results and retain errors in the final state. If there are no usable specialist results, the final answer is formed from the errors.

Local execution avoids network and remote-authentication failures, but it does not avoid model errors, chart errors, or process resource limits. It also means connector and specialist workloads scale and deploy together.

## 14. AstroWeave Custom Handoff vs Formal A2A

| Capability | AstroWeave custom HTTP today | Formal A2A Protocol |
| --- | --- | --- |
| Request transport | HTTP POST via `httpx` | Standard protocol methods over supported HTTP-based transports |
| Request envelope | AstroWeave-specific JSON fields | Standard message/task structures and protocol envelope |
| Agent discovery | Static environment variable maps a specialist name to a URL | Agent Card discovery or another agreed discovery mechanism |
| Capability description | Python registry names/descriptions, not exposed as a remote standard card | Agent Card describes identity, endpoint, authentication, capabilities, and skills |
| Specialist result | LangGraph state JSON with `specialist_results`/`errors` | Standard Message or Task response, with Parts and optional Artifacts |
| Long-running work | One synchronous request waits up to 90 seconds | Task lifecycle; clients can receive/poll updates and use supported streaming/push patterns |
| Follow-up task IDs | Uses AstroWeave conversation/session/message IDs at connector API; no A2A task IDs | Standard context and task identifiers group related work and identify individual tasks |
| Interoperability | Both ends must know AstroWeave's custom schema and endpoint | Independent compliant clients/servers can use a common contract |
| Framework independence | Possible operationally, but contract is custom | Designed to interoperate across agent frameworks and vendors |

Therefore, the precise current description is **remote specialist HTTP dispatch** or **A2A-style agent handoff**, not “AstroWeave implements A2A.” The former is a real and useful architecture step; the latter would require implementing or adopting the actual protocol.

## 15. When Would Formal A2A Be Worth Adding Here?

The current custom request is small and fits the present topology: one connector knows a small fixed set of specialists, and each request waits for the specialist to finish. A formal protocol would become more useful if AstroWeave needs to:

- connect to specialist agents owned by another team or vendor;
- allow independently built agents to advertise their skills and endpoint;
- replace static URL maps with interoperable discovery;
- support work lasting longer than a normal HTTP request;
- track specialist task status, ask the user a follow-up question, or resume a task;
- stream partial progress or notify the connector when work completes;
- exchange richer deliverables than the current JSON conclusion fields;
- let different agent frameworks participate without each learning AstroWeave's private request format.

Before adopting the standard, the project would need to decide how the existing domain registry maps to Agent Cards and Skills, how auth requirements are declared and provisioned, how AstroWeave conversation/session IDs relate to A2A context/task IDs, and how specialist results/errors become standard Messages, Tasks, and Artifacts. This guide does not make that migration; it documents the current behavior accurately.

## 16. A Short Glossary

| Word | Beginner definition |
| --- | --- |
| Agent | Software that can use instructions and logic, often with an AI model, to work toward a goal. |
| Agent-to-agent | One agent asks another agent to help with work. |
| Protocol | Shared rules for how software requests and responses must be shaped and understood. |
| Remote service | A program reachable at another network address or in another process. “Remote” can still mean another process on your own laptop. |
| Endpoint | A URL path where a service accepts a particular kind of request. |
| JSON | A text format for representing objects and lists so different programs can exchange structured data. |
| Authentication | Checking who is making a request. AstroWeave uses a signed bearer token for these endpoints. |
| Agent Card | In formal A2A, a JSON description of an agent's identity, endpoint, skills, features, and auth requirements. |
| Task | In formal A2A, a trackable unit of work with an ID and lifecycle/status. |
| Artifact | In formal A2A, a concrete result of a task, such as a document or structured output. |
| In-process call | A direct function/graph invocation inside the current Python process; no HTTP request is sent. |
| A2A-style | A useful description of agent collaboration over an application-specific interface; not proof of conformance to the A2A standard. |

## 17. Reliable References

The project-specific facts in this document are based on the source files and executed comparison listed above. For formal A2A concepts and current protocol details, use the official A2A documentation as the authority:

- [A2A Protocol overview](https://a2a-protocol.org/latest/)
- [What is A2A?](https://a2a-protocol.org/latest/topics/what-is-a2a/)
- [Core concepts and components](https://a2a-protocol.org/latest/topics/key-concepts/)
- [Life of a task](https://a2a-protocol.org/latest/topics/life-of-a-task/)
- [Agent discovery and Agent Cards](https://a2a-protocol.org/latest/topics/agent-discovery/)
- [A2A specification](https://a2a-protocol.org/latest/specification/)

Protocol versions evolve. When implementing a formal A2A client or server, check the versioned specification and SDK documentation rather than copying a request example from this explanation.
