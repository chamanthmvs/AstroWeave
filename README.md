# AstroWeave

> A hierarchical multi-agent astrology system built with LangGraph.

AstroWeave is an AI-powered astrology system where a central **Astrologer Manager** coordinates specialized astrologer agents to analyze user questions, select relevant methodologies, evaluate results, and produce a coherent final response.

## Architecture

```text
User Question
      |
      v
Astrologer Manager
      |
      v
Planner ---> Executor ---> Specialist Subgraph(s)
                                  |
                    +-------------+-------------+
                    |                           |
              Domain Specialist          Methodology
              Sports, Career,             Vedic, KP,
              Relationships, etc.         or Both
                                  |
                                  v
                         Collector / Evaluator
                                  |
                         Re-plan when required
                                  |
                                  v
                            Synthesizer
                                  |
                                  v
                            Final Answer
```

## Core Concepts

- **Hierarchical orchestration:** a top-level manager invokes independently structured specialist subgraphs.
- **Domain specialization:** specialists focus on areas such as sports, relationships, career, education, and finance.
- **Methodology separation:** Vedic and KP are analysis methodologies, not ordinary domain specialists.
- **Iterative reasoning:** results are collected and evaluated before synthesis; insufficient results can trigger re-planning.
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

## Status

**Under active development**

v1 is wired end-to-end: a question from the Streamlit UI reaches the FastAPI
backend, is routed to domain specialists by an LLM-driven planner, grounded
in a real birth chart, and synthesized into one final answer. Not yet in
place: a knowledge/retrieval (RAG) layer for grounding specialists in
astrology reference material, and methodology-specific (Vedic/KP) retrieval
logic beyond label selection. See project_overview.txt for the full picture.