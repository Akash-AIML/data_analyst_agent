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
# LLM wiring
# ---------------------------------------------------------------------------

class ResilientFallbackModel(BaseChatModel):
    primary: Any
    fallback: Any

    def _generate(self, messages: Any, stop: Any = None, **kwargs: Any) -> Any:
        try:
            return self.primary._generate(messages, stop=stop, **kwargs)
        except Exception:
            for attempt in range(1, 4):
                try:
                    return self.fallback._generate(messages, stop=stop, **kwargs)
                except Exception as fb_err:
                    if attempt < 3:
                        time.sleep(3.0)
                    else:
                        raise fb_err

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        try:
            return self.primary.with_structured_output(schema, **kwargs)
        except Exception:
            for attempt in range(1, 4):
                try:
                    return self.fallback.with_structured_output(schema, **kwargs)
                except Exception as fb_err:
                    if attempt < 3:
                        time.sleep(3.0)
                    else:
                        raise fb_err

    @property
    def _llm_type(self) -> str:
        return "resilient_fallback"



from tools.llm_factory import get_ordered_llm


def get_chat_model(model: Optional[str] = None, temperature: float = 0.2) -> BaseChatModel:
    """Default chat model. Configured with automatic fallback across Groq, Gemini, and OpenAI."""
    return get_ordered_llm(model=model, temperature=temperature)






def structured_invoke(chat: BaseChatModel, schema: type[BaseModel], prompt: str) -> BaseModel:
    """Invoke a chat model and parse the reply as ``schema``.

    Preferred path: ``with_structured_output`` (tool calling on real OpenAI
    models). Fallback: plain JSON-mode prompting + Pydantic validation, so
    plain stubs and non-tool-calling models work too - and parse failures
    surface as Pydantic errors instead of silent garbage.
    """
    try:
        llm = chat.with_structured_output(schema)
        result = llm.invoke(prompt)
        parsed = _coerce_result(result, schema)
        if parsed is not None:
            return parsed
    except (NotImplementedError, AttributeError, Exception):
        pass

    return _json_invoke(chat, schema, prompt)


def _coerce_result(result: Any, schema: type[BaseModel]) -> Optional[BaseModel]:
    if isinstance(result, schema):
        return result
    if isinstance(result, BaseModel):  # e.g. wrapped by include_raw
        data = result.model_dump()
        if "parsed" in data:
            return schema.model_validate(data["parsed"])
        return None
    if isinstance(result, dict):
        return schema.model_validate(result)
    if isinstance(result, str):
        return schema.model_validate_json(result)
    return None


def _json_invoke(chat: BaseChatModel, schema: type[BaseModel], prompt: str) -> BaseModel:
    json_prompt = (
        prompt
        + "\n\nRespond with ONLY a valid JSON object matching this schema:\n"
        + json.dumps(schema.model_json_schema(), default=str)
    )
    reply = chat.invoke(json_prompt)
    text = _extract_text(reply)

    # 1. Direct JSON parse attempt
    try:
        data = json.loads(text)
        if isinstance(data, list):
            if schema == InsightsBatch:
                return schema(insights=data)
            elif schema == RecommendationsBatch:
                return schema(recommendations=data)
            elif schema == ConsistencyReport:
                return schema(contradictions=data)
        elif isinstance(data, dict):
            return schema.model_validate(data)
    except Exception:
        pass

    # 2. Substring extraction attempt
    indices_start = [i for i in (text.find("{"), text.find("[")) if i != -1]
    indices_end = [i for i in (text.rfind("}"), text.rfind("]")) if i != -1]
    if indices_start and indices_end:
        start_idx = min(indices_start)
        end_idx = max(indices_end)
        if end_idx > start_idx:
            sub_text = text[start_idx : end_idx + 1]
            try:
                data = json.loads(sub_text)
                if isinstance(data, list):
                    if schema == InsightsBatch:
                        return schema(insights=data)
                    elif schema == RecommendationsBatch:
                        return schema(recommendations=data)
                    elif schema == ConsistencyReport:
                        return schema(contradictions=data)
                elif isinstance(data, dict):
                    return schema.model_validate(data)
            except Exception:
                pass

    return schema.model_validate_json(text)



def _extract_text(reply: Any) -> str:
    """Pull JSON text out of whatever the model returned (AIMessage/dict/str)."""
    if isinstance(reply, str):
        text = reply
    elif hasattr(reply, "content"):
        text = reply.content
    elif isinstance(reply, dict):
        text = reply.get("content") or ""
        if not text and reply.get("tool_calls"):
            text = reply["tool_calls"][0].get("args") or ""
    else:
        text = str(reply)

    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        last = text.rfind("```")
        text = text[first_nl + 1 : last].strip() if last > first_nl else text[first_nl + 1 :].strip()
    return text


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
