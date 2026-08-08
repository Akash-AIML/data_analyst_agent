"""LLM prompts and Pydantic output schemas for insight generation.

Anti-hallucination design (Member 3 devil's-advocate review):
  * Every ``Insight`` must cite a number that appears verbatim in the
    supplied ``JSON_BLOCK`` of *verified* evidence (produced by
    ``validation.extract_evidence``).
  * Structured output is enforced with Pydantic via
    ``with_structured_output`` - no free-form JSON parsing.
  * A separate cheap self-consistency call detects contradictions between
    insights instead of shipping them silently.

In tests, ``get_chat_model`` is swapped for a stub, so nothing here requires
an API key.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from llm import structured_invoke as _structured_invoke


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------

class Insight(BaseModel):
    """One evidence-bound business insight."""

    id: int = Field(description="sequential id, starting at 1")
    title: str = Field(description="short title, <= 10 words")
    body: str = Field(description="1-3 sentences stating the finding")
    evidence: str = Field(
        description="the exact number(s) cited, copied verbatim from the JSON_BLOCK"
    )
    metric: str = Field(description="the metric this insight is about")
    value: float = Field(description="the numeric value this insight is based on")
    confidence: float = Field(ge=0.0, le=1.0, description="0..1, how certain")


class InsightsBatch(BaseModel):
    """Structured container so the model returns exactly a list of insights.

    No min_length here: enforcing count at the schema level makes a slightly
    short-but-valid answer fail entirely. The node enforces the >=5 target
    leniently (warn + degrade) instead of throwing away good work.
    """

    insights: List[Insight] = Field(description="business insights")


class Recommendation(BaseModel):
    """One actionable business recommendation."""

    title: str = Field(description="short action-oriented title")
    body: str = Field(description="what to do and why, <= 3 sentences")
    insight_id: int = Field(description="id of the insight this recommendation derives from")


class RecommendationsBatch(BaseModel):
    recommendations: List[Recommendation] = Field(description="actionable recommendation")


class Contradiction(BaseModel):
    insight_a_id: int
    insight_b_id: int
    reason: str = Field(description="why the two insights contradict or overlap")


class ConsistencyReport(BaseModel):
    contradictions: List[Contradiction] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt text
# ---------------------------------------------------------------------------

SYSTEM_INSIGHT = """You are a senior data analyst. You translate statistics into \
concise, business-relevant insights. You NEVER invent numbers: every insight must \
cite a number that appears VERBATIM in the supplied JSON_BLOCK of verified evidence. \
If a claim needs a number that is not in the block, omit the claim. \
Only descriptive/exploratory findings are allowed - no modelling, no forecasting."""

SYSTEM_RECOMMENDATION = """You are a business consultant. Given a set of evidence-bound \
insights, derive 3-5 actionable recommendations. Each recommendation must trace back \
to at least one insight id and must not introduce new numbers."""

SYSTEM_CONSISTENCY = """You are an auditor. Review the given insights for \
contradictions or overlapping claims (e.g. one says 'sales increasing' while another \
says 'sales declining' from the same metric). Return a list of contradiction pairs. \
Return an empty list if the insights are consistent."""


def _json_block(evidence: List[Dict[str, Any]]) -> str:
    return json.dumps(evidence, default=str, indent=2)


def build_insight_prompt(
    evidence: List[Dict[str, Any]],
    profile_summary: Optional[str] = None,
) -> str:
    parts = [
        "Produce at least 5 insights about the dataset.\n",
        f"VERIFIED EVIDENCE JSON_BLOCK (only cite numbers from here):\n{_json_block(evidence)}\n",
    ]
    if profile_summary:
        parts.append(f"Profile summary for context (do NOT cite these as evidence):\n{profile_summary}\n")
    parts.append(
        "Rules:\n"
        "- every insight's 'evidence' and 'value' must come verbatim from the JSON_BLOCK\n"
        "- no two insights may reuse the same 'metric'\n"
        "- cite exact numbers, not approximations\n"
        "- keep body <= 3 sentences"
    )
    return "\n".join(parts)


def build_recommendation_prompt(insights: List[Dict[str, Any]]) -> str:
    return (
        "Derive 3-5 actionable business recommendations from these insights:\n"
        + json.dumps(insights, default=str, indent=2)
        + "\nEach recommendation must set 'insight_id' to an existing insight id."
    )


def build_consistency_prompt(insights: List[Dict[str, Any]]) -> str:
    return (
        "Audit these insights for contradictions and overlapping claims:\n"
        + json.dumps(insights, default=str, indent=2)
    )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# LLM wiring (delegated to the central llm module)
# ---------------------------------------------------------------------------

def get_chat_model(model: Optional[str] = None, temperature: float = 0.2) -> BaseChatModel:
    """Default chat model. Configured with automatic fallback across OpenAI/Groq."""
    from llm import build_chat_model
    return build_chat_model(task="INSIGHT", temperature=temperature)


def structured_invoke(chat: BaseChatModel, schema: type[BaseModel], prompt: str) -> BaseModel:
    """Invoke a chat model and parse the reply as ``schema``.

    Delegates to ``llm.structured_invoke`` which tries tool calling first and
    falls back to a JSON-mode prompt so plain stubs (FakeChatLLM) and
    non-tool-calling models work too. Parse failures surface as Pydantic errors.
    """
    return _central_structured_invoke(
        task="INSIGHT",
        messages=[{"role": "system", "content": prompt}],
        schema=schema,
        temperature=0.2,
        chat=chat,
    )


# alias to keep signature/semantics readable
_central_structured_invoke = _structured_invoke


def generate_insights(
    chat: BaseChatModel,
    evidence: List[Dict[str, Any]],
    profile_summary: Optional[str] = None,
) -> List[Insight]:
    batch = structured_invoke(chat, InsightsBatch, build_insight_prompt(evidence, profile_summary))
    return list(batch.insights)


def generate_recommendations(
    chat: BaseChatModel,
    insights: List[Dict[str, Any]],
) -> List[Recommendation]:
    batch = structured_invoke(chat, RecommendationsBatch, build_recommendation_prompt(insights))
    return list(batch.recommendations)


def check_consistency(
    chat: BaseChatModel,
    insights: List[Dict[str, Any]],
) -> List[Contradiction]:
    batch_res = structured_invoke(chat, ConsistencyReport, build_consistency_prompt(insights))
    return list(batch_res.contradictions)


# ---------------------------------------------------------------------------
# Post-generation enforcement (code-level, not just prompt-level)
# ---------------------------------------------------------------------------

def verify_insights(
    insights: List[Insight],
    evidence: List[Dict[str, Any]],
) -> List[Insight]:
    """Drop/flag insights whose ``value`` isn't backed by the evidence block.

    Returns only verifiable insights. This is the fact-check layer that makes
    hallucination structurally hard rather than prompt-dependent.
    """
    if not insights:
        return []
    allowed = {
        float(v)
        for entry in evidence
        for v in entry.get("stats", {}).values()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }
    if not allowed:
        return []

    verified: List[Insight] = []
    for ins in insights:
        try:
            if float(ins.value) in allowed:
                verified.append(ins)
            elif ins.evidence and any(str(ins.evidence).strip() in str(e) for e in evidence):
                verified.append(ins)
        except (TypeError, ValueError):
            continue
    return verified





def dedupe_by_metric(insights: List[Insight]) -> List[Insight]:
    seen: set = set()
    out: List[Insight] = []
    for ins in insights:
        key = ins.metric.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(ins)
    return out
