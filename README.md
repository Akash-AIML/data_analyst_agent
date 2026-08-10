# 🤖 AI Data Analyst Agent System

An autonomous multi-agent data analysis platform built with **LangGraph**, **Pydantic**, **FastAPI**, and **Streamlit**. 

Given a CSV dataset, the system automatically performs exploratory data analysis (EDA), generates data profiling reports, plans and executes sandboxed Python code to compute stats and plot charts, validates quantitative evidence, compiles an executive HTML/PDF report, and provides a report-grounded conversational AI assistant.

| Agent | Role | Code | Readme |
|-------|------|------|--------|
| **Member 1 — Profiler** | CSV → pandas + sweetviz HTML report + structured `profile` | `agents/profiler_agent.py`, `tools/`, `api/`, `ui/` | `agents/m1/README.md` |
| **Member 2 — Analysis** | planner → executor (sandboxed code) → reflector → `analysis_results` | `agents/analysis_agent.py`, `tools/python_executor.py` | (see docstring) |
| **Member 3 — Insight** | validates, writes insights/recommendations, compiles HTML+PDF report, report-grounded Streamlit chat | `agents/insight/` | `agents/insight/README_INSIGHT.md` |

---

## 📌 1. Project Overview

The **AI Data Analyst Agent** transforms raw CSV files into validated, executive-ready analytical insights through a collaborative pipeline of specialized agents:

1. **Member 1 — Profiler Agent**: Inspects CSV structure, extracts statistical summaries via pandas/LLM, and produces an interactive `ydata-profiling` HTML report.
2. **Member 2 — Analysis Agent**: Generates a task-based analysis plan, executes Python code in an isolated subprocess sandbox, captures stdout/stderr/generated charts, and reflects on task completion.
3. **Member 3 — Insight & Report Agent**: Performs deterministic cross-validation, extracts verified evidence, formulates insights and recommendations, renders Base64-embedded HTML/PDF deliverables, and powers a report-grounded chatbot.

---

## ✨ 2. Key Features

- **Multi-Agent Orchestration**: End-to-end workflow managed by a state-driven LangGraph architecture.
- **Resilient LLM Provider Fallback**: Automatic, zero-downtime fallback across **Groq → Gemini → OpenAI** (`ResilientFallbackModel`) to handle API outages or rate limits.
- **Sandboxed Python Code Execution**: Isolated subprocess execution (30s timeout) with dynamic chart generation (Matplotlib/Seaborn) and automatic code sanitization.
- **Deterministic Evidence Validation**: Pre-LLM mathematical validation engine verifying bounds, rates, cardinalities, and column existence.
- **Pure Pandas Profiling Fallback**: Robust fallback profiling mechanism when LLMs encounter context limitations on ultra-wide or massive datasets.
- **Offline HTML & PDF Report Generation**: Jinja2 templated executive HTML reports with Base64 image embedding, plus WeasyPrint PDF generation (with graceful degradation if native dependencies are absent).
- **Report-Grounded Q&A Chatbot**: Anti-hallucination chat agent strictly constrained to the generated report context with explicit *"Not in this report"* response rules.
- **Interactive 5-Tab Streamlit Dashboard**: Web UI covering Pipeline Execution, EDA Inspection, Visual Galleries, Interactive Q&A Chat, and Agent Diagnostics.
- **Production REST API**: FastAPI backend providing asynchronous endpoints for file uploads, profiling, and report downloads.

---

## 📐 3. Architecture & How It Works

```
                     ┌────────────────────────┐
                     │     Uploaded CSV       │
                     └───────────┬────────────┘
                                 │
                                 ▼
                     ┌────────────────────────┐
                     │    1. Profiler Agent   │
                     │  (Pandas + ydata-prof) │
                     └───────────┬────────────┘
                                 │
                                 ▼
                     ┌────────────────────────┐
                     │  2a. Analysis Planner  │
                     │   (Builds task plan)   │
                     └───────────┬────────────┘
                                 │
                                 ▼
              ┌───────────────► 2b. Execution Sandbox (Subprocess)
              │                 │   (Generates plots & stats)
              │                 ▼
              └──────────────── 2c. Reflector Agent
                   (Retries)    │   (Evaluates completeness)
                                │
                                ▼
                     ┌────────────────────────┐
                     │  3. Insight & Report   │
                     │   (Validate + Render)  │
                     └───────────┬────────────┘
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
 ┌──────────────────────┐                 ┌──────────────────────┐
 │  Executive Deliverables│                 │ Report-Grounded Chat │
 │  (HTML & PDF Reports)│                 │ (Streamlit Interface)│
 └──────────────────────┘                 └──────────────────────┘
```

### Shared State Architecture (`AgentState`)
All agents read from and write to a single source of truth defined in `state/graph_state.py` (and re-exported via `state.py` / `agents/state.py`). The state is strictly validated via Pydantic (`StateContract`).

| Agent | Keys Written |
|---|---|
| **Profiler** | `csv_path`, `profile`, `profile_report_path`, `status` |
| **Analysis** | `analysis_plan`, `analysis_results`, `generated_files`, `execution_log`, `reflection_notes` |
| **Insight** | `validation_report`, `insights`, `recommendations`, `report_path`, `pdf_path`, `report_status` |
| **Shared** | `error_log`, `thinking_log`, `status` |

---

## 📁 4. Project Structure

```
data_analyst_agent/
├── agents/                     # Agent implementations
│   ├── profiler/               # Profiler Agent (M1)
│   │   ├── agent.py            # profiler_node
│   │   ├── prompts.py          # Profiler system & user prompts
│   │   └── schemas.py          # ProfileOutput Pydantic schema
│   ├── analysis/               # Analysis Agent (M2)
│   │   ├── agent.py            # planner_node, executor_node, reflector_node
│   │   └── prompts.py          # Code generation & reflection prompts
│   └── insight/                # Insight & Report Agent (M3)
│       ├── insight_node.py     # insight_node orchestration
│       ├── validation.py       # Deterministic verification engine
│       ├── report_generator.py # Jinja2 HTML & WeasyPrint PDF compiler
│       ├── chat.py             # Report-grounded chatbot core
│       ├── prompts.py          # Insight generation & verification prompts
│       └── templates/          # Jinja2 HTML templates
│
├── api/                        # FastAPI REST API Backend
│   └── main.py                 # Endpoint routes (/health, /analyze, /report/{filename})
│
├── state/                      # Shared state contract
│   └── graph_state.py          # AgentState TypedDict & StateContract Pydantic model
│
├── tools/                      # Shared execution & LLM utilities
│   ├── llm_factory.py          # ResilientFallbackModel (Groq -> Gemini -> OpenAI)
│   ├── profiling_tool.py       # ydata-profiling LangChain BaseTool
│   └── python_executor.py      # Subprocess code execution sandbox
│
├── ui/                         # Streamlit Dashboard UI
│   ├── components/             # Modular Streamlit tab components
│   │   ├── header.py           # Top branding header & CSS styling
│   │   ├── pipeline_runner.py  # Tab 1: Ingestion & Pipeline Runner
│   │   ├── eda_profile.py      # Tab 2: EDA & Embedded ydata Report
│   │   ├── insights_gallery.py # Tab 3: Insights & Visualizations Gallery
│   │   ├── analyst_chat.py     # Tab 4: Interactive Analyst Q&A Chat
│   │   └── diagnostics.py      # Tab 5: Agent Thinking Logs & Raw State
│   └── services/               # UI helper services (pipeline_service.py)
│
├── tests/                      # Automated test suite (55 test cases)
│   ├── analysis/               # Analysis agent tests
│   ├── insight/                # Insight agent, validation, & chat tests
│   ├── pipeline/               # Full pipeline graph tests
│   ├── profiler/               # Profiler agent tests
│   └── ui/                     # Web UI tests
│
├── data/                       # Sample CSV datasets (sample_sales.csv, etc.)
├── output/                     # Generated outputs (profiles/, analysis/, reports/)
├── uploads/                    # Temporary user file upload directory
├── app.py                      # Streamlit application main entrypoint
├── graph.py                    # LangGraph pipeline composition script
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

---

## ⚙️ 5. Prerequisites

- **Python**: 3.10 or higher (Tested on Python 3.13)
- **Virtual Environment**: Recommended (`venv` or `conda`)
- **Optional System Libraries (for PDF export)**:
  - WeasyPrint requires native libraries (`Pango`, `Cairo`, `GLib`). If these native dependencies are not installed on your OS, PDF generation gracefully degrades while HTML reports remain fully functional.

---

## 🚀 6. Installation & Setup

1. **Navigate to the project directory**:
   ```bash
   cd data_analyst_agent
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## 🔑 7. Environment Variables & Configuration

Create a `.env` file in the project root (`data_analyst_agent/.env`):

```ini
# --- LLM Provider API Keys (Ordered Fallback: Groq -> Gemini -> OpenAI) ---
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=your_base_url_here
MODEL=gemini-2.5-flash

# --- Application Configuration ---
OUTPUT_DIR=output/profiles
MAX_FILE_SIZE_MB=50
```

> [!NOTE]
> The LLM factory (`tools/llm_factory.py`) automatically evaluates available API keys in order. You only need at least one valid key (`GROQ_API_KEY`, `GEMINI_API_KEY`, or `OPENAI_API_KEY`) to run the system.

---

## 🖥️ 8. Running the Application

### Option A: Streamlit Dashboard UI (Recommended)
Run the full 5-tab interactive web interface:
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### Option B: FastAPI Backend Server
Run the production REST API server:
```bash
uvicorn api.main:app --reload --port 8000
```
- API Base URL: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`

### Option C: Standalone CLI Execution
Run the full multi-agent pipeline directly on `data/sample_sales.csv`:
```bash
python graph.py
```

---

## 🧪 9. Running Tests

The repository includes **55 test items** covering input validation, LLM fallback, execution sandboxing, report generation, and chat grounding.

### Run all tests:
```bash
pytest
```

### Run specific agent test suites:
```bash
# Profiler Agent tests
pytest tests/profiler/

# Analysis Agent tests
pytest tests/analysis/

# Insight Agent, Validation, & Chat tests
pytest tests/insight/

# Pipeline integration tests
pytest tests/pipeline/
```

### Offline / No-API-Key Test Mode
Tests under `tests/insight/` use a deterministic stub model (`FakeChatModel`) and mock fixtures (`fixtures.py`), allowing you to test the complete validation, report compilation, and chat logic offline without making LLM API calls.

---

## 💡 10. Usage Examples

### Executing the Pipeline Programmatically
```python
from graph import create_pipeline

# Initialize pipeline with automatic resilient LLM fallback
pipeline = create_pipeline()

# Define initial state with target CSV
initial_state = {
    "csv_path": "data/sample_sales.csv",
    "status": "running",
    "error_log": [],
    "thinking_log": []
}

# Run execution
final_state = pipeline(initial_state)

# Access output details
print("Report Status :", final_state.get("report_status"))
print("HTML Report   :", final_state.get("report_path"))
print("PDF Report    :", final_state.get("pdf_path"))
print("Insights Count:", len(final_state.get("insights", [])))
```

---

## 🧩 11. Important Modules & Components

- `tools/llm_factory.py`: Implements `ResilientFallbackModel`, wrapping multiple providers to try models sequentially (`Groq → Gemini → OpenAI`) on error or rate limits.
- `tools/python_executor.py`: Subprocess sandbox executing generated analysis code. Sanitizes code (removes redundant `pd.read_csv` calls), enforces a 30-second execution timeout, and captures new image files in `output/analysis/`.
- `agents/insight/validation.py`: Deterministic verification engine. Validates numeric bounds, percentage ranges $[0, 100]$, correlation coefficients $[-1, 1]$, and column types without LLM intervention.
- `agents/insight/report_generator.py`: Compiles reports via Jinja2. Converts chart images to Base64 data URIs for self-contained, offline-compatible HTML and PDF reports.
- `agents/insight/chat.py`: Grounds chat responses strictly on the serialized report context.

---

## 📊 12. Reports & Outputs

All generated artifacts are saved in the `output/` directory:

- `output/profiles/`: Interactive `ydata-profiling` HTML reports (e.g., `sample_sales_profile.html`).
- `output/analysis/`: Visualization images generated by executed Python code (e.g., PNG/JPG charts).
- `output/reports/`: Executive HTML and PDF reports compiled by the Insight agent (e.g., `sample_sales_report.html`, `sample_sales_report.pdf`).

---

## 🛡️ 13. Error Handling & Graceful Degradation

- **LLM Failures**: If the primary LLM provider fails or hits rate limits, `ResilientFallbackModel` seamlessly routes requests to the next configured provider.
- **Wide/Large CSVs**: If LLMs fail during profiling due to context window size, `profiler_node` falls back to `_build_profile_from_pandas`, constructing the dataset profile strictly via pandas.
- **Analysis Execution Errors**: If Python code fails during execution, `executor_node` captures stderr and passes it to an LLM error-fix prompt for up to 3 retry attempts before marking the task failed.
- **Validation Warnings**: If validation detects issues, `insight_node` sets `report_status` to `"degraded"` and continues building the report using verified evidence entries.
- **WeasyPrint PDF Fallback**: If native PDF libraries (`Pango`/`Cairo`) are missing, `report_generator` catches the exception, logs a warning, sets `pdf_path = None`, and delivers the complete HTML report.

---

## 📋 14. Known Limitations

- **WeasyPrint Native Dependencies**: PDF export depends on WeasyPrint, which requires GTK+/Pango libraries on Windows/Linux. If not present, PDF generation is skipped (HTML report is always preserved).
- **Execution Sandbox Timeout**: Python code execution times out after 30 seconds per task.
- **Prompt Token Capping**: For datasets with over 80 columns, `_extract_df_info` truncates printed dtypes and sample previews to fit comfortably within LLM context windows.

---

## 🔮 15. Future Improvements

- Support for multi-file CSV uploads and relational database connectors.
- Dockerized sandbox containers for stricter execution isolation.

### 1. Run FastAPI Backend
```bash
python -m uvicorn api.main:app --reload --port 8000
```

### 2. Run React Frontend
```bash
cd frontend
npm install
npm run dev
```


### 1. Run FastAPI Backend
```bash
python -m uvicorn api.main:app --reload --port 8000
```

### 2. Run React Frontend
```bash
cd frontend
npm install
npm run dev
```

### 3. Run Streamlit App (Alternative UI)
```bash
streamlit run app.py
```

### 4. Run Test Suite
```bash
pytest
```

## Shared state contract
Single source of truth: `state.py` (or `state/graph_state.py`) re-exported so all agents import `AgentState` from one place.

## Setup / env
Set the relevant LLM keys in `.env`: `OPENAI_API_KEY`, `GROQ_API_KEY`, or `GEMINI_API_KEY`.
