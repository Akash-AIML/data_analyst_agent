"""LangGraph node: validate -> insights -> recommendations -> report.

``insight_node(state) -> AgentState`` never raises. If the upstream pipeline
failed (empty ``analysis_results`` or ``status == "failed"``) it emits a
"degraded" report from the error/execution logs instead of crashing.

For tests, bind a stub LLM with ``build_insight_node(llm)`` so the node is
fully deterministic without an API key.
"""

from __future__ import annotations

import traceback
from typing import Any, Callable, Dict, List

from agents.insight import prompts
from agents.insight import report_generator
from agents.insight.validation import extract_evidence, validate_results

DEFAULT_OUTPUT_DIR = "output/reports"


def _thinking(state: Dict[str, Any], message: str) -> None:
    """Log the node's reasoning for the agentic-narrative requirement."""
    state["thinking_log"] = (state.get("thinking_log") or []) + [f"insight: {message}"]


def _log_error(state: Dict[str, Any], message: str) -> None:
    state["error_log"] = (state.get("error_log") or []) + [message]


def build_insight_node(
    llm: Any = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Create an ``insight_node`` bound to a concrete chat model."""

    def insight_node(state: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal llm
        if llm is None:
            llm = prompts.get_chat_model()

        state = dict(state)
        state.setdefault("error_log", [])
        state.setdefault("thinking_log", [])
        state.setdefault("report_status", "ok")

        profile = dict(state.get("profile") or {})
        # Normalize: profile["columns"] may be an int (total count) not a dict of column metadata.
        # validate_results expects either a dict or we strip it so it doesn't crash.
        if not isinstance(profile.get("columns"), dict):
            profile["_columns_count"] = profile.get("columns", 0)
            profile["columns"] = {}
        results = state.get("analysis_results") or []
        pipeline_ok = bool(results)



        # 1) Deterministic validation -------------------------------------------------
        _thinking(state, "running deterministic validation")
        try:
            validation = validate_results(profile, results)
            state["validation_report"] = validation
        except Exception:  # noqa: BLE001
            _log_error(state, f"validation crashed: {traceback.format_exc(limit=1)}")
            validation = {
                "status": "failed",
                "checks": [],
                "warnings": [],
                "errors": [f"validation crashed: {traceback.format_exc(limit=1)}"],
            }
            state["validation_report"] = validation

        if not pipeline_ok:
            state["report_status"] = "degraded"
            _thinking(state, "upstream failed or empty - emitting degraded report")
            return _write_report(state, output_dir)

        if validation.get("errors"):
            _log_error(
                state,
                f"validation reported {len(validation['errors'])} error(s); proceeding with valid evidence",
            )
            state["report_status"] = "degraded"
            _thinking(state, "validation reported errors - proceeding with valid evidence")


        # 2) Evidence extraction (only verified numbers reach the LLM) -----------------
        evidence = extract_evidence(profile, results, validation)
        if not evidence:
            state["report_status"] = "degraded"
            _thinking(state, "no valid evidence extracted - degrading")
            return _write_report(state, output_dir)

        # 3) Insights + code-level verification -----------------------------------------
        _thinking(state, f"generating insights from {len(evidence)} evidence entries")
        insights = _generate_insights(llm, evidence, state)

        # 4) Recommendations --------------------------------------------------------------
        _thinking(state, "generating recommendations")
        state["recommendations"] = _generate_recommendations(llm, insights, state)

        # 5) Self-consistency ------------------------------------------------------------
        _thinking(state, "running self-consistency audit")
        state["contradictions"] = _generate_consistency(llm, insights, state)

        # 6) Report ----------------------------------------------------------------------
        return _write_report(state, output_dir)

    return insight_node


def _generate_insights(llm: Any, evidence: List[Dict[str, Any]],
                       state: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        raw = prompts.generate_insights(llm, evidence)
    except Exception as exc:  # noqa: BLE001
        _log_error(state, f"insight generation failed: {exc}")
        return []

    verified = prompts.verify_insights(raw, evidence)
    deduped = prompts.dedupe_by_metric(verified)
    dropped = len(raw) - len(deduped)
    if dropped:
        _log_error(
            state,
            f"dropped {dropped} unverifiable/duplicate insight(s)",
        )
        if state.get("report_status") == "ok":
            state["report_status"] = "degraded"
    if len(deduped) < 5:
        _log_error(
            state,
            f"only {len(deduped)} verified insight(s); target is at least 5",
        )
        if state.get("report_status") == "ok":
            state["report_status"] = "degraded"
    state["insights"] = [ins.model_dump() for ins in deduped]
    return state["insights"]


def _generate_recommendations(llm: Any, insights: List[Dict[str, Any]],
                              state: Dict[str, Any]) -> List[str]:
    if not insights:
        _thinking(state, "no insights - skipping recommendations")
        return []
    try:
        recs = prompts.generate_recommendations(llm, insights)
    except Exception as exc:  # noqa: BLE001
        _log_error(state, f"recommendation generation failed: {exc}")
        return []
    out: List[str] = []
    for r in recs:
        label = f"{r.title}: {r.body}"
        if r.insight_id in {i.get("id") for i in insights}:
            label += f" (from insight #{r.insight_id})"
        out.append(label)
    return out


def _generate_consistency(llm: Any, insights: List[Dict[str, Any]],
                          state: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not insights:
        return []
    try:
        contradictions = prompts.check_consistency(llm, insights)
    except Exception as exc:  # noqa: BLE001
        _log_error(state, f"consistency check failed: {exc}")
        return []
    return [c.model_dump() for c in contradictions]


def _write_report(state: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    _thinking(state, "compiling HTML + PDF report")
    try:
        return report_generator.write_report(state, output_dir)
    except Exception as exc:  # noqa: BLE001
        _log_error(state, f"report compilation failed: {exc}")
        state["report_status"] = "failed"
        return state


# Default node for the real pipeline (needs OPENAI_API_KEY at call time).
def insight_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Default entry point; builds a real OpenAI-backed node on first use."""
    return build_insight_node(prompts.get_chat_model())(state)
