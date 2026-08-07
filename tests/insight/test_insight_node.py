"""End-to-end tests for the insight LangGraph node with a stubbed LLM."""

from __future__ import annotations

import os

import pytest

from agents.insight.insight_node import build_insight_node
from tests.insight import fixtures
from tests.insight.fake_llm import FakeChatModel, RECOMMENDATIONS_JSON as _r



@pytest.fixture()
def node(tmp_path):
    return build_insight_node(FakeChatModel(), output_dir=str(tmp_path / "reports"))


def test_healthy_pipeline_produces_full_report(node):
    state = node(fixtures.healthy_state())
    assert state["report_status"] == "ok"
    assert len(state["insights"]) >= 1
    assert state["recommendations"]
    assert state["contradictions"] == []
    assert os.path.exists(state["report_path"])
    assert state["pdf_path"] and os.path.exists(state["pdf_path"])
    # every insight kept must be backed by real evidence values
    evidence_vals = {
        v for e in fixtures.evidence_for(state) for v in e["stats"].values()
    }
    for ins in state["insights"]:
        assert float(ins["value"]) in evidence_vals


def test_insights_with_unverifiable_values_are_dropped(node, tmp_path):
    class HallucinatingLLM(FakeChatModel):
        @property
        def _llm_type(self) -> str:
            return "hallucinating-fake"

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            import json

            from langchain_core.messages import AIMessage
            from langchain_core.outputs import ChatGeneration, ChatResult

            prompt = "\n".join(getattr(m, "content", "") or "" for m in messages)
            if "Derive 3-5 actionable" in prompt:
                payload = fixtures.RECOMMENDATIONS_JSON if hasattr(fixtures, "RECOMMENDATIONS_JSON") else None
                if payload is None:
                    from tests.insight.fake_llm import RECOMMENDATIONS_JSON as _r

                    payload = _r
            elif "Audit these insights" in prompt:
                payload = {"contradictions": []}
            else:
                # one legit insight + one invented number (12345.0 not in evidence)
                payload = {
                    "insights": [
                        {
                            "id": 1, "title": "real", "body": "real one",
                            "evidence": "0.92", "metric": "correlation",
                            "value": 0.92, "confidence": 0.9,
                        },
                        {
                            "id": 2, "title": "hallucinated", "body": "fake",
                            "evidence": "12345.0", "metric": "fake_metric",
                            "value": 12345.0, "confidence": 0.9,
                        },
                    ]
                }
            msg = AIMessage(content=json.dumps(payload))
            return ChatResult(generations=[ChatGeneration(message=msg)])

    state = build_insight_node(
        HallucinatingLLM(), output_dir=str(tmp_path / "reports")
    )(fixtures.healthy_state())
    titles = {i["title"] for i in state["insights"]}
    assert "real" in titles
    assert "hallucinated" not in titles


def test_failed_upstream_degrades_gracefully(node):
    state = node(fixtures.failed_state())
    assert state["report_status"] == "degraded"
    assert not state["insights"]
    assert not state["recommendations"]
    assert os.path.exists(state["report_path"])
    with open(state["report_path"], encoding="utf-8") as fh:
        assert "Error Log" in fh.read()


def test_partial_results_emit_degraded_report(node):
    state = node(fixtures.partial_state())
    assert state["report_status"] == "degraded"
    assert os.path.exists(state["report_path"])


def test_node_never_raises_on_garbage_state(node):
    garbage = {
        "csv_path": "nope.csv",
        "profile": None,
        "analysis_results": "not-a-list",
        "generated_files": None,
    }
    state = node(garbage)
    assert state["report_status"] in ("degraded", "failed")
    assert state["error_log"]


def test_thinking_logs_exist_for_agentic_narrative(node):
    state = node(fixtures.healthy_state())
    assert state["thinking_log"]
    assert any("insight:" in line for line in state["thinking_log"])
