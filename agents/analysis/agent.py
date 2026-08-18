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
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from dotenv import load_dotenv

from agents.analysis.prompts import (
    CODE_GENERATION_PROMPT,
    ERROR_FIX_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    REFLECTION_PROMPT,
)
from agents.analysis.schemas import (
    KIND_MAP,
    AnalysisPlan,
    AnalysisReflection,
)
from agents.analysis.templates import template_for
from llm import plain_invoke, structured_invoke
from state import AgentState
from tools.python_executor import execute_code

load_dotenv(override=True)

logger = logging.getLogger(__name__)


MAX_RETRIES = 3
MAX_PLAN_TASKS = int(os.environ.get("MAX_PLAN_TASKS", "8"))


def planner_node(state: AgentState) -> AgentState:
    """Creates a structured analysis plan from the dataset profile.

    Deterministic by default: the plan is scheduled from the profiled columns
    using the templated task kinds (zero LLM spend). Set ``LLM_PLANNER=1`` to
    opt back into LLM planning.
    """
    profile = state.get("profile", {})
    if not profile:
        state.setdefault("error_log", []).append("Planner: No profile found in state")
        state["status"] = "failed"
        return state

    try:
        use_llm = os.getenv("LLM_PLANNER", "0") == "1"
        if use_llm:
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
            tasks = _materialize_tasks(parsed)
        else:
            tasks = _deterministic_plan(profile)
            tasks = _materialize_tasks(tasks)
            if state is not None:
                state.setdefault("llm_calls", []).append(
                    {"task": "PLANNER", "model": "deterministic", "ok": True, "cost_usd": 0.0}
                )
            logger.info("Planner used deterministic template plan (LLM_PLANNER not set)")

        if len(tasks) > MAX_PLAN_TASKS:
            logger.warning(
                "Plan has %d tasks but MAX_PLAN_TASKS=%d — truncating to control LLM cost",
                len(tasks), MAX_PLAN_TASKS,
            )
            tasks = tasks[:MAX_PLAN_TASKS]

        state["analysis_plan"] = tasks
        state["analysis_results"] = []
        state["execution_log"] = []
        state["generated_files"] = []

        logger.info("Planner created %d tasks", len(tasks))
        for t in tasks:
            logger.info("  - task %s: %s", t.get("task_id"), t.get("task_name"))
    except Exception as e:  # noqa: BLE001
        state.setdefault("error_log", []).append(f"Planner: Unexpected error: {e}")
        state["analysis_plan"] = []
        state["status"] = "failed"
    return state


def _deterministic_plan(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build a zero-LLM plan from the profile's column dtype breakdown.

    Every scheduled task maps 1:1 onto an executor template so the whole plan
    runs without any model call (and every result is verified by recompute).
    """
    numeric = [c for c in (profile.get("numeric_columns") or []) if isinstance(c, str)]
    categorical = [c for c in (profile.get("categorical_columns") or []) if isinstance(c, str)]
    all_cols = numeric + categorical
    plan: List[Dict[str, Any]] = []

    if not all_cols:
        plan.append({
            "task_id": 1,
            "task_name": "missing_value_analysis",
            "description": "Dataset-wide completeness check",
            "column": None,
        })
        return plan

    tid = 1
    if categorical:
        cat_sample = categorical[0]
        plan.append({
            "task_id": tid,
            "task_name": "category_frequency",
            "description": f"Top value counts for categorical column {cat_sample}",
            "column": cat_sample,
        })
        tid += 1

    if len(numeric) >= 1:
        plan.append({
            "task_id": tid,
            "task_name": "descriptive_statistics",
            "description": "Per-column mean/median/std/min/max across all numeric columns",
            "column": None,
        })
        tid += 1

    if len(numeric) >= 2 and len(all_cols) >= 2:
        plan.append({
            "task_id": tid,
            "task_name": "correlation_analysis",
            "description": f"Pearson correlation among {len(numeric)} numeric columns",
            "column": None,
        })
        tid += 1

    if numeric:
        plan.append({
            "task_id": tid,
            "task_name": "outlier_detection",
            "description": "IQR-based outlier detection on numeric columns",
            "column": None,
        })
        tid += 1

    if numeric:
        plan.append({
            "task_id": tid,
            "task_name": "distribution_plots",
            "description": "Histogram distribution plot per numeric column",
            "column": None,
        })
        tid += 1

    plan.append({
        "task_id": tid,
        "task_name": "missing_value_analysis",
        "description": "Per-column missing/null counts",
        "column": None,
    })

    return plan


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
    """Runs pending tasks; writes the canonical ``analysis_results`` list."""
    plan = state.get("analysis_plan") or []
    profile = state.get("profile", {})
    csv_path = state.get("csv_path", "")

    all_pending = [
        t for t in plan
        if t.get("status") == "pending"
        and t.get("attempts", 0) < t.get("max_retries", MAX_RETRIES)
    ]
    if not all_pending:
        logger.info("No pending tasks to execute")
        return state

    # Batch parallel execution for multiple pending deterministic tasks
    det_tasks = [
        t for t in all_pending
        if template_for(t.get("task_name", ""), profile) is not None
    ]
    if len(det_tasks) >= 1:
        logger.info("Running %d deterministic tasks in parallel", len(det_tasks))
        workers = min(8, len(det_tasks))
        futures = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for t in det_tasks:
                code = template_for(t.get("task_name", ""), profile)
                fut = pool.submit(execute_code, code, csv_path)
                futures[fut] = (t, code)

        for fut in as_completed(futures):
            task, code = futures[fut]
            attempt = int(task.get("attempts", 0)) + 1
            task["attempts"] = attempt
            try:
                res = fut.result()
                log_entry = {
                    "task_id": task.get("task_id"),
                    "task_name": task.get("task_name"),
                    "attempt": attempt,
                    "code": code[:500],
                    "success": res["success"],
                    "stdout": res["stdout"][:500],
                    "stderr": res["stderr"][:500],
                    "error": res.get("error"),
                }
                state.setdefault("execution_log", []).append(log_entry)
                if res["success"]:
                    _record_task_result(state, task, res)
                    logger.info("Parallel task %s completed", task.get("task_id"))
                else:
                    task["last_error"] = res.get("error", "Unknown error")
                    task["last_stdout"] = res.get("stdout", "")
                    task["status"] = "failed"
            except Exception as e:
                task["last_error"] = str(e)
                task["status"] = "failed"
                state.setdefault("execution_log", []).append({
                    "task_id": task.get("task_id"),
                    "task_name": task.get("task_name"),
                    "attempt": attempt,
                    "code": code[:500],
                    "success": False,
                    "stdout": "",
                    "stderr": "",
                    "error": str(e),
                })
        return state

    pending = all_pending[0]
    attempt = int(pending.get("attempts", 0)) + 1
    logger.info(
        "Executing task %s: %s (attempt %d)",
        pending.get("task_id"), pending.get("task_name"), attempt,
    )
    numeric_cols = profile.get("numeric_columns", [])
    categorical_cols = profile.get("categorical_columns", [])

    # Deterministic tasks skip the LLM entirely (saves calls + 429s).
    templated_code = template_for(pending.get("task_name", ""), profile)
    if templated_code is not None:

        logger.info(
            "Task %s uses deterministic template (no LLM call)",
            pending.get("task_name"),
        )
        try:
            result = execute_code(templated_code, csv_path)
        except Exception as e:  # noqa: BLE001  # template itself should be static
            pending["attempts"] = attempt
            pending["last_error"] = f"template execution failed: {e}"
            state.setdefault("execution_log", []).append({
                "task_id": pending.get("task_id"),
                "task_name": pending.get("task_name"),
                "attempt": attempt,
                "code": templated_code[:500],
                "success": False,
                "stdout": "",
                "stderr": "",
                "error": str(e),
            })
            if attempt >= pending.get("max_retries", MAX_RETRIES):
                pending["status"] = "failed"
            return state
        log_entry = {
            "task_id": pending.get("task_id"),
            "task_name": pending.get("task_name"),
            "attempt": attempt,
            "code": templated_code[:500],
            "success": result["success"],
            "stdout": result["stdout"][:500],
            "stderr": result["stderr"][:500],
            "error": result.get("error"),
        }
        state.setdefault("execution_log", []).append(log_entry)
        if result["success"]:
            _record_task_result(state, pending, result)
            logger.info("Task %s completed", pending.get("task_id"))
        else:
            pending["last_error"] = result.get("error", "Unknown error")
            pending["last_stdout"] = result.get("stdout", "")
            pending["status"] = "failed"
        return state

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
            _record_task_result(state, pending, result)
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


def _record_task_result(state: AgentState, pending: Dict[str, Any],
                        result: Dict[str, Any]) -> None:
    """Append a completed task's result + generated files to state."""
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
        if os.getenv("LLM_REFLECTOR", "0") != "1":
            # Deterministic reflection: the template plan covers all canonical
            # task kinds, so nothing is missing by construction (zero LLM spend).
            notes.append("Reflection complete (deterministic plan covers all canonical tasks)")
            if state is not None:
                state.setdefault("llm_calls", []).append(
                    {"task": "REFLECTOR", "model": "deterministic", "ok": True, "cost_usd": 0.0}
                )
        else:
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
