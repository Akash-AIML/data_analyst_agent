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
from pydantic import BaseModel, Field, field_validator


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
    llm_calls: List[Dict[str, Any]]
    status: str  # "running" | "in_progress" | "completed" | "failed"


def _as_str_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return list(v)


class StateContract(BaseModel):
    """Validating mirror of ``AgentState``."""

    model_config = {"validate_assignment": True}

    csv_path: Optional[str] = None
    profile: Dict[str, Any] = Field(default_factory=dict)
    profile_report_path: Optional[str] = None
    analysis_plan: List[Dict[str, Any]] = Field(default_factory=list)
    analysis_results: List[Dict[str, Any]] = Field(default_factory=list)
    generated_files: List[str] = Field(default_factory=list)
    execution_log: List[Dict[str, Any]] = Field(default_factory=list)
    reflection_notes: List[str] = Field(default_factory=list)
    validation_report: Dict[str, Any] = Field(default_factory=dict)
    insights: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    report_path: Optional[str] = None
    pdf_path: Optional[str] = None
    report_status: str = "ok"
    error_log: List[str] = Field(default_factory=list)
    thinking_log: List[str] = Field(default_factory=list)
    llm_calls: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "in_progress"

    @field_validator(
        "generated_files", "reflection_notes", "recommendations",
        "error_log", "thinking_log", mode="before",
    )
    @classmethod
    def _coerce_str_lists(cls, v: Any) -> List[str]:
        return _as_str_list(v)


def build_state(**kwargs: Any) -> Dict[str, Any]:
    """Build a plain ``AgentState`` dict, validated by ``StateContract``.

    Raises a ``pydantic.ValidationError`` if any supplied key/type violates
    the contract - use this at integration points to catch drift instantly.
    """
    model = StateContract(**kwargs)
    return model.model_dump(exclude_none=True)


__all__ = ["AgentState", "StateContract", "build_state"]