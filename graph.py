"""LangGraph integration pipeline linking Profiler, Analysis, and Insight agents.

A real ``StateGraph`` (not a hand-written loop):
    START -> profiler -> planner -> executor (self-loop while pending)
          -> reflector (may append tasks, looping back to executor)
          -> insight -> END

If the profiler fails, control flows straight to the insight node so a
degraded-but-useful report is still produced. State is the shared
``AgentState`` dict; each node mutates and returns it in place.

LangSmith tracing is enabled automatically when ``LANGSMITH_TRACING_V2=true``
(or the legacy ``LANGSMITH_TRACING=true``) is set with a configured API key;
``invoke(..., config=...)`` is forwarded as-is so callers can attach run
metadata/tags for filtering in the LangSmith UI.
"""

import os
import sys
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from agents.analysis.agent import executor_node, planner_node, reflector_node
from agents.insight.insight_node import build_insight_node
from agents.profiler.agent import profiler_node
from llm import _tracing_metadata
from state import AgentState


def _default_runnable_config(state: AgentState,
                             config: Optional[RunnableConfig] = None) -> RunnableConfig:
    """Merge caller config with LangSmith defaults.

    Tags every LangSmith run with ``ai-data-analyst`` and project metadata
    (csv_path, status) so traces are filterable. The caller's ``config``
    wins on conflict.
    """
    base: RunnableConfig = {
        "tags": ["ai-data-analyst"],
        "metadata": _tracing_metadata(state, {"graph": "data_analyst_agent"}),
        "run_name": f"pipeline::{state.get('csv_path', 'unknown')}",
    }
    if not config:
        return base
    merged: RunnableConfig = {**base, **config}
    merged.setdefault("metadata", {})
    if "metadata" in base:
        merged["metadata"] = {**base["metadata"], **merged.get("metadata", {})}
    merged["tags"] = list({*(base.get("tags") or []), *(config.get("tags") or [])})
    return merged


def _has_pending(state: Dict[str, Any]) -> bool:
    return any(
        t.get("status") == "pending"
        for t in (state.get("analysis_plan") or [])
    )


def _profiler_route(state: Dict[str, Any]) -> str:
    return "insight" if state.get("status") == "failed" else "planner"


def _executor_route(state: Dict[str, Any]) -> str:
    return "executor" if _has_pending(state) else "reflector"


def _reflector_route(state: Dict[str, Any]) -> str:
    return "executor" if _has_pending(state) else "insight"


def create_pipeline(llm_model=None):
    """Compile and return a runnable LangGraph pipeline.

    ``llm_model`` binds the Insight node (tests pass a stub). Analysis and
    Profiler nodes build their models from ``llm.py`` env config.
    """
    insight_node = build_insight_node(llm_model)

    graph = StateGraph(AgentState)

    graph.add_node("profiler", profiler_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("reflector", reflector_node)
    graph.add_node("insight", insight_node)

    graph.add_edge(START, "profiler")
    graph.add_conditional_edges("profiler", _profiler_route, {"planner": "planner", "insight": "insight"})
    graph.add_edge("planner", "executor")
    graph.add_conditional_edges("executor", _executor_route, {"executor": "executor", "reflector": "reflector"})
    graph.add_conditional_edges("reflector", _reflector_route, {"executor": "executor", "insight": "insight"})
    graph.add_edge("insight", END)

    compiled = graph.compile()
    return compiled


if __name__ == "__main__":
    from tests.insight import fixtures
    pipeline = create_pipeline()
    sample_csv = os.path.abspath("data/sample_sales.csv")
    initial_state = fixtures.healthy_state()
    if os.path.exists(sample_csv):
        initial_state["csv_path"] = sample_csv
    final_state = pipeline.invoke(
        initial_state,
        config=_default_runnable_config(initial_state),
    )
    print("\n" + "=" * 60)
    print("PIPELINE EXECUTION COMPLETED")
    print("=" * 60)
    print(f"Report Status: {final_state.get('report_status')}")
    print(f"Report Path:   {final_state.get('report_path')}")
    print(f"PDF Path:      {final_state.get('pdf_path')}")
    print(f"Insights:      {len(final_state.get('insights', []))}")
    print(f"Recommendations: {len(final_state.get('recommendations', []))}")
