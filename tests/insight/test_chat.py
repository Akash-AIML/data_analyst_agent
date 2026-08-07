"""Tests for the report-grounded chatbot core."""

from __future__ import annotations

import pytest

from agents.insight import chat
from agents.insight.insight_node import build_insight_node
from tests.insight import fixtures
from tests.insight.fake_llm import FakeChatModel



@pytest.fixture(scope="module")
def healthy_state():
    return build_insight_node(FakeChatModel())(fixtures.healthy_state())


@pytest.fixture(scope="module")
def partial_state():
    return build_insight_node(FakeChatModel())(fixtures.partial_state())


def test_build_context_covers_all_sections(healthy_state):
    ctx = chat.build_context(healthy_state)
    for section in (
        "DATASET", "PROFILE_COLUMNS", "VALIDATION", "INSIGHTS",
        "RECOMMENDATIONS", "EXECUTION_LOG", "REPORT",
    ):
        assert section in ctx
    assert "Average sale value" in ctx  # insight body present


@pytest.fixture(scope="module")
def failed_state():
    return build_insight_node(FakeChatModel())(fixtures.failed_state())


def test_build_context_includes_errors_when_present(failed_state):
    ctx = chat.build_context(failed_state)
    assert "=== ERROR_LOG ===" in ctx
    assert "sklearn" in ctx


def _report_block(ctx: str) -> str:
    lines = ctx.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == "=== REPORT ===")
    return "\n".join(lines[start:])


def test_context_reports_healthy_status(healthy_state):
    assert "status: ok" in _report_block(chat.build_context(healthy_state))


def test_degraded_report_reflects_errors(partial_state):
    ctx = chat.build_context(partial_state).lower()
    assert "degraded" in ctx


def test_persistence_roundtrip(tmp_path, healthy_state):
    path = str(tmp_path / "nested" / "report_state.json")
    chat.save_report_state(healthy_state, path)
    loaded = chat.load_report_state(path)
    assert loaded["csv_path"] == healthy_state["csv_path"]
    assert loaded["insights"] == healthy_state["insights"]
    assert "report_status" in loaded


def test_save_state_is_nan_safe(tmp_path):
    import os

    weird = dict(fixtures.healthy_state())
    weird["validation_report"] = {"status": "warnings", "x": float("nan")}
    path = str(tmp_path / "state.json")
    chat.save_report_state(weird, path)
    assert os.path.exists(path)


def test_answer_responds_text():
    reply = chat.answer(FakeChatModel(), "What is the average sale?", "some context")
    assert isinstance(reply, str) and reply


def test_answer_with_history():
    reply = chat.answer(
        FakeChatModel(),
        "Tell me more",
        "console",
        history=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ],
    )
    assert isinstance(reply, str) and reply


def test_context_from_file(tmp_path, healthy_state):
    path = str(tmp_path / "state.json")
    chat.save_report_state(healthy_state, path)
    ctx = chat.context_from_file(path)
    assert "Average sale value" in ctx