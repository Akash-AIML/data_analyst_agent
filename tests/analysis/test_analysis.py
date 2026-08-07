# tests/analysis/test_analysis.py
"""Standalone pytest suite for Analysis Agent — uses mock profile."""

import json
import os
import sys
import pytest

from agents.analysis.agent import planner_node, executor_node, reflector_node


def create_mock_state():
    """Creates a state object matching what Member 1 would produce."""
    mock_path = os.path.join(os.path.dirname(__file__), "..", "..", "mocks", "mock_profile_analysis.json")
    with open(mock_path, "r") as f:
        mock = json.load(f)
    
    state = {
        "csv_path": mock["csv_path"],
        "profile": mock["profile"],
        "profile_report_path": mock["profile_report_path"],
        "analysis_plan": None,
        "analysis_results": None,
        "generated_files": None,
        "execution_log": None,
        "reflection_notes": None,
        "validation_report": None,
        "insights": None,
        "recommendations": None,
        "report_path": None,
        "error_log": [],
        "status": "running"
    }
    return state


@pytest.fixture
def mock_analysis_state():
    return create_mock_state()


def _has_llm_key() -> bool:
    return bool(os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY"))


LLM_SKIP = pytest.mark.skipif(
    not _has_llm_key(),
    reason="LLM API Key (GROQ/GEMINI/OPENAI) not set — skipping Analysis Agent LLM integration tests",
)


@LLM_SKIP
def test_planner(mock_analysis_state):
    state = planner_node(mock_analysis_state)
    assert state["analysis_plan"] is not None, "Plan should not be None"
    assert len(state["analysis_plan"]) > 0, "Plan should have at least 1 task"
    
    for task in state["analysis_plan"]:
        assert "task_id" in task
        assert "task_name" in task
        assert "status" in task
        assert task["status"] == "pending"


@LLM_SKIP
def test_executor_and_reflector(mock_analysis_state):
    state = planner_node(mock_analysis_state)
    state = executor_node(state)
    
    execution_log = state.get("execution_log", [])
    assert len(execution_log) > 0, "Should have at least 1 log entry"
    
    # Run executor until all tasks done or failed
    max_iterations = len(state["analysis_plan"]) * 4
    for _ in range(max_iterations):
        pending = [t for t in state["analysis_plan"] if t["status"] == "pending"]
        if not pending:
            break
        state = executor_node(state)
    
    state = reflector_node(state)
    notes = state.get("reflection_notes", [])
    assert len(notes) > 0, "Should have reflection notes"


@LLM_SKIP
def test_error_recovery(mock_analysis_state):
    state = mock_analysis_state
    state["analysis_plan"] = [{
        "task_id": 99,
        "task_name": "error_test",
        "description": "Generate Python code that prints df['non_existent_column'] to trigger a KeyError",
        "status": "pending",
        "code": None,
        "attempts": 0,
        "max_retries": 3
    }]
    state["execution_log"] = []
    state["analysis_results"] = {}
    state["generated_files"] = []
    
    state = executor_node(state)
    log = state["execution_log"]
    assert len(log) > 0

