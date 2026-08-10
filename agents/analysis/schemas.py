"""Pydantic schemas for the Analysis Agent's structured LLM outputs.

These replace the old free-form ``json.loads`` parsing so the planner and
reflector get machine-validated output instead of bare text. The executor
also declares the canonical result shape here so validation/evidence can
cross-check real numbers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# The task kinds the deterministic validator understands. Kept in sync with
# ``agents/insight/validation.py``.
TASK_KINDS = [
    "descriptive_statistics",
    "missing_value_analysis",
    "correlation_analysis",
    "outlier_detection",
    "distribution_plots",
    "category_frequency",
]


class AnalysisTask(BaseModel):
    """One planned analysis step."""

    task_id: int = Field(description="sequential id starting at 1")
    task_name: str = Field(
        description=(
            "one of: descriptive_statistics | missing_value_analysis | "
            "correlation_analysis | outlier_detection | distribution_plots | "
            "category_frequency"
        )
    )
    description: str = Field(description="what the task computes, why it matters")
    column: Optional[str] = Field(
        default=None,
        description="target column name for single-column tasks, if applicable",
    )


class AnalysisPlan(BaseModel):
    """Structured output of the planner node."""

    tasks: List[AnalysisTask] = Field(description="ordered list of analysis tasks")


class MissingTask(BaseModel):
    """A task the reflector wants to add because the plan was incomplete."""

    task_name: str
    description: str
    column: Optional[str] = None


class AnalysisReflection(BaseModel):
    """Structured output of the reflector node."""

    complete: bool = Field(description="true if all necessary analyses were performed")
    notes: List[str] = Field(
        default_factory=list,
        description="short human notes explaining the verdict",
    )
    additional_tasks: List[MissingTask] = Field(
        default_factory=list,
        description="tasks to add to the plan when complete is false",
    )


KIND_MAP = {
    "descriptive_statistics": "mean",
    "missing_value_analysis": "missing",
    "correlation_analysis": "correlation",
    "outlier_detection": "count",
    "distribution_plots": "count",
    "category_frequency": "category_frequency",
}


def task_to_result(task: AnalysisTask | Dict[str, Any], stats: Dict[str, Any],
                   status: str = "completed") -> Dict[str, Any]:
    """Build the canonical analysis_results entry from a plan task + stats."""
    if isinstance(task, AnalysisTask):
        name = task.task_name
        col = task.column
        task_id = task.task_id
        title = f"{name}"
    else:
        name = task.get("task_name", "generic")
        col = task.get("column")
        task_id = task.get("task_id")
    entry: Dict[str, Any] = {
        "task_id": task_id,
        "title": name,
        "kind": KIND_MAP.get(name, "generic"),
        "status": status,
        "stats": stats or {},
    }
    if col:
        entry["column"] = col
    return entry