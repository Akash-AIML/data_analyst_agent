# Remaining Improvements Plan

**Status**: Phase 1, 2, 3, 4 (partial) complete. 110 tests passing.

## ✅ Completed (This Session)

| Area | Tasks |
|------|-------|
| **LangSmith Observability** | `LANGSMITH_TRACING_V2` env support, `_tracing_metadata()`, runnable config on graph invoke, tests |
| **Sandbox CPU Bug** | Fixed `_rlimits()`: `RLIMIT_CPU` now uses `_CPU_LIMIT_S` (not `_MEM_LIMIT_MB`) |
| **Configurable Recompute Tolerance** | `RECOMPUTE_TOLERANCE` / `RECOMPUTE_ABS_TOLERANCE` env vars, per-call overrides, 9 new tests |
| **PDF Status Field** | Added `pdf_status` ("ok" | "skipped" | "failed") separate from `report_status` |
| **Centralized Config** | New `config.py` with `OUTPUT_ROOT`, `PROFILE_DIR`, `ANALYSIS_DIR`, `REPORT_DIR`, `LLM_CACHE_PATH`, all tunables, `ensure_dirs()`, `snapshot()` |
| **LLM Cache** | TTL (default 7d), atomic write (`.tmp` + `os.replace`), FIFO cap, legacy schema migration, 5 new tests |
| **Budget Warnings** | Soft warn at `LLM_BUDGET_WARN_RATIO` (default 80%), hard stop at cap, `__budget__` summary entry on `state["llm_calls"]`, `budget_total()` / `budget_reset()` helpers, 4 new tests |
| **Sandbox Hardening** | AST gate (banned builtins + module calls + import blocking), regex layer for cosmetic cleanup, `SecurityError` raised in-process, 27 new tests in `tests/tools/test_sandbox_security.py` |
| **Lazy PDF & Auth** | `ENABLE_PDF` (default 0), `API_BEARER_TOKEN` optional auth, `BackgroundTasks` temp file cleanup |
| **Parallel Executor** | Deterministic analysis tasks run concurrently via `ThreadPoolExecutor` (4 workers) |
| **Chunked Profiling** | Large CSVs >50MB read via chunked streaming downsample (up to 50k rows) |
| **Edge Case Fixtures** | Added `empty.csv`, `single_row.csv`, `all_nulls.csv`, `mixed_types.csv`, `wide_200cols.csv` and `test_edge_cases.py` |
| **Structured Output Test**| Verified `ResilientFallbackModel.with_structured_output` delegation |
| **Production Tooling**| Created `pyproject.toml`, `.github/workflows/lint.yml`, and `docs/operations.md` runbook |

---

## 🔄 Remaining (Not Yet Done)

### Phase 2 — Performance & Scalability
- [x] **Lazy PDF**: Opt-in via env (`ENABLE_PDF=1`) — weasyprint is heavy (300MB native deps)
- [x] **Parallel Executor**: Independent analysis tasks run concurrently (read-only on same df)
- [x] **Chunked Profiling**: For CSVs >50MB, stream + downsample + merge sweetviz summaries
- [ ] **Pre-warm Subprocess Pool**: First-call latency dominated by Python startup; keep N workers hot

### Phase 3 — Reliability & Testing (Gaps)
- [x] **Fixtures for Edge Cases**: Mixed-type CSV, 100% missing column, weird dates, empty CSV, single-row, wide CSV (>200 cols) — add to `tests/fixtures/csvs/`
- [x] **ResilientFallbackModel structured_output Test**: Verify `with_structured_output` pass-through works for Groq/OpenAI/Gemini
- [ ] **Integration Tests w/ Real CSV Diversity**: Run pipeline on 3 diverse datasets in CI
- [ ] **OpenTelemetry / LangSmith Exporter**: Wire `LANGSMITH_ENDPOINT` for self-hosted / EU; add OTel traces for node durations

### Phase 4 — Production Hardening
- [x] **Auth on FastAPI**: Bearer token from env (`API_BEARER_TOKEN`)
- [x] **Background Upload Cleanup**: Non-blocking `BackgroundTasks` temp file removal in `api/main.py`
- [x] **Pyproject.toml + Ruff + MyPy**: Add linting/formatting CI (`pyproject.toml`, `.github/workflows/lint.yml`)
- [x] **Runbook**: `docs/operations.md` — env vars, failure modes, cost controls, debugging guide


### Feature Additions (Optional)
- [ ] **Multi-CSV / Batch Mode**: Manifest file → multiple reports
- [ ] **Scheduled Reports**: Cron / GitHub Actions trigger → object storage
- [ ] **Data Lineage**: Track which CSV row produced which insight
- [ ] **Pluggable LLM Providers**: Anthropic, Ollama, Azure OpenAI in `llm.py`
- [ ] **Custom Insight Templates**: Seed prompts with domain context (finance, healthcare)
- [ ] **Comparison Reports**: Diff two datasets' reports side-by-side
- [ ] **Streaming LLM Tokens**: Streamlit chat streaming for insights + Q&A

---

## 🧪 How to Verify Changes

```bash
# Run all tests
venv/bin/python -m pytest -q

# Run specific test groups
venv/bin/python -m pytest tests/llm/test_llm.py -v
venv/bin/python -m pytest tests/tools/test_sandbox_security.py -v
venv/bin/python -m pytest tests/insight/test_verify.py -v
venv/bin/python -m pytest tests/insight/test_report_generator.py -v

# Quick sanity: run the pipeline end-to-end
venv/bin/python -m graph  # or: venv/bin/python graph.py
```

---

## 🔑 Key Files Modified

| File | Purpose |
|------|---------|
| `config.py` | **NEW** — Centralized paths + tunables |
| `llm.py` | LangSmith tracing, cache TTL/atomic, budget warnings, budget API |
| `graph.py` | RunnableConfig with LangSmith metadata |
| `tools/python_executor.py` | CPU rlimits fix, AST sandbox gate, SecurityError |
| `agents/insight/verify.py` | Configurable recompute tolerance |
| `agents/insight/report_generator.py` | `pdf_status` field |
| `agents/insight/insight_node.py` | Uses config.REPORT_DIR |
| `api/main.py` | Config-driven paths, CORS, `/config` endpoint |
| `tools/profiling_tool.py` | Uses config.PROFILE_DIR + tunables |
| `.env.example` | All new env vars documented |
| `pytest.ini` | **NEW** — pytest config |
| `tests/llm/test_llm.py` | 13 new tests (LangSmith, cache, budget) |
| `tests/tools/test_sandbox_security.py` | **NEW** — 27 sandbox tests |
| `tests/insight/test_verify.py` | **NEW** — 9 tolerance tests |

---

## 🚀 Next Priority (If Continuing)

1. **Lazy PDF** — Add `ENABLE_PDF` env; skip weasyprint by default
2. **Background Upload Cleanup** — Non-blocking temp file removal
3. **Auth on API** — Simple bearer token gate
4. **Pyproject + Ruff + MyPy CI** — Enforce code quality