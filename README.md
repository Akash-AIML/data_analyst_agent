# Profiler Agent — Member 1

A production-grade LangGraph Profiler Agent that ingests CSV files, generates an interactive `ydata-profiling` HTML report, and returns a structured dataset profile via a FastAPI backend with a clean single-page HTML/JS frontend.

---

## Project Structure

```
.
├── agents/
│   ├── profiler_agent.py       # LangGraph node
│   ├── profiler_prompts.py     # LLM prompts
│   └── profiler_schemas.py     # Pydantic output schema
├── api/
│   └── main.py                 # FastAPI backend
├── data/
│   └── sample_sales.csv        # Demo CSV
├── mocks/
│   └── mock_profile.json       # Example output for teammates
├── output/profiles/            # Generated HTML reports (gitignored)
├── state/
│   └── graph_state.py          # Shared AgentState TypedDict
├── tests/
│   └── test_profiler.py        # Edge case test suite
├── tools/
│   └── profiling_tool.py       # ydata-profiling BaseTool
├── ui/
│   └── index.html              # Single-page frontend
├── .env.example                # Environment variable template
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Create & activate virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your OPENAI_API_KEY (and optionally OPENAI_BASE_URL)
```

`.env` variables:

| Variable | Description | Default |
|---|---|---|
| `MODEL` | LLM model name | `gpt-4.1-nano` |
| `OPENAI_API_KEY` | Your OpenAI API key | *(required)* |
| `OPENAI_BASE_URL` | API base URL (for proxies/alternatives) | `https://api.openai.com/v1` |
| `OUTPUT_DIR` | Where HTML reports are saved | `output/profiles` |
| `MAX_FILE_SIZE_MB` | Maximum CSV upload size | `50` |

---

## Running

### Start the backend

```bash
uvicorn api.main:app --reload
```

API will be available at `http://localhost:8000`.  
Auto-generated API docs: `http://localhost:8000/docs`.

### Open the frontend

```bash
# From project root
python -m http.server 8080 --directory ui
```

Open `http://localhost:8080` in your browser.

---

## Running Tests

```bash
python -m pytest tests/test_profiler.py -v
```

Tests covering: normal CSV, missing file, non-CSV extension, empty CSV, all-missing column.  
LLM-dependent tests are skipped automatically if `OPENAI_API_KEY` is not set.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/analyze` | Upload CSV → returns profile JSON |
| `GET` | `/report/{filename}` | Serves the HTML report |

---

## State Contract

- **Reads:** `csv_path`
- **Writes:** `profile`, `profile_report_path`, `error_log`, `status`

```python
from agents.profiler_agent import profiler_node

state = {
    "csv_path": "data/sample_sales.csv",
    "profile": None,
    "profile_report_path": None,
    "error_log": [],
    "status": "running"
}
result = profiler_node(state)
# result["status"] == "completed"
# result["profile"]  -> dict with full ProfileOutput
```
