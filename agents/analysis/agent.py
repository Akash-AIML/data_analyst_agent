# agents/analysis/agent.py
"""Analysis Agent: planner -> executor -> reflector (LangGraph nodes).

M2 contract (matches state/graph_state.py + agents/analysis/schemas.py):
  * ``analysis_plan``        -> list of tasks: {task_id, task_name, description,
                                column?, status, attempts, max_retries}
  * ``analysis_results``     -> canonical LIST of result dicts
       {task_id, title, kind, column?, status, stats}
    where ``stats`` are the numeric values the executor captured via the
    ``RESULT_JSON`` sandbox protocol - the exact numbers validation uses.
  * ``execution_log``        -> one entry per attempt (task, code, outcome)
  * ``generated_files``      -> list of image paths produced by tasks
  * ``reflection_notes``     -> human-readable QA notes

LLM wiring is centralized in ``llm.py`` (primary + Groq failover, usage logs).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from dotenv import load_dotenv

from state import AgentState
from llm import structured_invoke, plain_invoke

from agents.analysis.prompts import (
    PLANNER_SYSTEM_PROMPT,
    CODE_GENERATION_PROMPT,
    ERROR_FIX_PROMPT,
    REFLECTION_PROMPT,
)
from agents.analysis.schemas import (
    AnalysisPlan,
    AnalysisReflection,
    KIND_MAP,
)

from tools.python_executor import execute_code

load_dotenv(override=True)

logger = logging.getLogger(__name__)


MAX_RETRIES = 3


def planner_node(state: AgentState) -> AgentState:
    """Creates a structured analysis plan from the dataset profile."""
    profile = state.get("profile", {})
    if not profile:
        state.setdefault("error_log", []).append("Planner: No profile found in state")
        state["status"] = "failed"
        return state

    try:
        parsed = structured_invoke(
            task="PLANNER",
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user",
                 "content": f"Here is the dataset profile:\n{json.dumps(profile, indent=2)}\n\nCreate an analysis plan."},
            ],
            schema=AnalysisPlan,
            temperature=0.1,
            state=state,
        )
        analysis_plan = _materialize_tasks(parsed)

        state["analysis_plan"] = analysis_plan
        state["analysis_results"] = []
        state["execution_log"] = []
        state["generated_files"] = []

        logger.info("Planner created %d tasks", len(analysis_plan))
        for t in analysis_plan:
            logger.info("  - task %s: %s", t.get("task_id"), t.get("task_name"))
    except Exception as e:  # noqa: BLE001
        state.setdefault("error_log", []).append(f"Planner: Unexpected error: {e}")
        state["analysis_plan"] = []
        state["status"] = "failed"
    return state


def _materialize_tasks(parsed: Any) -> List[Dict[str, Any]]:
    """Turn planner output (AnalysisPlan | dict | list) into task dicts."""
    tasks: List[Dict[str, Any]] = []

    if parsed is None:
        return tasks

    if isinstance(parsed, AnalysisPlan):
        raw = parsed.tasks
        # Pydantic object model_dump OR plain dicts
        for item in raw:
            tasks.append(item if isinstance(item, dict) else item.model_dump())
    elif isinstance(parsed, dict):
        cand = parsed.get("tasks", [])
        if isinstance(cand, list):
            tasks = [t if isinstance(t, dict) else t.model_dump() for t in cand]
        elif isinstance(parsed.get("task_name"), str):
            tasks = [parsed]
    elif isinstance(parsed, list):
        tasks = [t if isinstance(t, dict) else t.model_dump() for t in parsed]

    # Enforce the tracking fields the executor depends on.
    for i, task in enumerate(tasks, start=1):
        task.setdefault("task_id", i)
        task.setdefault("task_name", task.get("task_name", f"task_{i}"))
        task.setdefault("description", task.get("description", ""))
        task.setdefault("column", None)
        task["status"] = "pending"
        task["code"] = None
        task["attempts"] = 0
        task["max_retries"] = MAX_RETRIES
    return tasks


def executor_node(state: AgentState) -> AgentState:
    """Runs next pending task; writes the canonical ``analysis_results`` list."""
    plan = state.get("analysis_plan") or []
    profile = state.get("profile", {})
    csv_path = state.get("csv_path", "")
    pending = next(
        (t for t in plan
         if t.get("status") == "pending"
         and t.get("attempts", 0) < t.get("max_retries", MAX_RETRIES)),
        None,
    )
    if pending is None:
        logger.info("No pending tasks to execute")
        return state

    attempt = int(pending.get("attempts", 0)) + 1
    logger.info(
        "Executing task %s: %s (attempt %d)",
        pending.get("task_id"), pending.get("task_name"), attempt,
    )
    numeric_cols = profile.get("numeric_columns", [])
    categorical_cols = profile.get("categorical_columns", [])

    if attempt > 1 and pending.get("last_error"):
        prompt_txt = ERROR_FIX_PROMPT.format(
            original_code=pending.get("code", ""),
            error_message=pending.get("last_error", ""),
            stdout=pending.get("last_stdout", ""),
            numeric_columns=numeric_cols,
            categorical_columns=categorical_cols,
        )
    else:
        prompt_txt = CODE_GENERATION_PROMPT.format(
            task_description=pending.get("description", ""),
            numeric_columns=numeric_cols,
            categorical_columns=categorical_cols,
        )

    try:
        code = _strip_markdown(plain_invoke(
            task="EXECUTOR",
            messages=[
                {"role": "system", "content": "You generate Python code. Return ONLY code, no markdown."},
                {"role": "user", "content": prompt_txt},
            ],
            temperature=0.1,
            state=state,
        ))

        pending["code"] = code
        pending["attempts"] = attempt

        result = execute_code(code, csv_path)

        log_entry = {
            "task_id": pending.get("task_id"),
            "task_name": pending.get("task_name"),
            "attempt": attempt,
            "code": code[:500],
            "success": result["success"],
            "stdout": result["stdout"][:500],
            "stderr": result["stderr"][:500],
            "error": result.get("error"),
        }
        state.setdefault("execution_log", []).append(log_entry)

        if result["success"]:
            pending["status"] = "completed"
            stats = result.get("stats") or {}
            title = pending.get("task_name", "")
            entry: Dict[str, Any] = {
                "task_id": pending.get("task_id"),
                "title": title,
                "kind": KIND_MAP.get(title, "generic"),
                "status": "completed",
                "stats": stats,
            }
            if pending.get("column"):
                entry["column"] = pending["column"]
            state.setdefault("analysis_results", [])
            state["analysis_results"].append(entry)

            if result.get("generated_files"):
                state.setdefault("generated_files", [])
                state["generated_files"].extend(result["generated_files"])
            logger.info("Task %s completed", pending.get("task_id"))
        else:
            pending["last_error"] = result.get("error", "Unknown error")
            pending["last_stdout"] = result.get("stdout", "")
            if attempt >= pending.get("max_retries", MAX_RETRIES):
                pending["status"] = "failed"
            else:
                logger.info("Task %s failed, will retry (attempt %d)", pending.get("task_id"), attempt)

    except Exception as e:  # noqa: BLE001  (LLM / executor errors)
        pending["attempts"] = attempt
        pending["last_error"] = str(e)
        state.setdefault("execution_log", []).append({
            "task_id": pending.get("task_id"),
            "task_name": pending.get("task_name"),
            "attempt": attempt,
            "code": "",
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": str(e),
        })
        if attempt >= pending.get("max_retries", MAX_RETRIES):
            pending["status"] = "failed"
        else:
            logger.info("Task %s error: %s, retrying", pending.get("task_id"), e)

    return state


def reflector_node(state: AgentState) -> AgentState:
    """QA pass: verifies coverage, appends tasks the planner missed."""
    plan = state.get("analysis_plan", []) or []
    profile = state.get("profile", {})
    results = state.get("analysis_results") or []
    notes = state.get("reflection_notes") or []
    if notes is None:
        notes = []

    pending_tasks = [t for t in plan if t.get("status") == "pending"]
    if pending_tasks:
        note = f"Tasks still pending: {[t.get('task_name') for t in pending_tasks[:5]]}"
        notes.append(note)
        state["reflection_notes"] = notes
        return state

    failed = [t for t in plan if t.get("status") == "failed"]
    if failed:
        note = f"Tasks failed (max retries exceeded): {[t.get('task_name') for t in failed]}"
        notes.append(note)
        logger.info("[REFLECTOR] %s", note)

    completed_names = [t.get("task_name") for t in plan if t.get("status") == "completed"]
    if not completed_names:
        state["reflection_notes"] = notes
        return state

    try:
        profile_summary = {
            "numeric": profile.get("numeric_columns", []),
            "categorical": profile.get("categorical_columns", []),
            "missing": profile.get("missing_values", {}),
            "rows": profile.get("rows", 0),
        }
        user_payload = {
            "profile_summary": profile_summary,
            "completed_tasks": completed_names,
            "results_summary": json.dumps(results, default=str)[:2000],
        }
        parsed = structured_invoke(
            task="REFLECTOR",
            messages=[
                {"role": "system", "content": REFLECTION_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, indent=2, default=str)},
            ],
            schema=AnalysisReflection,
            temperature=0.1,
            state=state,
        )

        if parsed is None:
            notes.append("Reflection failed (no structured output)")
        elif parsed.complete and not parsed.additional_tasks:
            notes.append("Reflection complete - all necessary analyses performed")
        else:
            current_max = max((int(t.get("task_id", 0)) for t in plan), default=0)
            next_id = current_max + 1
            for mt in parsed.additional_tasks:
                plan.append({
                    "task_id": next_id,
                    "task_name": mt.task_name,
                    "description": mt.description,
                    "column": mt.column,
                    "status": "pending",
                    "code": None,
                    "attempts": 0,
                    "max_retries": MAX_RETRIES,
                })
                next_id += 1
            notes.append(f"Reflection added {len(parsed.additional_tasks)} new task(s)")
            state["analysis_plan"] = plan
    except Exception as e:  # noqa: BLE001
        note = f"Reflection LLM call failed: {e}"
        notes.append(note)
        state.setdefault("error_log", []).append(f"Reflector: {note}")

    state["reflection_notes"] = notes
    if state.get("analysis_results"):
        state["status"] = "completed"
    return state


def _strip_markdown(code: str) -> str:
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines).strip()
    return code