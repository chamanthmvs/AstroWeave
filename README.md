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
- **Domain specialization:** career, finance, love, and sports specialists answer questions about their area; a general specialist reads the person as a whole (personality, strengths, life direction) and covers areas without a dedicated specialist, such as education, family, children, health constitution, and travel abroad.
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
- Claude (Opus 5.5 by default) via the official Anthropic SDK; OpenAI and Groq remain selectable
- PyJHora (Swiss Ephemeris) in an isolated chart service
- Retrieval and knowledge bases
- Tool contracts and per-agent registries (LLM-directed tool execution is not wired yet)

## Current Status

**This project is still in progress and is not production-ready.**

The connector owns accounts, conversation IDs, history, and persistence. A
Streamlit question reaches `/run`, where the orchestrator plans dependency
stages: independent specialists run concurrently; dependent specialists wait
for prior findings. A configured app ID can route directly to a specialist,
skipping planning and synthesis. Specialists run locally by default or through
an optional authenticated HTTP service. The knowledge/RAG layer, rolling summaries, cross-conversation memory,
and methodology-specific Vedic/KP logic are not implemented yet.

The fuller implementation snapshot and roadmap are published in the
[here](https://chamanthmvs.github.io/AstroWeave/).

For the complete functional behavior, architecture, API and state contracts,
security assessment, operations guide, and implementation roadmap, see the
[project documentation](docs/PROJECT_DOCUMENTATION.md).

For the visual, chapter-by-chapter beginner's book covering the whole system,
start at [AstroWeave, Explained](docs/ASTROWEAVE_BOOK.md). Its tool chapter
explains the difference between registered tools, Python function calls, and
LLM-directed tool execution.

## Local Development

Install the project (editable), configure an LLM provider with environment
variables, then run the backend in one terminal and the chart service in
another. The package is installable, so there is no `PYTHONPATH` to set:

```bash
pip install -e ".[dev]"          # runtime deps + pytest; or `pip install -r requirements.txt`
export ANTHROPIC_API_KEY=your_key_here   # Claude Opus 5.5 is the default model
export ASTROWEAVE_SESSION_HISTORY_LIMIT=12
export ASTROWEAVE_CONVERSATION_HISTORY_LIMIT=8
export ASTROWEAVE_REQUEST_CLAIM_TTL_SECONDS=1800
export ASTROWEAVE_AUTH_SECRET=replace-with-a-long-random-secret
uvicorn astroweave.api.main:app --reload
```

The backend serves a self-contained web UI (a dependency-free single-page app in
`frontend/`, with a light/dark toggle) from the same origin at
`http://127.0.0.1:8000/`. Open that in a browser once the chart service and
backend are running.

> **VS Code:** open the *Run and Debug* panel, choose **▶ AstroWeave: all
> services**, and press play to launch the chart service and backend together
> (configs live in `.vscode/`). Run tests with the **Run tests** task.

The connector creates conversation/session IDs on the first request and returns
them for follow-ups. For an optional direct career route, set
`ASTROWEAVE_APP_ROUTES='{"career-app":"career"}'` on the connector and send
`"app_id":"career-app"` to `/run`. To deploy career separately, run
`uvicorn astroweave.specialist_service:app --port 8200` with a
shared `ASTROWEAVE_AUTH_SECRET`, and configure the connector with
`ASTROWEAVE_SPECIALIST_URLS='{"career":"http://127.0.0.1:8200"}'`.

The `/run` endpoint also requires the chart service (if it is unreachable,
`/run` responds with a clear **HTTP 503** rather than a vague failure):

```bash
cd chart_service
pip install -r requirements.txt
uvicorn main:app --port 8100
```

Never commit `.env` files, API keys, or local user databases. Use your
hosting provider's secret manager for deployments.

### LLM configuration

Every setting resolves most-specific-first: `ASTROWEAVE_LLM_<SETTING>_<AGENT>`
(e.g. `_CAREER`), then `_<ROLE>` (`_SPECIALIST` / `_ORCHESTRATOR`), then the
global `ASTROWEAVE_LLM_<SETTING>`.

| Setting | Default | Notes |
|---|---|---|
| `PROVIDER` | `anthropic` | also `openai`, `groq` (needs `GROQ_API_KEY`) |
| `MODEL` | `claude-opus-5-5` | `openai/gpt-oss-120b` when the provider is `groq` |
| `EFFORT` | `high` for specialists, `medium` for routing/synthesis | Claude only: `low`, `medium`, `high`, `xhigh`, `max` |
| `MAX_TOKENS` | `64000` for Claude, `4096` otherwise | Claude's thinking counts toward this; requests are streamed |
| `TEMPERATURE` | `0.2` | ignored by Claude, whose current models do not accept it |

Claude requests use adaptive thinking, prompt caching for the long specialist
prompts, structured outputs (JSON schemas) for routing and specialist replies,
and server-side refusal fallbacks. Other providers' JSON replies are retried
once when malformed or truncated.

### Accounts and password reset

Accounts use SQLite with scrypt password hashing. A signed-in user can change
their password at `POST /auth/change-password` (and from the sidebar in the UI).
For a forgotten password, `POST /auth/request-reset` always returns the same
response (so it can't reveal which emails exist) and mints a short-lived,
single-use reset token. There is no email provider wired up, so the token is
logged for the operator and an **admin** can mint one to hand over via
`POST /admin/reset-token`; the user completes the reset at `POST /auth/reset`
(or the “Forgot password?” flow in the UI). The token is bound to the current
password hash, so it stops working the moment the password changes. Wire an
email sender later to deliver the token automatically.

### Your profile (deterministic)

`GET /me/profile` returns a fixed classical profile from the user's Moon Nakshatra
(+ pada), Moon Rasi and Lagna: ruling planet, deity, symbol, gana, yoni, nadi,
element, modality and varna, plus a plain-language summary a non-astrologer can
read and a caveat that the full chart modulates these archetypes. Pure lookup, no
LLM (`astroweave.common.astro.build_profile`); the UI has a 'Your profile' screen.

### Kundli matching (Guna Milan)

`POST /match` computes marriage compatibility between the signed-in user and a
partner's birth details: the **North-Indian 36-point Ashtakoota** (Varna, Vasya,
Gana, Tara, Yoni, Graha Maitri, Bhakoot, Nadi), the **South-Indian 10 poruthams**,
and **Manglik (Kuja) dosha** for each person. The scores come from PyJHora's
validated Ashtakoota engine in the chart service (`/match`); `chart_service/test_match.py`
holds the engine to classical rules across all 27x27 nakshatra pairs and corrects a
PyJHora typo in the South rajju neck group. The UI has a dedicated **Kundli matching**
screen (partner form + geocode) that renders the full breakdown. `GET /me/chart`
returns the user's **Rasi, Nakshatra, and Lagna**, shown in a persistent left panel.

Run the matching validation tests (they need the chart service's own venv, which has PyJHora):

```bash
cd chart_service && ./.venv/bin/python test_match.py
```

### Rate limiting

Because every `/run` spends money on the LLM provider's key, the endpoint has a
per-user daily cap (default **50 runs/day**, UTC) and an optional global
backstop. Idempotent replays of an already-answered request do not count.

| Setting | Default | Notes |
|---|---|---|
| `ASTROWEAVE_RATE_LIMIT_PER_DAY` | `50` | per-user cap; `0` disables it |
| `ASTROWEAVE_RATE_LIMIT_GLOBAL_PER_DAY` | `0` (off) | cap across all users; set a number for a hard spend ceiling |

Over the cap, `/run` returns **HTTP 429** (`code: rate_limited`) with a
`Retry-After` header. `GET /usage` reports the signed-in user's runs used and
remaining today. Counts live in the same SQLite database (`usage_daily` table).

### Token usage and cost

Each run's token usage is captured from every model call (routing, each
specialist, synthesis) and written to the `usage_events` table — one row per
model per run, with the dollar cost computed from an editable per-model price
table at write time. Only counts, model names, ids and cost are stored, never
the text of a question or answer. This is the data behind per-user spend
reporting and cost-aware evaluations.

### Admin dashboard

Set `ASTROWEAVE_ADMIN_EMAILS` (comma-separated) to the accounts that may see
analytics. Those users can open **`/admin`** — a dashboard of total cost, runs,
tokens, a daily-cost chart, and per-model and per-user breakdowns — backed by the
admin-only `GET /admin/summary`. The page shell is public but shows nothing
without an admin token; there is no in-app way to grant admin and no default
admin.

### Chart data

The chart service computes the Parashari sections with the **Lahiri** ayanamsa
and the KP section (Placidus cusps, star/sub lords, ruling planets) with the
**Krishnamurti** ayanamsa; both are request fields (`ayanamsa`, `kp_ayanamsa`).
Before a specialist sees the chart, `astroweave.common.astro.build_chart_view`
derives house placements, lordships, dignities, aspects, nakshatras, combustion,
KP significators, dasha windows (with month-level pratyantardashas from one year
back to five years ahead) and transit context in code, and keeps the
divisional charts relevant to that specialist's domain. It never changes a
computed value.

Specialist prompts share explicit honesty rules: every statement must rest on a
chart factor in the data, unfavourable indications are stated as plainly as
favourable ones, and the final answer may not add or soften anything the
specialists found. Instead of a confidence label, answers say concretely what
limits certainty when something does.
