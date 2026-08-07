"""LangGraph integration pipeline linking Profiler, Analysis, and Insight agents."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from typing import Dict, Any
from state import AgentState
from agents.profiler.agent import profiler_node
from agents.analysis.agent import planner_node, executor_node, reflector_node
from agents.insight.insight_node import build_insight_node


def create_pipeline(llm_model=None):
    """Returns a step-by-step pipeline runner connecting Profiler, Analysis, and Insight agents."""
    insight_node = build_insight_node(llm_model)

    def run_pipeline(initial_state: Dict[str, Any]) -> Dict[str, Any]:
        s = dict(initial_state)
        s = profiler_node(s)
        if s.get("status") == "failed":
            print(f"[PIPELINE] Profiler failed: {s.get('error_log')}")
            # Even if profiler fails, run insight node to generate degraded report
            return insight_node(s)

        s = planner_node(s)
        # The analysis executor handles one task per call; loop until no
        # pending work remains (retries + task processing), then reflect.
        loop_guard = 0
        while any(t.get("status") == "pending" for t in s.get("analysis_plan", [])):
            s = executor_node(s)
            loop_guard += 1
            if loop_guard > 100:  # safety: avoid infinite loop
                break
        s = reflector_node(s)
        s = insight_node(s)
        return s

    return run_pipeline


if __name__ == "__main__":
    from tests.insight import fixtures
    pipeline = create_pipeline()
    sample_csv = os.path.abspath("data/sample_sales.csv")
    initial_state = fixtures.healthy_state()
    if os.path.exists(sample_csv):
        initial_state["csv_path"] = sample_csv
    final_state = pipeline(initial_state)
    print("\n" + "=" * 60)
    print("PIPELINE EXECUTION COMPLETED")
    print("=" * 60)
    print(f"Report Status: {final_state.get('report_status')}")
    print(f"Report Path:   {final_state.get('report_path')}")
    print(f"PDF Path:      {final_state.get('pdf_path')}")
    print(f"Insights:      {len(final_state.get('insights', []))}")
    print(f"Recommendations: {len(final_state.get('recommendations', []))}")

