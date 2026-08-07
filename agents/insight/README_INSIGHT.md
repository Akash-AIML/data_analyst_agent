# Member 3 — Insight & Report Agent

Validates the Analysis Agent's output, translates verified statistics into
business insights + recommendations, and compiles a final **HTML + PDF** report
with graceful degradation when the upstream pipeline (Profiler/Analysis)
fails.

```
agents/
  state.py                     # shared AgentState contract (team-owned, drafted by M3)
  insight/
    validation.py              # deterministic validation engine (no LLM)
    prompts.py                 # OpenAI prompts + Pydantic output schemas (structured)
    report_generator.py        # HTML (Jinja2) + PDF (weasyprint)
    insight_node.py            # build_insight_node(llm) -> LangGraph node
    templates/report_template.html
    tests/                     # pytest suite (mock LLM, fixtures)
    README_INSIGHT.md
```

## Install / deps
```bash
pip install weasyprint langchain-openai   # + existing: langgraph, jinja2, pydantic, pytest
```

## Quick start
```python
from agents.insight.insight_node import build_insight_node
from agents.insight.prompts import get_chat_model

node = build_insight_node(get_chat_model())   # needs OPENAI_API_KEY
state = node(state)                           # state is an AgentState dict
# -> fills validation_report, insights, recommendations,
#    report_path (.html), pdf_path (.pdf), report_status
```

No API key? Run the whole agent against a stubbed LLM:
```python
from agents.insight.tests.fake_llm import FakeChatModel
node = build_insight_node(FakeChatModel())
```

## Key design decisions (from the devil's-advocate review)
- **Anti-hallucination**: the LLM is given a `JSON_BLOCK` of *verified* numbers
  (`validation.extract_evidence`) and must cite them verbatim. `prompts.verify_insights`
  then drops any insight whose `value` isn't backed by the evidence — a code-level
  fact-check, not just a prompt rule.
- **Structured output**: `prompts.structured_invoke` uses `with_structured_output`
  (tool-calling) on real OpenAI models and falls back to JSON-mode + Pydantic
  validation for stubs / non-tool models. Parse failures surface as Pydantic errors,
  never silent garbage.
- **Graceful degradation**: `insight_node` never raises. If upstream results are
  empty/failed, or validation errors occur, or too few insights verify, it emits a
  "degraded" report from the error/execution logs instead of crashing.
- **Image resilience**: charts are embedded as base64 data URIs only when the file
  exists and has an allowed extension (`.png/.jpg/.jpeg/.svg`). Zero charts hides the
  section; missing files are skipped; a broken `<img>` is impossible.
- **PDF fallback**: if weasyprint fails at runtime the HTML is still delivered,
  `pdf_path` stays `null`, and the error is recorded.

## State contract (additions by Member 3)
- `validation_report: dict` — deterministic check results (`status`, `checks`, ...)
- `insights: list[dict]`, `recommendations: list[str]`
- `contradictions: list[dict]` — self-consistency audit output
- `report_path: str`, `pdf_path: str|None`
- `report_status: str` — `"ok" | "degraded" | "failed"`
- `thinking_log: list[str]` — node reasoning for the "agentic narrative"

`agents/state.py` is the single source of truth; `build_state()` + `StateContract`
validate it so a mis-keyed field from any member fails fast at integration.

## Test / demo
```bash
python -m pytest agents/insight/tests -q   # 35 tests, incl. the chat core
```
Covers: validation edge cases (constant-column NaN correlations, case-insensitive
column matching, missing-rate mismatch, out-of-bounds stats), report resilience
(0 / partial / missing images, PDF fallback, never-raises), end-to-end node runs
(healthy, hallucinating LLM, failed upstream, garbage state), and the report-grounded
chat builder / answer / persistence.

## Chatbot (Streamlit, no API key needed)
```bash
venv/bin/streamlit run agents/insight/streamlit_app.py
```
Generates a sample report (fixtures as stand-in M1/M2 + built-in demo model), then
you ask questions and get answers grounded ONLY in that report. Off-report questions
get an honest "not in this report". Flip the "use real OpenAI" toggle when
`OPENAI_API_KEY` is set. You can also upload a `report_state.json` (produced by
`chat.save_report_state`) instead of regenerating.
- Core logic (UI-free, testable): `agents/insight/chat.py` — `build_context`,
  `answer`, `save_report_state` / `load_report_state`.

## Integration handshake (confirm with team)
- `analysis_results` item schema (`task_id`, `title`, `kind`, `column`, `stats`, `files`).
- `generated_files` path convention — absolute preferred (report embeds by path).
- Report write location (`output/reports/`) and whether `report_path` is absolute.
- Agree that "degraded" is an acceptable deliverable when upstream fails.