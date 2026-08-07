# 🧩 Data Analyst Agent — Three Member Plans & Devil’s Advocate Critique

## Overview
This document contains the execution roadmaps for all three team members working on the **Data Analyst Agent** multi-agent system, along with critical Devil's Advocate evaluations, mitigation strategies, and the detailed execution blueprint for **Member 3 (Insight & Report Agent)**.

---

# 👤 Member 1 Plan — Profiler Agent

### Goal
Build an agent node that receives a `csv_path`, produces a structured `profile` dict and a `ydata-profiling` HTML report, and writes both into the shared `AgentState`.

### Step‑by‑step Tasks (Day 1 → Day 2)

| # | Task | Time |
|---|------|------|
| 1 | Set up `profiling_tool.py` – wrap `ydata-profiling` as a LangChain Tool that accepts a path and returns the HTML path | 1 h |
| 2 | Write `profiler_prompts.py` – system prompt for the LLM that reasons about column types, flags id / datetime / high-cardinality cols | 1 h |
| 3 | Build `profiler_node(state)` – calls the tool, parses output, asks LLM to refine schema detection, validates the profile structure | 2 h |
| 4 | Write `test_profiler.py` – uses a sample CSV, creates a minimal state, runs the node, checks all required keys and constraints | 1 h |
| 5 | Handle edge cases: bad encoding, empty file, huge file, non‑csv extension | 1 h |
| 6 | Produce `README_PROFILER.md` | 0.5 h |
| 7 | Integration hand‑shake: confirm exact key names with team | 0.5 h |

**Deliverable**  
A single function `profiler_node(state: AgentState) -> AgentState` that populates `profile`, `profile_report_path`, and `error_log`.

---

## 😈 Devil’s Advocate Critique — Member 1

### 1. `ydata-profiling` is a double‑edged sword
`ydata-profiling` is excellent, but it often **fails silently** on edge cases (e.g., entirely empty columns, mixed‑type columns). You plan to handle “bad encoding” and “empty file”, but what about a column that is `object` but looks numeric? ydata‑profiling will classify it as `Categorical` with hundreds of unique values, blowing up the report. Your LLM‑based schema refinement **must** catch and re‑classify this, but LLM reasoning over raw column names is brittle — it may mis‑label `"ID"` as a numeric identifier when it’s actually a high‑cardinality categorical.  
**Risk**: The profile dict could mis‑represent the data, causing the Analysis Agent to generate impossible code.

### 2. The “LLM reasons about column types” promise is hand‑wavy
The plan says “ask LLM to refine schema detection”. What’s the exact prompt? How do you force the LLM to return a structured JSON with exactly the required keys? If the LLM hallucinates a column named `Sales_x`, the whole downstream breaks. You need a **StructuredOutputParser** or a Pydantic schema enforced by LangChain’s `with_structured_output()`. If you just ask the LLM for a dict, you’ll spend hours debugging parsing failures.  
**Risk**: The profiler node becomes a parsing‑error factory.

### 3. No plan for dealing with large CSVs
2‑day projects often test with a 10 MB dataset. `ydata-profiling` on a 10 MB CSV can take **minutes** and consume gigabytes of RAM. Your node might time out, or the deployment container might crash. The plan doesn’t mention a size limit or early bail‑out.  
**Suggestion**: Add a quick pre‑check: if `os.path.getsize(csv_path) > 50 MB`, skip the full profile, just compute basic stats with pandas chunks.

### 4. Testing is too thin
The test uses a “sample CSV” but doesn’t specify that it must contain:
- Mixed‑type columns
- Date columns in bizarre formats
- Columns with 100% missing values
- Completely empty CSVs

Without these, your tests will pass even though your agent fails in the integration session.

### 5. The “error_log” mechanism is under‑specified
You’re supposed to append errors, but what stops the node from crashing before appending? If `profiling_tool` raises an exception, your node must catch it, format it, and still return a valid state. That means all tool calls must be wrapped in try‑except, and you must guarantee no `KeyError` when building the profile dict.

### 6. No explicit validation of the `profile` dict before returning
You hand the profile to Member 2, but if `numeric_columns` is an empty list (because ydata mis‑parsed everything as object), the Analysis Agent will plan zero tasks and produce no insights. Your node should self‑validate that `rows > 0`, `columns > 0`, and that at least one numeric or categorical column exists, or set `status = "failed"` and stop the pipeline.

---

# 👤 Member 2 Plan — Analysis Agent (Planner + Executor + Reflector)

### Goal
Build three nodes that take a `profile`, create an analysis plan, generate/execute Python code step‑by‑step, recover from errors, and reflect on completeness.

### Step‑by‑step Tasks

| # | Task | Time |
|---|------|------|
| 1 | Build `python_executor.py` – subprocess sandbox that takes `code` + `csv_path`, runs in a restricted env, captures stdout/stderr/files, enforces timeout & path limits | 2 h |
| 2 | Write all prompts: planning, code generation, error‑fixing, reflection | 1 h |
| 3 | Implement `planner_node(state)` – uses LLM to produce an ordered list of analysis tasks based on the profile | 1.5 h |
| 4 | Implement `executor_node(state)` – picks next pending task, generates code, executes, handles retries, updates state incrementally | 3 h |
| 5 | Implement `reflector_node(state)` – checks if plan is complete, re‑plans if necessary, writes reflection notes | 1.5 h |
| 6 | Write `test_analysis.py` – test each node with mock profile; inject deliberate errors to verify retry | 1 h |
| 7 | `README_ANALYSIS.md` | 0.5 h |
| 8 | Integration tweaks | 0.5 h |

**Deliverables**  
Three node functions and one tool. The state gains `analysis_plan`, `analysis_results`, `generated_files`, `execution_log`, `reflection_notes`.

---

## 😈 Devil’s Advocate Critique — Member 2

### 1. The sandbox is the biggest hidden monster
“Subprocess with restricted paths” hides days of work. Consider:
- Generated code imports pandas (`import pandas as pd`).
- Code saves plots to output folder (`plt.savefig("output/analysis/...")`).
- Security risks from arbitrary imports (`os.system`).
- Timeout handling for hung loops.
**Risk**: Hours spent on sandbox, lingering crash scenarios.

### 2. The retry loop is fragile
LLMs can misdiagnose error messages. Without retry caps and back-off strategies, infinite loops occur. Distinction between retry-able vs fatal errors is crucial.

### 3. Unconstrained Planner Creativity
Planner might attempt machine-learning models missing in execution environment. Must strictly enforce descriptive and exploratory analysis only.

### 4. Inconsistent State Mutations
Midway crashes leave partial state. Node must return explicit status flags (`failed`, `in_progress`, `completed`).

### 5. Scope Creep on Reflection Node
In tight timelines, reflection node risks simplification. Core execution pipeline must be prioritized.

### 6. Isolation Testing Friction
Testing require mock sandboxes and deterministic error injection.

---

# 👤 Member 3 Plan — Insight & Report Agent

### Goal
Build a node that validates analysis results, translates statistics into business insights, generates recommendations, and compiles a final HTML/PDF report.

### Step‑by‑step Tasks

| # | Task | Time |
|---|------|------|
| 1 | Write validation logic: sanity‑check means, correlations, percentages; cross‑reference with profile; produce `validation_report` dict | 2 h |
| 2 | Create insight generation prompt – instruct LLM to produce at least 5 insights with exact numbers | 1 h |
| 3 | Create recommendation prompt – from insights, derive actionable business recommendations | 0.5 h |
| 4 | Build `report_template.html` using Jinja2 – all required sections, dynamic image embedding | 1.5 h |
| 5 | Wrap report generation as a LangChain Tool `report_generator.py` | 1 h |
| 6 | Implement `insight_node(state)` – calls validation, calls LLM for insights/recommendations, passes everything to report generator | 2 h |
| 7 | Write `test_insight.py` using mocks | 1 h |
| 8 | `README_INSIGHT.md` | 0.5 h |

**Deliverable**  
One node function that fills `validation_report`, `insights`, `recommendations`, and `report_path`.

---

## 😈 Devil’s Advocate Critique — Member 3

### 1. Hardcoded Validation Rules can be brittle
Real validation must handle constant column correlation `NaN`s, case-insensitive key matching (`Sales` vs `sales`), and null counts.

### 2. Hallucinated Insights vs Truth
LLMs can write convincing business copy on bad data. Strict prompts requiring numeric verification against analysis outputs are required.

### 3. Broken HTML Layout on Missing Images
Jinja2 template must handle 0, partial, or missing generated chart images gracefully without rendering broken images or crashing.

### 4. Single-pass LLM Insights
Prompts must include self-consistency checks so insight #2 doesn't contradict insight #5.

### 5. Upstream Pipeline Failure Handling
If Member 1 or 2 fail, Member 3 must gracefully degrade and produce an error summary report instead of crashing.

---

# 🔥 Overall Devil’s Advocate Summary Matrix

| Area | Hidden Risk | Mitigation |
|------|-------------|------------|
| **LLM Dependency** | Every member relies on deterministic LLM behavior. Prompt tuning issues, rate limits. | Shared prompt-tuning slot (1 h together). Enforce Pydantic structured output. |
| **Testing with Real CSVs** | Mock tests pass; first real CSV breaks down. | Early integration test with 3 diverse CSV datasets. |
| **State Contract Drift** | Silent key updates break integration across members. | Formalized Pydantic / TypedDict `AgentState` schema in `state.py`. |
| **Sandbox Security** | Insecure subprocess execution. | Strict restricted subprocess with timeouts, restricted imports, isolated workdir. |
| **Time Overrun** | Sandbox (M2) and Jinja template (M3) underestimation. | M2: cap sandbox at 3h. M3: template with modular fallbacks. |
| **Agentic Narrative** | Pipeline runs rigidly without visible agent reasoning. | Log LLM thinking steps and execution logs to `AgentState`. |

---

# 📐 Member 3 Detailed Implementation Blueprint & Architecture

## Shared State Contract (`state.py`)
```python
from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    csv_path: str
    profile: Dict[str, Any]
    profile_report_path: str
    analysis_plan: List[Dict[str, Any]]
    analysis_results: List[Dict[str, Any]]
    generated_files: List[str]
    execution_log: List[Dict[str, Any]]
    reflection_notes: List[str]
    validation_report: Dict[str, Any]
    insights: List[Dict[str, Any]]
    recommendations: List[str]
    report_path: str
    error_log: List[str]
    status: str
```

## Member 3 Module Deliverables
1. `state.py`: Explicit schema contract for `AgentState`.
2. `validation.py`: Data verification engine (correlation bounds check, soft key matching, constant column handling).
3. `prompts.py`: Structured LLM prompts enforcing numeric evidence and preventing insight contradictions.
4. `templates/report_template.html`: Modern, responsive Jinja2 HTML report template with dynamic stat cards, chart grid, and fallbacks.
5. `report_generator.py`: HTML report compiler.
6. `insight_node.py`: Main LangGraph node function `insight_node(state: AgentState) -> AgentState`.
7. `test_insight.py`: `pytest` test suite (mocking state, partial failures, validation edge cases).
8. `README_INSIGHT.md`: Module documentation and integration guide.
