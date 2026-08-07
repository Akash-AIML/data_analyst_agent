"""Deterministic stub chat model for testing insight generation.

Returns canned structured JSON depending on which prompt it receives, so
``insight_node`` behaves identically on every run - no API key needed.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

INSIGHTS_JSON = {
    "insights": [
        {
            "id": 1,
            "title": "Four regions active",
            "body": "Four distinct regions are shipping product.",
            "evidence": "4",
            "metric": "unique_regions",
            "value": 4.0,
            "confidence": 0.9,
        },
        {
            "id": 2,
            "title": "Sales correlate with units",
            "body": "Sales strongly track units shipped.",
            "evidence": "0.92",
            "metric": "correlation",
            "value": 0.92,
            "confidence": 0.85,
        },
        {
            "id": 3,
            "title": "Average sale value",
            "body": "Average sales per transaction is solid.",
            "evidence": "1308.0",
            "metric": "mean_sales",
            "value": 1308.0,
            "confidence": 0.95,
        },
        {
            "id": 4,
            "title": "No missing units data",
            "body": "The units column is complete.",
            "evidence": "0.0",
            "metric": "missing_units",
            "value": 0.0,
            "confidence": 0.99,
        },
        {
            "id": 5,
            "title": "Top sale reaches 2175",
            "body": "The largest transaction tops out at 2175.",
            "evidence": "2175.0",
            "metric": "max_sales",
            "value": 2175.0,
            "confidence": 0.7,
        },
    ]
}

RECOMMENDATIONS_JSON = {
    "recommendations": [
        {
            "title": "Push WidgetA in North",
            "body": "North sells most units, so increase WidgetA stock there.",
            "insight_id": 1,
        },
        {
            "title": "Track unit sales",
            "body": "Since sales track units, focus on volume drivers.",
            "insight_id": 2,
        },
        {
            "title": "Review East pricing",
            "body": "Investigate why East underperforms despite similar prices.",
            "insight_id": 5,
        },
    ]
}

CONSISTENCY_JSON = {"contradictions": []}


class FakeChatModel(BaseChatModel):
    """Returns canned JSON text per prompt; supports structured invoke via the
    JSON fallback path in ``prompts.structured_invoke``."""

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        prompt_text = "\n".join(
            getattr(m, "content", "") or "" for m in messages
        )
        if "Derive 3-5 actionable" in prompt_text:
            payload = RECOMMENDATIONS_JSON
        elif "Audit these insights" in prompt_text:
            payload = CONSISTENCY_JSON
        else:
            payload = INSIGHTS_JSON
        msg = AIMessage(content=json.dumps(payload))
        return ChatResult(generations=[ChatGeneration(message=msg)])
