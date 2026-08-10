"""Regression tests for the central ``llm`` module (no API key needed).

Use the deterministic ``FakeChatModel`` stub so ``plain_invoke`` /
``structured_invoke`` can be exercised offline. Guards against the
``NameError`` regression where ``plain_invoke`` referenced the undefined
``_llm_model`` instead of ``_llm_model_name``.
"""

import pytest

from llm import plain_invoke, structured_invoke
from tests.insight.fake_llm import FakeChatModel
from agents.analysis.schemas import AnalysisPlan


@pytest.fixture
def chat():
    return FakeChatModel()


@pytest.fixture
def state():
    return {"llm_calls": []}


def test_plain_invoke_returns_text(chat, state):
    text = plain_invoke(
        task="EXECUTOR",
        messages=[{"role": "user", "content": "Write code"}],
        temperature=0.1,
        chat=chat,
        state=state,
    )
    assert isinstance(text, str)
    assert text.strip()  # non-empty reply

    assert len(state["llm_calls"]) == 1
    record = state["llm_calls"][0]
    assert record["task"] == "EXECUTOR"
    assert record["ok"] is True
    assert record["model"]


def test_plain_invoke_accepts_string_message(chat, state):
    text = plain_invoke(
        task="EXECUTOR",
        messages="Just say hi.",
        chat=chat,
        state=state,
    )
    assert isinstance(text, str)
    assert len(state["llm_calls"]) == 1


def test_structured_invoke_records_call_even_on_parse_failure(chat, state):
    # FakeChatModel returns insights JSON, not a valid AnalysisPlan — so the
    # call should degrade to None (gracefully) but still be logged.
    parsed = structured_invoke(
        task="PLANNER",
        messages=[{"role": "user", "content": "Plan it"}],
        schema=AnalysisPlan,
        temperature=0.1,
        chat=chat,
        state=state,
    )
    assert parsed is None or isinstance(parsed, AnalysisPlan)
    assert len(state["llm_calls"]) == 1
    assert state["llm_calls"][0]["task"] == "PLANNER"
    assert "model" in state["llm_calls"][0]


def test_no_llm_calls_appended_without_state(chat):
    text = plain_invoke(task="EXECUTOR", messages="hi", chat=chat)
    assert isinstance(text, str)