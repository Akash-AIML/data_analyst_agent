# AI Data Analyst Operations Runbook

## Overview
This runbook describes system configuration, operational monitoring, failure modes, cost control limits, and troubleshooting procedures for the **AI Data Analyst Agent** system.

---

## 1. Environment Variables & Configuration

The system uses `config.py` as the single source of truth for paths and operational tunables. All settings can be set in `.env` or passed via environment variables.

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `OPENAI_API_KEY` | *(required)* | Primary API Key for LLM operations |
| `OPENAI_BASE_URL` | `https://integrate.api.nvidia.com/v1` | Custom OpenAI-compatible endpoint URL |
| `MODEL` | `nvidia/nemotron-mini-4b-instruct` | Primary LLM model identifier |
| `GROQ_API_KEY` | `""` | Fallback LLM provider key |
| `GEMINI_API_KEY` | `""` | Secondary fallback provider key |
| `LLM_BUDGET_US` | `1.0` | Maximum USD budget per pipeline run (0 disables) |
| `LLM_BUDGET_WARN_RATIO` | `0.8` | Soft warning threshold for budget limit (80%) |
| `ENABLE_PDF` | `0` | Opt-in toggle (`1` or `0`) for WeasyPrint PDF generation |
| `API_BEARER_TOKEN` | `""` | Bearer token to secure `/analyze` and `/chat` endpoints |
| `ALLOWED_ORIGINS` | `*` | Comma-separated list of allowed CORS origins |
| `MAX_FILE_SIZE_MB` | `200.0` | Maximum CSV upload size limit |

---

## 2. API Endpoints & Health Check

- **GET `/health`**: Returns real-time connection and latency status for system components.
- **GET `/config`**: Returns full non-secret runtime snapshot of all active tunables and directory paths.
- **POST `/analyze`**: Upload CSV dataset and execute full agent pipeline. Accepts Bearer token if `API_BEARER_TOKEN` is configured.
- **POST `/chat`**: Grounded report Q&A endpoint.

---

## 3. Failure Modes & Troubleshooting

### Failure Mode 1: PDF Generation Fails (`pdf_status="failed"`)
- **Symptom**: `write_report` logs warning `PDF generation skipped: weasyprint missing or failed`.
- **Cause**: Missing system libraries (`libpango`, `libcairo`, `libgobject`).
- **Resolution**: HTML reports continue to be rendered without disruption (`report_status="ok"`). To fix PDF generation, ensure `ENABLE_PDF=1` and install required system packages (`apt-get install pango1.0-tools`).

### Failure Mode 2: LLM Rate Limits / 429 Errors
- **Symptom**: Repeated HTTP 429 status from primary LLM model.
- **Resolution**:
  - The system automatically fails over to `GROQ_API_KEY` or `GEMINI_API_KEY` via `ResilientFallbackModel`.
  - Deterministic templates run automatically for standard analysis tasks (`LLM_PLANNER=0`), preventing excess LLM calls.

### Failure Mode 3: Memory Exhaustion / Large CSV Uploads (>50MB)
- **Symptom**: High memory usage on large file profiling.
- **Resolution**: Profiler streams CSV files >50MB in chunks, downsampling up to 50,000 rows across chunks to bound memory usage.

---

## 4. Maintenance & Verification

Run the test suite using the project virtual environment:

```bash
# Run full unit and integration test suite
./venv/bin/pytest -v

# Run pipeline end-to-end sanity check
./venv/bin/python graph.py
```
