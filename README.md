# AstroWeave

> An in-progress hierarchical multi-agent astrology system built with LangGraph.

AstroWeave is an AI-powered astrology system where a central **Astrologer Manager** coordinates specialized astrologer agents to analyze user questions, select relevant methodologies, evaluate results, and produce a coherent final response.

## Architecture

```text
User Question
      |
      v
Resolve Conversation Context
      |
      +-- invalid query ------------------------------+
      |                                               |
      v                                               v
Classify Request                              Synthesize Response
      |                                               ^
      v                                               |
Plan Specialist Tasks --> Select Next Task -- queue empty --+
                         |
                         v
                    Run Specialist
                         |
                         v
               Specialist Subgraph
                         |
                         v
             Collect Specialist Result
                         |
                         +-- tasks remain --> Select Next Task
                         |
                         +-- queue complete --> Synthesize Response
                                                    |
                                                    v
                                      Persist Conversation Turn
                                                    |
                                                    v
                                              Final Answer
```

## Core Concepts

- **Hierarchical orchestration:** a top-level manager invokes independently structured specialist subgraphs.
- **Domain specialization:** specialists focus on areas such as sports, relationships, career, education, and finance.
- **Methodology separation:** Vedic and KP are analysis methodologies, not ordinary domain specialists.
- **Queue-driven execution:** planned specialist tasks execute one at a time, are collected transparently, and continue until the queue is empty.
- **Two-scope history:** current-session messages and prior-session conversation messages are loaded separately from SQLite and supplied as bounded context.
- **Durable transcripts:** completed user/assistant turns are persisted atomically and can be resumed or deleted.
- **Extensible design:** new domains, methodologies, tools, and knowledge sources can be added independently.

## Example Flow

For a question such as *“Will I get a new job this year?”*, AstroWeave can identify the Career domain, select Vedic, KP, or both methodologies, invoke the Career Specialist, evaluate the analysis, and synthesize the final response.

## Technology

- Python
- LangGraph
- LangChain
- Large language models
- Retrieval and knowledge bases
- Tool-based agent execution

## Current Status

**This project is still in progress and is not production-ready.**

The v2 flow is wired end-to-end: a Streamlit question reaches the FastAPI
backend, an LLM-driven request classifier selects domain specialists, the task
planner creates a queue, and each specialist subgraph runs before response
synthesis produces one answer. Conversation-context resolution is now an
implemented SQLite-backed stage with separate session and prior-conversation
windows. The knowledge/RAG layer, rolling summaries, cross-conversation memory,
and methodology-specific Vedic/KP logic are not implemented yet.

The fuller implementation snapshot and roadmap are published in the
[here](https://chamanthmvs.github.io/AstroWeave/).

For the complete functional behavior, architecture, API and state contracts,
security assessment, operations guide, and implementation roadmap, see the
[project documentation](docs/PROJECT_DOCUMENTATION.md).

## Local Development

Install the root dependencies, configure an LLM provider with environment
variables, then run the backend and UI in separate terminals:

```bash
pip install -r requirements.txt
export ASTROWEAVE_LLM_PROVIDER=groq
export ASTROWEAVE_LLM_MAX_TOKENS=4096
export ASTROWEAVE_SESSION_HISTORY_LIMIT=12
export ASTROWEAVE_CONVERSATION_HISTORY_LIMIT=8
export ASTROWEAVE_REQUEST_CLAIM_TTL_SECONDS=1800
export ASTROWEAVE_AUTH_SECRET=replace-with-a-long-random-secret
export GROQ_API_KEY=your_key_here
PYTHONPATH=src uvicorn astroweave.api.main:app --reload
streamlit run app/streamlit_app.py
```

The `/run` endpoint also requires the chart service:

```bash
cd chart_service
pip install -r requirements.txt
uvicorn main:app --port 8100
```

Never commit `.env` files, API keys, or local user databases. Use your
hosting provider's secret manager for deployments.

JSON-producing LLM calls are retried once when a provider returns malformed or
truncated output. Logs include the attempt number, response length, and finish
reason. `ASTROWEAVE_LLM_MAX_TOKENS` can be overridden by role or specialist
using the same suffix precedence as the other LLM settings.
