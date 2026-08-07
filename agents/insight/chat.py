"""Report-grounded chatbot core (UI-free).

Turns a finished ''AgentState`` (the same content the HTML/PDF report
carries) into a compact grounded context, and answers user questions strictly
from it.

Anti-hallucination (matches the rest of Member 3's module):
  * The model sees ONLY the report context. Questions outside it get an
    honest "not in report" reply - enforced by the system prompt and by the
    fact that no other data is provided.
  * Answers cite numbers verbatim from the report.

``answer`` is model-agnostic: pass any chat model (LangChain ``BaseChatModel``)
so tests use the fake and the real app uses OpenAI.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel

# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful data-analyst assistant. You answer questions \
ONLY from the REPORT CONTEXT below. Rules:
- If the answer is not in the REPORT CONTEXT, say "Not in this report" and briefly \
explain what the report does contain.
- Cite numbers exactly as they appear in the context; never invent numbers.
- Be concise (3 sentences or fewer unless asked for detail)."""


def _fmt(res: Any, indent: int = 1) -> str:
    pad = " " * indent
    if isinstance(res, dict):
        return "\n".join(
            f"{pad}{k}: {_fmt(v, indent + 2)}" if not isinstance(v, (dict, list))
            else f"{pad}{k}:\n{_fmt(v, indent + 2)}"
            for k, v in res.items()
        )
    if isinstance(res, list):
        return "\n".join(f"{pad}- {_fmt(i, indent + 2)}" for i in res)
    if isinstance(res, float) and str(res) == "nan":
        return "NaN"
    return str(res)


def build_context(state: Dict[str, Any]) -> str:
    """Serialize the report-relevant parts of an AgentState to plain text.

    This is the SINGLE source of truth the chat is grounded on, and mirrors
    the sections rendered in the HTML report.
    """
    profile = state.get("profile") or {}
    validation = state.get("validation_report") or {}
    errors = validation.get("errors") or []
    warnings = validation.get("warnings") or []

    cols_val = profile.get("columns")
    if isinstance(cols_val, (dict, list, tuple, set)):
        num_cols = len(cols_val)
    elif isinstance(cols_val, (int, float)):
        num_cols = float(cols_val)
    else:
        num_cols = 0

    sections = [
        ("DATASET", {
            "csv_path": state.get("csv_path"),
            "rows": profile.get("rows"),
            "columns": profile.get("columns_count") or num_cols,
            "numeric_columns": profile.get("numeric_columns"),
            "categorical_columns": profile.get("categorical_columns"),
            "datetime_columns": profile.get("datetime_columns"),
        }),
        ("PROFILE_COLUMNS", cols_val if isinstance(cols_val, dict) else {}),

        ("VALIDATION", {
            "status": validation.get("status"),
            "failed_checks": [
                c for c in validation.get("checks", []) if not c.get("ok")
            ],
            "warnings": warnings,
            "errors": errors,
        }),
        ("INSIGHTS", state.get("insights") or []),
        ("RECOMMENDATIONS", [{"text": r} for r in (state.get("recommendations") or [])]),
        ("CONTRADICTIONS", state.get("contradictions") or []),
        ("EXECUTION_LOG", state.get("execution_log") or []),
        ("REFLECTION_NOTES", state.get("reflection_notes") or []),
        ("ERROR_LOG", state.get("error_log") or []),
        ("REPORT", {
            "status": state.get("report_status"),
            "pipeline_status": state.get("status"),
            "report_path": state.get("report_path"),
            "pdf_path": state.get("pdf_path"),
            "charts": [os.path.basename(p) for p in (state.get("generated_files") or [])],
        }),
    ]

    lines: List[str] = []
    for name, data in sections:
        lines.append(f"\n=== {name} ===")
        lines.append(_fmt(data) if data not in (None, [], {}) else "(none)")
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_report_state(state: Dict[str, Any], path: str) -> None:
    """Persist a state to JSON (NaN-safe) so the app can load it later."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, default=str)


def load_report_state(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Answer
# ---------------------------------------------------------------------------

def answer(
    model: BaseChatModel,
    user_message: str,
    context: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Ground ``user_message`` on ``context`` with optional prior turns."""
    messages: List[Any] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"REPORT CONTEXT:\n{context}"},
    ]
    for turn in history or []:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})

    result = model.invoke(messages)
    return _extract(result)


def _extract(result: Any) -> str:
    if isinstance(result, str):
        return result
    if hasattr(result, "content"):
        return result.content
    if isinstance(result, dict):
        return str(result.get("content") or result)
    return str(result)


# ---------------------------------------------------------------------------
# Convenience: build context directly from a JSON report file path
# ---------------------------------------------------------------------------

def context_from_file(path: str) -> str:
    return build_context(load_report_state(path))