"""LangGraph integration pipeline linking Member 1 (Profiler), Member 2 (Analysis), and Member 3 (Insight)."""

from typing import Dict, Any
from state import AgentState
from agents.insight.insight_node import build_insight_node

# Placeholder stubs for M1 & M2 if not yet merged
try:
    from agents.profiler.profiler_node import profiler_node
except ImportError:
    def profiler_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Stub profiler node used prior to Member 1 merge."""
        state = dict(state)
        if "profile" not in state or not state["profile"]:
            state["profile"] = {"columns": {"sample": {"type": "numeric"}}, "rows": 100}
        state["status"] = "healthy"
        return state

try:
    from agents.analysis.planner_node import planner_node
    from agents.analysis.executor_node import executor_node
except ImportError:
    def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Stub planner node used prior to Member 2 merge."""
        state = dict(state)
        state["analysis_plan"] = [{"task": "Default EDA Summary", "status": "pending"}]
        return state

    def executor_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Stub executor node used prior to Member 2 merge."""
        state = dict(state)
        state["analysis_results"] = [
            {
                "task": "Default EDA Summary",
                "metrics": {"sample_metric": 42.0},
                "correlations": {"sample_corr": 0.95}
            }
        ]
        state["generated_files"] = []
        return state

def create_pipeline(llm_model=None):
    """Returns a step-by-step pipeline runner connecting M1, M2, and M3."""
    insight_node = build_insight_node(llm_model)

    def run_pipeline(initial_state: Dict[str, Any]) -> Dict[str, Any]:
        s1 = profiler_node(initial_state)
        s2 = planner_node(s1)
        s3 = executor_node(s2)
        s4 = insight_node(s3)
        return s4

    return run_pipeline

if __name__ == "__main__":
    from agents.insight.tests import fixtures
    pipeline = create_pipeline()
    final_state = pipeline(fixtures.healthy_state())
    print("Pipeline Execution Completed!")
    print(f"Status: {final_state.get('report_status')} | Report: {final_state.get('report_path')}")
