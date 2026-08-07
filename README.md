# data_analyst_agent

Multi-agent **AI Data Analyst** built with LangGraph. One CSV goes in; a validated
analysis report (HTML + PDF) and an interactive, report-grounded Q&A come out.

## Architecture (three agents)
Pipeline: **Profiler → Analysis → Insight & Report**, joined by a single shared
`AgentState` contract.

| Agent | Role | Code | Readme |
|-------|------|------|--------|
| **Member 1 — Profiler** | CSV → pandas + ydata-profiling HTML report + structured `profile` | `agents/profiler_agent.py`, `tools/`, `api/`, `ui/` | `agents/m1/README.md` |
| **Member 2 — Analysis** | planner → executor (sandboxed code) → reflector → `analysis_results` | `agents/analysis_agent.py`, `tools/python_executor.py` | (see docstring) |
| **Member 3 — Insight** | validates, writes insights/recommendations, compiles HTML+PDF report, report-grounded Streamlit chat | `agents/insight/` | `agents/insight/README_INSIGHT.md` |

## Quick start
```bash
venv/bin/python -m pytest agents/insight/tests -q       # Member 3 suite (no API key)
venv/bin/streamlit run agents/insight/streamlit_app.py   # report + chat UI
```

## Shared state contract
Single source of truth: `state/graph_state.py` (convention) re-exported as
`agents/state.py` so all agents import `AgentState` from one place.

## Setup / env
Members use LangChain LLMs (OpenAI / Groq / Gemini) — set the relevant
`OPENAI_API_KEY` / `GROQ_API_KEY` / `GEMINI_API_KEY`. See each agent's readme.