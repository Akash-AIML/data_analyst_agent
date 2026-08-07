"""Canonical shared AgentState contract — single source of truth.

All three members import `AgentState` from here (directly, or via the
`agents/state.py` re-export). Rules:
  * M1 (Profiler)  writes: csv_path, profile, profile_report_path, status
  * M2 (Analysis)  writes: analysis_plan, analysis_results, generated_files,
                            execution_log, reflection_notes
  * M3 (Insight)   writes: validation_report, insights, recommendations,
                            report_path, pdf_path, report_status
  * Shared: error_log, thinking_log, status

`analysis_results`: canonical type is a **list** of result dicts, each shaped
`{task_id, title, kind, column?, status, stats, files}` so Member 3's
validation can cross-check it. (Member 2's node currently writes a dict keyed
by task name — see the integration notes; align on the list form.)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """Everything one full pipeline run carries between nodes."""

    # --- Input / M1 Profiler -----------------------------------------
    csv_path: str
    profile: Dict[str, Any]
    profile_report_path: str

    # --- M2 Analysis (planner + executor + reflector) ----------------
    analysis_plan: List[Dict[str, Any]]
    analysis_results: List[Dict[str, Any]]
    generated_files: List[str]
    execution_log: List[Dict[str, Any]]
    reflection_notes: List[str]

    # --- M3 Insight & Report -------------------------------------------
    validation_report: Dict[str, Any]
    insights: List[Dict[str, Any]]
    recommendations: List[str]
    report_path: str
    pdf_path: Optional[str]
    report_status: str  # "ok" | "degraded" | "failed"

    # --- Shared ------------------------------------------------------
    error_log: List[str]
    thinking_log: List[str]
    status: str  # "running" | "in_progress" | "completed" | "failed"