"""End-to-end integration test suite for the complete pipeline graph."""

import os
import pytest
from state import build_state
from graph import create_pipeline
from tests.insight.fake_llm import FakeChatModel


def test_create_pipeline_returns_runner():
    pipeline = create_pipeline(FakeChatModel())
    assert callable(pipeline)


def test_full_pipeline_with_fake_llm(tmp_path):
    pipeline = create_pipeline(FakeChatModel())
    state = build_state(
        csv_path="data/sample_sales.csv",
        status="running",
    )
    final_state = pipeline(state)
    assert "report_status" in final_state
    assert final_state["report_status"] in ("ok", "degraded", "failed")

