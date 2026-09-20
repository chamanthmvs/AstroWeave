# AstroWeave

> An in-progress hierarchical multi-agent astrology system built with LangGraph.

AstroWeave is an AI-powered astrology system where a central **Astrologer Manager** coordinates specialized astrologer agents to analyze user questions, select relevant methodologies, evaluate results, and produce a coherent final response.

## Architecture

```text
User Question
      |
      v
Resolve Conversation Context (placeholder)
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
```

## Core Concepts

- **Hierarchical orchestration:** a top-level manager invokes independently structured specialist subgraphs.
- **Domain specialization:** specialists focus on areas such as sports, relationships, career, education, and finance.
- **Methodology separation:** Vedic and KP are analysis methodologies, not ordinary domain specialists.
- **Queue-driven execution:** planned specialist tasks execute one at a time, are collected transparently, and continue until the queue is empty.
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

The v1 flow is wired end-to-end: a Streamlit question reaches the FastAPI
backend, an LLM-driven request classifier selects domain specialists, the task
planner creates a queue, and each specialist subgraph runs before response
synthesis produces one answer. Conversation-context resolution is currently an
explicit placeholder. The knowledge/RAG layer and methodology-specific Vedic/KP
logic are not implemented yet.

The fuller implementation snapshot and roadmap are published in the
[here](https://chamanthmvs.github.io/AstroWeave/).

## Local Development

Install the root dependencies, configure an LLM provider with environment
variables, then run the backend and UI in separate terminals:

```bash
pip install -r requirements.txt
export ASTROWEAVE_LLM_PROVIDER=groq
export ASTROWEAVE_LLM_MAX_TOKENS=4096
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
