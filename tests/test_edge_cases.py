"""Unit tests for edge-case datasets (empty, single row, all nulls, mixed types, wide CSV)."""

from __future__ import annotations

import os
import pytest

from tools.profiling_tool import ProfilingTool
from agents.profiler.agent import profiler_node
from agents.analysis.agent import planner_node, executor_node
from state import AgentState

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "csvs")


def test_empty_csv_handling(tmp_path):
    csv_path = os.path.join(FIXTURES_DIR, "empty.csv")
    tool = ProfilingTool()
    res = tool._run(csv_path, output_dir=str(tmp_path))
    assert "ERROR" in res or "empty" in res.lower()

    state: AgentState = {"csv_path": csv_path, "status": "running"}
    out_state = profiler_node(state)
    assert out_state["status"] == "failed"
    assert len(out_state.get("error_log", [])) > 0


def test_single_row_csv(tmp_path):
    csv_path = os.path.join(FIXTURES_DIR, "single_row.csv")
    tool = ProfilingTool()
    res = tool._run(csv_path, output_dir=str(tmp_path))
    assert "SUCCESS" in res

    state: AgentState = {"csv_path": csv_path, "status": "running"}
    prof_state = profiler_node(state)
    assert prof_state["status"] != "failed"
    assert prof_state["profile"]["rows"] == 1

    plan_state = planner_node(prof_state)
    assert len(plan_state.get("analysis_plan", [])) > 0


def test_all_nulls_csv(tmp_path):
    csv_path = os.path.join(FIXTURES_DIR, "all_nulls.csv")
    tool = ProfilingTool()
    res = tool._run(csv_path, output_dir=str(tmp_path))
    assert "SUCCESS" in res

    state: AgentState = {"csv_path": csv_path, "status": "running"}
    prof_state = profiler_node(state)
    assert prof_state["status"] != "failed"
    assert prof_state["profile"]["missing_values"] is not None


def test_mixed_types_csv(tmp_path):
    csv_path = os.path.join(FIXTURES_DIR, "mixed_types.csv")
    tool = ProfilingTool()
    res = tool._run(csv_path, output_dir=str(tmp_path))
    assert "SUCCESS" in res

    state: AgentState = {"csv_path": csv_path, "status": "running"}
    prof_state = profiler_node(state)
    plan_state = planner_node(prof_state)
    exec_state = executor_node(plan_state)
    assert exec_state["status"] != "failed"


def test_wide_200cols_csv(tmp_path):
    csv_path = os.path.join(FIXTURES_DIR, "wide_200cols.csv")
    tool = ProfilingTool()
    res = tool._run(csv_path, output_dir=str(tmp_path))
    assert "SUCCESS" in res

    state: AgentState = {"csv_path": csv_path, "status": "running"}
    prof_state = profiler_node(state)
    col_cnt = prof_state["profile"].get("columns") or prof_state["profile"].get("columns_count")
    assert col_cnt == 200

