"""Shared AgentState contract for the Data Analyst Agent.

Owned jointly by all three team members. Member 3 drafted this; get M1/M2
sign-off on the exact key names before the Day 2 integration session.

Usage:
    from agents.state import AgentState, build_state

The TypedDict documents the shape for all nodes; Pydantic validation
(``validated_state``) is provided so that a mis-keyed field from any
member fails fast during integration instead of silently drifting.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field, field_validator


class AgentState(TypedDict, total=False):
    """Everything one full pipeline run carries between nodes.

    total=False so members can construct partial states (a node only
    reads/writes the keys it owns) while the full contract stays explicit.
    """

    # --- M1: Profiler ------------------------------------------------
    csv_path: str
    profile: Dict[str, Any]
    profile_report_path: str

    # --- M2: Analysis (planner + executor + reflector) ---------------
    analysis_plan: List[Dict[str, Any]]
    analysis_results: List[Dict[str, Any]]
    generated_files: List[str]
    execution_log: List[Dict[str, Any]]
    reflection_notes: List[str]

    # --- M3: Insight & Report (this member) --------------------------
    validation_report: Dict[str, Any]
    insights: List[Dict[str, Any]]
    recommendations: List[str]
    report_path: str
    pdf_path: Optional[str]
    report_status: str  # "ok" | "degraded" | "failed"

    # --- Shared ------------------------------------------------------
    error_log: List[str]
    thinking_log: List[str]
    status: str  # pipeline status: "in_progress" | "completed" | "failed"


# ---------------------------------------------------------------------------
# Pydantic counterpart: validates the contract, used in tests and at node
# boundaries. Assigning a wrong key name or type fails fast here.
# ---------------------------------------------------------------------------

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
