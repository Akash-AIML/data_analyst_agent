# System Architecture & Multi-Agent Pipeline

The **AI Data Analyst** system is built on a modular, state-driven multi-agent architecture powered by LangGraph.

---

## 1. High-Level Data Flow

```text
               +-----------------------+
               |     Input Dataset     |
               |      (sample.csv)     |
               +-----------+-----------+
                           |
                           v
               +-----------------------+
               |    Profiler Agent     |
               | (sweetviz +        |
               |  pandas descriptive)  |
               +-----------+-----------+
                           |
                     `AgentState`
                           |
                           v
               +-----------------------+
               |    Analysis Agent     |
               | (Planner -> Executor  |
               |     -> Reflector)     |
               +-----------+-----------+
                           |
                     `AgentState`
                           |
                           v
               +-----------------------+
               |     Insight Agent     |
               | (Validation -> Evidence|
               |   -> Executive Report)|
               +-----------+-----------+
                           |
                           v
               +-----------------------+
               |   Output Deliverable  |
               |   (HTML / PDF Report) |
               +-----------------------+
```

---

## 2. Shared State (`state/graph_state.py`)

All agents read from and write to a single, unified `AgentState` schema:

| Stage | Input State Keys | Output State Keys Written |
|---|---|---|
| **Profiler** | `csv_path` | `profile`, `profile_report_path`, `status` |
| **Analysis** | `profile`, `csv_path` | `analysis_plan`, `analysis_results`, `generated_files`, `execution_log`, `reflection_notes` |
| **Insight** | `profile`, `analysis_results` | `validation_report`, `insights`, `recommendations`, `report_path`, `pdf_path`, `report_status` |

---

## 3. Directory Layout

```text
.
├── agents/
│   ├── profiler/       # CSV ingestion & sweetviz HTML report
│   ├── analysis/       # Code generation, python executor, reflection loop
│   └── insight/        # Deterministic validation & HTML/PDF executive summary
├── api/                # FastAPI web backend
├── data/               # Sample CSV datasets
├── docs/               # Architecture and workflow documentation
├── graph.py            # LangGraph pipeline orchestrator
├── mocks/              # Mock dataset profiles for isolated testing
├── state/              # Shared AgentState TypedDict & StateContract validator
├── tests/              # Component unit & pipeline integration test suites
├── tools/              # Shared tools (profiling_tool, python_executor)
└── ui/                 # Single-page web dashboard
```
