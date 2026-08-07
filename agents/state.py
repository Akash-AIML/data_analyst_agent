"""Shared AgentState contract + Pydantic validation mirror.

Single source of truth for the ``AgentState`` TypedDict lives in
``state/graph_state.py``; this module re-exports it and adds a validating
Pydantic ``StateContract``/``build_state`` (used by Member 3's fixtures/tests
so a mis-keyed field fails fast instead of silently drifting).

Usage:
    from agents.state import AgentState, build_state
    from state import AgentState            # same class
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from state.graph_state import AgentState  # noqa: F401  (re-exported)

__all__ = ["AgentState", "StateContract", "build_state"]


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
