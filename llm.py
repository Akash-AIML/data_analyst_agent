"""Central LLM factory, failover, structured invocation, and cost logging.

Single source of truth for model wiring across all agents (profiler,
analysis planner/executor/reflector, insight, chat).

Design:
  * ``get_chat_model`` -> a provider-backed ``BaseChatModel``. OpenAI-compatible
    base URL is the primary provider (via ``OPENAI_API_KEY``/``MODEL``); Groq is
    the automatic failover on 4xx/5xx; plain Groq or Gemini as stand-alone
    providers when no OpenAI key is present.
  * ``structured_invoke`` runs one chat call and parses the reply into a
    Pydantic schema: tries tool calling (``with_structured_output``) first, then
    a JSON-mode prompt + validation so plain stubs and non-tool-calling models
    still work, and parse failures surface as Pydantic errors, never as
    silently-garbage strings.
  * Every helper appends a ``{call}`` record to ``state["llm_calls"]`` when a
    state dict is supplied: latency, provider/model, tokens, and an estimated
    price (table below). This makes token/cost visible per pipeline run.
  * Optional in-memory response cache (``LLM_CACHE_ENABLED=1``) memoizes exact
    prompt+task replies for cheap deterministic steps (planner / reflector).

The old per-agent ``ResilientFallbackModel`` / ``_build_*_llm`` copies are
superseded by this module; import from here instead of re-declaring overrides.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, Optional, Sequence, Union

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

load_dotenv(override=True)


# ---------------------------------------------------------------------------
# LangSmith tracing
# ---------------------------------------------------------------------------
# LangChain picks up LANGSMITH_TRACING_V2=true (preferred) or LANGSMITH_TRACING=true,
# plus LANGSMITH_API_KEY and LANGSMITH_PROJECT from env automatically. We just
# normalize the legacy var name and expose a ``tracing_enabled`` flag so callers
# (CLI, FastAPI) can short-circuit when no key is configured.

LANGSMITH_TRACING_ENABLED = (
    os.getenv("LANGSMITH_TRACING_V2", "").lower() in ("1", "true", "yes")
    or os.getenv("LANGSMITH_TRACING", "").lower() in ("1", "true", "yes")
) and bool(os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY"))

LANGSMITH_PROJECT = (
    os.getenv("LANGSMITH_PROJECT")
    or os.getenv("LANGCHAIN_PROJECT")
    or "ai-data-analyst"
)


def _tracing_metadata(state: Optional[Dict[str, Any]] = None,
                      extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the metadata dict we attach to every LangSmith run.

    Includes run-level context (csv_path, task) so traces are filterable in
    the LangSmith UI. Never includes API keys or PII from the dataframe.
    """
    md: Dict[str, Any] = {"langsmith_project": LANGSMITH_PROJECT}
    if state is not None:
        csv_path = state.get("csv_path")
        if csv_path:
            md["csv_path"] = os.path.basename(str(csv_path))
        md["status"] = state.get("status", "unknown")
    if extra:
        for k, v in extra.items():
            if v is not None:
                md[k] = v
    return md


# Rate-limit pacing + budget guard (make sure it honors both our test env and
# live envs).  NVIDIA NIM is cheap and high-RPM sequential, but other providers
# (e.g. a LiteLLM proxy at 10k TPM) throttle on bursts, so we pace conservatively.
_MIN_INTERVAL_S = float(os.getenv("LLM_MIN_INTERVAL_S", "1.0"))
# Budget values are read lazily via ``_budget_limit()`` etc. so tests can
# monkeypatch env vars without re-importing the module.
_BUDGET_WARN_RATIO = float(os.getenv("LLM_BUDGET_WARN_RATIO", "0.8"))

_THREAD_LOCK = None
try:
    import threading
    _THREAD_LOCK = threading.Lock()
except Exception:  # noqa: BLE001
    pass

_last_call_ts: float = 0.0
_run_cost_us = 0.0
_budget_warned: bool = False  # only log the warn once per run


def _budget_limit() -> float:
    """Read LLM_BUDGET_US at call time (so env reloads are honored)."""
    return float(os.getenv("LLM_BUDGET_US", "1.0") or 0.0)


def budget_total() -> float:
    """Cumulative cost accrued so far in this process."""
    return _run_cost_us


def budget_reset() -> None:
    """Reset the per-run accumulator (used by tests + between pipeline runs)."""
    global _run_cost_us, _last_call_ts, _budget_warned
    _run_cost_us = 0.0
    _last_call_ts = 0.0
    _budget_warned = False


def _pace() -> None:
    """Enforce a minimum interval + cumulative budget across LLM calls.

    ``LLM_MIN_INTERVAL_S`` spaces sequential calls (avoids TPM/RPM 429s on
    bursty proxies). ``LLM_BUDGET_US`` (0 = disabled) stops new LLM work once a
    run's estimated cost passes the cap; callers degrade deterministically.
    Logs a soft warning at ``LLM_BUDGET_WARN_RATIO`` (default 80%) of the cap
    so an operator sees the spend before the hard stop kicks in.
    """
    global _last_call_ts, _run_cost_us, _budget_warned
    limit = _budget_limit()
    if limit:
        if _run_cost_us >= limit:
            raise RuntimeError(
                f"llm budget exhausted (est ${_run_cost_us:.4f} >= "
                f"${limit}); deterministic fallbacks engaged"
            )
        if not _budget_warned and _run_cost_us >= limit * _BUDGET_WARN_RATIO:
            _budget_warned = True
            logger.warning(
                "llm budget at %.0f%% (est $%.4f of $%.4f) - further "
                "calls may be cut off",
                _BUDGET_WARN_RATIO * 100, _run_cost_us, limit,
            )
    if _THREAD_LOCK is not None and _THREAD_LOCK.acquire(False):
        try:
            import time as _t
            wait = _MIN_INTERVAL_S - (_t.monotonic() - _last_call_ts)
            if wait > 0:
                _t.sleep(wait)
            _last_call_ts = _t.monotonic()
        finally:
            _THREAD_LOCK.release()


def _charge(usage: Dict[str, Any]) -> None:
    global _run_cost_us
    cost = usage.get("cost_usd") or 0.0
    _run_cost_us += float(cost)


def _record_budget_summary(state: Optional[Dict[str, Any]]) -> None:
    """Stash the current cumulative spend on state so callers can display it.

    Idempotent: overwrites any previous summary with the latest totals so the
    final report always reflects the actual run cost (not a stale snapshot).
    """
    if state is None:
        return
    summary = {
        "task": "__budget__",
        "model": "aggregator",
        "ok": True,
        "cost_usd_total": round(_run_cost_us, 6),
        "calls": sum(
            1 for c in (state.get("llm_calls") or []) if c.get("task") != "__budget__"
        ),
        "budget_limit_us": _budget_limit(),
        "budget_exhausted": bool(
            _budget_limit() and _run_cost_us >= _budget_limit()
        ),
    }
    calls = state.get("llm_calls")
    if isinstance(calls, list):
        # replace the last budget entry (if any) without growing the list
        for i in range(len(calls) - 1, -1, -1):
            if calls[i].get("task") == "__budget__":
                calls[i] = summary
                return
        calls.append(summary)


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model / pricing registry
# ---------------------------------------------------------------------------

_MODEL_ALIASES: Dict[str, str] = {
    # task/model name -> model string used in prompts / env lookups
    "gpt-4.1-nano": "gpt-4.1-nano",
    "gpt-4.1-mini": "gpt-4.1-mini",
    "llama-3.3-70b-versatile": "llama-3.3-70b-versatile",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.0-flash": "gemini-2.0-flash",
}

# USD per 1M tokens. Fallbacks for unknown models: pessimistic estimate.
_PRICE_PER_MTOK: Dict[str, Dict[str, float]] = {
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},  # via Groq
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "nvidia/nemotron-mini-4b-instruct": {"input": 0.10, "output": 0.10},  # NVIDIA NIM
    "nvidia/nemotron-nano-2b-instruct": {"input": 0.10, "output": 0.10},  # NVIDIA NIM
    "default": {"input": 0.80, "output": 2.40},
}


def _price_for(model: str) -> Dict[str, float]:
    key = _MODEL_ALIASES.get(model, model)
    return _PRICE_PER_MTOK.get(key, _PRICE_PER_MTOK["default"])


def _task_model(task: str) -> Optional[str]:
    """Per-task model override from env, e.g. ``PLANNER_MODEL``."""
    raw = os.getenv(f"{task}_MODEL", "").strip()
    return raw or os.getenv("MODEL", "gpt-4.1-nano")


def _resolve_openai_base_url() -> str:
    """Resolve the OpenAI-compatible ``base_url`` for the primary provider.

    Supports several conventions (OpenAI SDK, NVIDIA NIM, LiteLLM proxies):
      * ``OPENAI_BASE_URL``   - may be the API root (``.../v1``) OR the full
        ``.../v1/chat/completions`` endpoint (a common NVIDIA NIM oversight).
      * ``OPENAI_API_BASE`` / ``OPENAI_BASE_URL`` older alias accepted too.

    If the configured value already ends with ``/chat/completions`` we strip it
    so LangChain does not append it a second time (which yields 404 on NIM).
    """
    base = (
        os.getenv("OPENAI_BASE_URL", "").strip()
        or os.getenv("OPENAI_API_BASE", "").strip()
        or "https://api.openai.com/v1"
    )
    base = base.rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    return base

# ---------------------------------------------------------------------------
# Fallback chat model
# ---------------------------------------------------------------------------

def _is_rate_limit(exc: Exception) -> bool:
    """Best-effort classification of a rate-limit (429) error."""
    msg = str(exc).lower()
    if "429" in msg or "rate limit" in msg or "too many requests" in msg:
        return True
    code = getattr(exc, "status_code", None)
    return code == 429


class ResilientFallbackModel(BaseChatModel):
    """Calls ``primary`` first; transparently fails over to ``fallback``.

    Rate-limit (429/TPM) errors are transient, so the primary is retried a few
    times with bounded exponential backoff before crossing over - this avoids
    burning the fallback (often the shared daily-cap provider) on a momentary
    throttle. Non-429 errors fail over immediately with bounded backoff on the
    fallback itself.
    """

    primary: Any
    fallback: Any
    attempt_limit: int = 4
    primary_rate_retries: int = 3

    @property
    def _llm_type(self) -> str:
        return "resilient_fallback"

    def _generate(self, messages: Any, stop: Any = None, **kwargs: Any) -> Any:
        first_fail: Exception | None = None
        for attempt in range(self.primary_rate_retries):
            try:
                return self.primary._generate(messages, stop=stop, **kwargs)
            except Exception as exc:  # noqa: BLE001
                first_fail = first_fail or exc
                if not _is_rate_limit(exc):
                    break
                if attempt < self.primary_rate_retries - 1:
                    time.sleep(min(2 ** (attempt + 1), 20))

        # primary exhausted its retries -> try fallback with backoff
        for attempt in range(1, self.attempt_limit + 1):
            try:
                return self.fallback._generate(messages, stop=stop, **kwargs)
            except Exception as fb_err:  # noqa: BLE001
                if attempt >= self.attempt_limit:
                    raise fb_err from (first_fail or fb_err)
                time.sleep(min(2 ** attempt, 12))

    @property
    def model(self) -> str:  # informational alias for logging
        return self.primary.model if getattr(self.primary, "model", None) else "resilient_fallback"

    @property
    def provider(self) -> str:
        return "resilient (openai/groq)"


def build_chat_model(task: str = "DEFAULT", temperature: float = 0.2) -> BaseChatModel:
    """Build the agent chat model for ``task`` with automatic failover.

    Returns either a plain model (single provider) or a
    ``ResilientFallbackModel`` when both primary and fallback are present.
    """
    # --- primary: OpenAI-compatible endpoint ---
    openai_key = os.getenv("OPENAI_API_KEY", "")

    groq_key = os.getenv("GROQ_API_KEY", "")
    groq_llm = None
    if groq_key:
        try:
            from langchain_groq import ChatGroq
            groq_llm = ChatGroq(
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                groq_api_key=groq_key,
                temperature=temperature,
                max_retries=0,
            )
        except Exception:  # noqa: BLE001
            groq_llm = None

    if openai_key:
        from langchain_openai import ChatOpenAI
        base_url = _resolve_openai_base_url()
        primary = ChatOpenAI(
            model=os.getenv("MODEL", "gpt-4.1-nano"),
            api_key=openai_key,
            base_url=base_url,
            temperature=temperature,
            max_retries=0,  # fail fast -> fallback handles retries
        )
        if groq_llm:
            return ResilientFallbackModel(primary=primary, fallback=groq_llm)
        return primary

    if groq_llm:
        return groq_llm

    if os.getenv("GEMINI_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            temperature=temperature,
        )

    raise EnvironmentError(
        "No LLM configured. Set at least one of OPENAI_API_KEY, GROQ_API_KEY or "
        "GEMINI_API_KEY in .env."
    )


# ---------------------------------------------------------------------------
# Structured invocation
# ---------------------------------------------------------------------------

def _messages_to_str(messages: Union[str, Sequence[Union[dict, BaseMessage]]]) -> str:
    if isinstance(messages, str):
        return messages
    parts = []
    for m in messages:
        if isinstance(m, BaseMessage):
            parts.append(m.content or "")
        elif isinstance(m, dict):
            parts.append(str(m.get("content", "")))
        else:
            parts.append(str(m))
    return "\n".join(parts)


def _extract_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return str(result.get("content") or result)
    if hasattr(result, "content"):
        txt = result.content
        if isinstance(txt, list):  # content blocks
            return "".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in txt
            )
        return str(txt)
    return str(result)


class _Cache:
    """Disk-backed LLM response cache with TTL + atomic writes.

    When ``LLM_CACHE_ENABLED=1`` the cache loads from
    ``config.LLM_CACHE_PATH`` (default ``output/llm_cache.json``) at startup
    and writes back atomically (write to ``.tmp``, then rename) after each
    ``set`` so a crash mid-write never leaves a half-written file.

    Entries older than ``LLM_CACHE_TTL_S`` seconds (default 7 days) are
    considered stale and re-fetched; entries are also evicted FIFO when the
    on-disk cache exceeds ``LLM_CACHE_CAP`` items (default 512) so a long-lived
    deployment doesn't grow the file unboundedly.

    Schema on disk::

        {
          "<sha256>": {"v": <value>, "ts": <unix_epoch_seconds>},
          ...
        }

    A legacy cache file (no ``ts`` field) is treated as fresh — keeps the
    upgrade path zero-effort.
    """

    def __init__(self, cap: int = 512, ttl_s: int = 7 * 24 * 3600) -> None:
        from config import LLM_CACHE_CAP
        self._cap = LLM_CACHE_CAP if cap is None else int(cap)
        self._ttl_s = int(os.getenv("LLM_CACHE_TTL_S", str(ttl_s)))
        # Path and enabled-flag are read lazily on every operation so tests
        # can monkeypatch env vars without rebuilding the singleton.
        self._data: Dict[str, Any] = {}
        self._load()

    @property
    def _path(self) -> str:
        from config import LLM_CACHE_PATH
        return os.getenv("LLM_CACHE_PATH", LLM_CACHE_PATH)

    def _is_enabled(self) -> bool:
        """Cache is opt-in via LLM_CACHE_ENABLED; checked lazily each call so
        tests can monkeypatch the env without reloading the module."""
        return os.getenv("LLM_CACHE_ENABLED", "").lower() in ("1", "true", "yes", "on")

    def _load(self) -> None:
        if not self._is_enabled():
            return
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self._data = data if isinstance(data, dict) else {}
                self._evict_stale()
        except Exception:  # noqa: BLE001  # corrupt cache is not fatal
            self._data = {}

    def _evict_stale(self) -> None:
        """Drop entries older than TTL and trim to cap."""
        if not self._data:
            return
        import time as _t
        now = _t.time()
        stale = []
        for k, v in list(self._data.items()):
            if isinstance(v, dict) and isinstance(v.get("ts"), (int, float)):
                if now - float(v["ts"]) > self._ttl_s:
                    stale.append(k)
        for k in stale:
            self._data.pop(k, None)
        # Cap by FIFO on the original key insertion order.
        if len(self._data) > self._cap:
            for oldest in list(self._data)[: len(self._data) - self._cap]:
                self._data.pop(oldest, None)

    def _flush(self) -> None:
        if not self._is_enabled():
            return
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            tmp_path = f"{self._path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, default=str)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, self._path)  # atomic on POSIX & Windows
        except Exception as exc:  # noqa: BLE001
            logger.debug("cache flush failed: %s", exc)

    def _key(self, task: str, prompt: str, model: str) -> str:
        digest = hashlib.sha256(f"{model}::{task}::{prompt}".encode("utf-8")).hexdigest()
        return digest

    def get(self, task: str, prompt: str, model: str) -> Optional[Any]:
        if not self._is_enabled():
            return None
        entry = self._data.get(self._key(task, prompt, model))
        if entry is None:
            return None
        if isinstance(entry, dict) and "v" in entry:
            return entry["v"]
        # legacy schema: bare value
        return entry

    def set(self, task: str, prompt: str, model: str, value: Any) -> None:
        if not self._is_enabled():
            return
        import time as _t
        key = self._key(task, prompt, model)
        self._data[key] = {"v": value, "ts": _t.time()}
        self._evict_stale()
        self._flush()

    def clear(self) -> None:
        """Drop everything in memory + on disk; primarily for tests."""
        self._data = {}
        try:
            if os.path.exists(self._path):
                os.remove(self._path)
        except OSError:
            pass


_CACHE = _Cache()


def _usage_stats(model: str, result: Any, latency_s: float) -> Dict[str, Any]:
    """Best-effort token + price accounting for a single call."""
    in_tok = out_tok = None
    meta = getattr(result, "usage_metadata", None) or {}
    if isinstance(meta, dict):
        in_tok = meta.get("input_tokens") or meta.get("prompt_tokens")
        out_tok = meta.get("output_tokens") or meta.get("completion_tokens")
    resp_meta = getattr(result, "response_metadata", {}) or {}
    if in_tok is None and isinstance(resp_meta, dict):
        usage = resp_meta.get("usage") or {}
        in_tok = usage.get("prompt_tokens")
        out_tok = usage.get("completion_tokens")

    price = _price_for(model)
    cost = None
    if in_tok is not None and out_tok is not None:
        cost = round(in_tok / 1e6 * price["input"] + out_tok / 1e6 * price["output"], 6)
    return {
        "model": model,
        "latency_s": round(latency_s, 3),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": cost,
    }


def _record(state: Optional[Dict[str, Any]], record: Dict[str, Any]) -> None:
    if state is None:
        return
    state.setdefault("llm_calls", [])
    if not isinstance(state.get("llm_calls"), list):
        state["llm_calls"] = []
    state["llm_calls"].append(record)


def _llm_model_name(chat: BaseChatModel) -> str:
    for attr in ("model",):
        if getattr(chat, attr, None):
            return str(getattr(chat, attr))
    return getattr(chat, "_llm_type", "unknown")


def structured_invoke(
    task: str,
    messages: Union[str, Sequence[Union[dict, BaseMessage]]],
    schema: type[BaseModel],
    temperature: float = 0.2,
    chat: Optional[BaseChatModel] = None,
    state: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[BaseModel]:
    """Invoke ``schema`` still passes through with fallbacks; parse structured output.

    Returns a validated Pydantic model or ``None`` on total failure.
    ``metadata`` is forwarded to LangSmith (csv_path, task, status).
    """
    model = chat or build_chat_model(task, temperature=temperature)
    prompt = _messages_to_str(messages)
    model_name = _llm_model_name(model)

    cached = _CACHE.get(task, prompt, model_name)
    if cached is not None:
        if state is not None:
            rec = {"task": task, "cached": True, "model": model_name}
            _record(state, {**rec, **cached})
        return cached

    run_metadata = _tracing_metadata(state, {"task": task, **(metadata or {})})
    _pace()
    t0 = time.monotonic()
    try:
        parsed = _structured_call(model, schema, messages, run_metadata)
    except Exception as exc:  # noqa: BLE001
        logger.warning("structured_invoke(%s) failed: %s", task, exc)
        _record(state, {
            "task": task, "model": model_name, "ok": False,
            "error": str(exc)[:300], "latency_s": round(time.monotonic() - t0, 3),
        })
        return None
    latency = time.monotonic() - t0

    if isinstance(parsed, dict) and "parsed" in parsed:
        parsed = parsed["parsed"]
    if not isinstance(parsed, schema):
        try:
            parsed = schema.model_validate(parsed)
        except Exception:  # noqa: BLE001
            _record(state, {
                "task": task, "model": model_name, "ok": False,
                "error": f"cannot validate as {schema.__name__}",
                "latency_s": round(latency, 3),
            })
            return None

    usage = _usage_stats(model_name, parsed, latency)
    raw = getattr(model, "_llm_last_raw_reply", None)
    if usage.get("input_tokens") is None and raw is not None:
        usage = _usage_stats(model_name, raw, latency)
    _charge(usage)
    _record(state, {"task": task, "model": model_name, "ok": True, **usage})
    _record_budget_summary(state)
    _CACHE.set(task, prompt, model_name, parsed)
    return parsed


def _supports_tool_calling(model: BaseChatModel) -> bool:
    """Whether the wrapped provider supports ``json_schema`` response_format.

    NVIDIA NIM / nemotron rejects ``json_schema`` (400) and overflows its tiny
    context on ``json_mode``, so structured output for those must go through the
    plain "reply with JSON" prompt + Pydantic validation path instead.
    """
    raw = str(getattr(model, "model", ""))
    base = _resolve_openai_base_url()
    if "nvidia" in base or "nim" in base or "nemotron" in raw:
        return False
    return True


def _structured_call(model: BaseChatModel, schema: type[BaseModel], messages: Any,
                     metadata: Optional[Dict[str, Any]] = None) -> Any:
    """Return a tool-calling structured response, or fall back to JSON-in-prompt."""
    invoke_cfg = {"metadata": metadata} if metadata else None
    try:
        if not _supports_tool_calling(model):
            raise TypeError("provider does not support json_schema response_format")
        bound = model.with_structured_output(schema)
        result = bound.invoke(messages, config=invoke_cfg)
        if isinstance(result, schema) or isinstance(result, dict) or isinstance(result, str):
            return result
    except (NotImplementedError, AttributeError, TypeError):
        pass
    except Exception:  # noqa: BLE001
        pass
    return _json_invoke(model, schema, messages, metadata=metadata)


def _json_invoke(model: BaseChatModel, schema: type[BaseModel], messages: Any,
                 attempts: int = 3,
                 metadata: Optional[Dict[str, Any]] = None) -> dict:
    """Prompt the model for a plain JSON object and hand it off for validation.

    For structured-output-averse providers (NVIDIA NIM / small local models) we
    avoid dumping ``model_json_schema()`` into the prompt - those models tend to
    echo the schema back verbatim. Instead we give a compact field shape hint
    and rely on ``schema.model_validate`` to enforce the contract.

    Small models still mangle the response occasionally (e.g. copy a list into a
    str field); we retry a few times feeding the validation error back so the
    model can correct itself rather than failing the whole node.
    """
    hint = _schema_shape_hint(schema)
    wrap_field = _list_container_field(schema)
    last_msg: Any = None
    invoke_cfg = {"metadata": metadata} if metadata else None
    for attempt in range(attempts):
        json_prompt = (
            _messages_to_str(messages)
            + "\n\nReply with ONLY a valid JSON object. No markdown fences, no commentary.\n"
            + "Expected shape (field names and types must match exactly):\n"
            + hint
        )
        reply = model.invoke(json_prompt, config=invoke_cfg)
        last_msg = reply
        text = _extract_text(reply)
        data = _json_from_text(text)
        if isinstance(data, list) and wrap_field:
            # small models often return the bare list of items instead of the
            # {"<container>": [...]} wrapper - lift it into the container field.
            data = {wrap_field: data}
        data = _coerce_string_fields(schema, data)
        messages_lst = (
            list(messages) if isinstance(messages, (list, tuple)) else [{"role": "user", "content": str(messages)}]
        )
        try:
            if isinstance(data, dict):
                _stash_raw_reply(model, last_msg)
                return schema.model_validate(data).model_dump()
            _stash_raw_reply(model, last_msg)
            return schema.model_validate_json(text).model_dump()
        except Exception as exc:  # noqa: BLE001  # validation error -> retry
            messages_lst.append({
                "role": "user",
                "content": (
                    "Your previous reply did not parse:\n"
                    f"{str(exc)[:300]}\n"
                    "Return the corrected JSON matching the expected shape exactly."
                ),
            })
            messages = messages_lst
    _stash_raw_reply(model, last_msg)
    if isinstance(data, dict):
        return data
    return {}


def _coerce_string_fields(schema: type[BaseModel], data: Any) -> Any:
    """Best-effort rescue for small models that paste objects into ``str`` fields.

    e.g. ``evidence`` in an insight may come back as the source dict instead of
    a quoted number string. If a declared ``str`` field got a dict/list here we
    stringify it so the subsequent Pydantic validation still passes.
    """
    from typing import List as _TList
    from typing import get_origin as _get_origin
    if not isinstance(data, dict):
        return data

    def _inner_class(annotation) -> Optional[type]:
        origin = _get_origin(annotation)
        if origin in (_TList, list):
            args = getattr(annotation, "__args__", ())
            if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                return args[0]
        return None

    for fname, field in schema.model_fields.items():
        if fname not in data or not isinstance(data[fname], (dict, list)):
            continue
        ann = field.annotation
        inner = _inner_class(ann)
        target_name = getattr(ann, "__name__", None) or getattr(inner, "__name__", None)

        # str field got an object -> stringify
        if target_name == "str" and isinstance(data[fname], (dict, list)):
            data[fname] = str(data[fname])
            continue

        # list of models -> recurse into each item
        if inner is not None and isinstance(data[fname], list):
            data[fname] = [_coerce_string_fields(inner, it) for it in data[fname] if isinstance(it, dict)]

        # single nested model -> recurse
        if isinstance(ann, type) and issubclass(ann, BaseModel) and isinstance(data[fname], dict):
            data[fname] = _coerce_string_fields(ann, data[fname])
    return data


def _stash_raw_reply(model: BaseChatModel, reply: Any) -> None:
    """Remember the last raw provider reply so usage metadata survives."""
    try:
        model._llm_last_raw_reply = reply
    except Exception:  # noqa: BLE001
        pass


def _list_container_field(schema: type[BaseModel]) -> Optional[str]:
    """Name of a ``List[...]``-typed field, if the schema has exactly one.

    Used to lift a bare list (that small models return instead of the
    ``{"field": [...]}`` wrapper) back into its container field.
    """
    from typing import List as _TList
    candidates = []
    for name, field in schema.model_fields.items():
        ann = field.annotation
        origin = getattr(ann, "__origin__", None)
        if origin in (_TList, list):
            candidates.append(name)
    return candidates[0] if len(candidates) == 1 else None


def _schema_shape_hint(schema: type[BaseModel]) -> str:
    """JSON skeleton (typed example) for a Pydantic schema.

    Full ``model_json_schema()`` docs get echoed back by small models
    (nemotron-mini & co.); a terse concrete example - with placeholder values
    for every field - produces usable output that ``schema.model_validate``
    still accepts. Nested ``BaseModel`` fields are expanded recursively.
    """
    def _example_for(annotation: Any, depth: int = 0) -> Any:
        if depth > 3:
            return None
        origin = getattr(annotation, "__origin__", None)
        args = getattr(annotation, "__args__", ())
        if origin is list or origin is getattr(__import__("typing"), "List", list):
            inner = args[0] if args else str
            return [_example_for(inner, depth + 1)]
        if origin is dict or origin is getattr(__import__("typing"), "Dict", dict):
            return {"key": "value"}
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return _model_example(annotation, depth + 1)
        name = getattr(annotation, "__name__", str(annotation)).lower()
        if "float" in name or "int" in name:
            return 1
        if "bool" in name:
            return True
        return "example"
    def _model_example(model: type[BaseModel], depth: int = 0) -> dict:
        out: Dict[str, Any] = {}
        for fname, field in model.model_fields.items():
            try:
                out[fname] = _example_for(field.annotation, depth)
            except Exception:  # noqa: BLE001
                out[fname] = "example"
        return out
    return json.dumps(_model_example(schema), indent=2, default=str)



def _json_from_text(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        last = text.rfind("```")
        text = text[first_nl + 1 : last].strip() if last > first_nl else text[first_nl + 1 :].strip()
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        pass
    try:
        starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
        ends = [i for i in (text.rfind("}"), text.rfind("]")) if i != -1]
        if starts and ends and min(starts) < max(ends):
            return json.loads(text[min(starts) : max(ends) + 1])
    except Exception:  # noqa: BLE001
        pass
    return None


def plain_invoke(
    task: str,
    messages: Union[str, Sequence[Dict[str, Any]]],
    temperature: float = 0.2,
    chat: Optional[BaseChatModel] = None,
    state: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Non-structured free-text call; returns the text reply."""
    model = chat or build_chat_model(task, temperature=temperature)
    model_name = _llm_model_name(model)
    run_metadata = _tracing_metadata(state, {"task": task, **(metadata or {})})
    _pace()
    t0 = time.monotonic()
    invoke_cfg = {"metadata": run_metadata} if run_metadata else None
    result = model.invoke(
        messages if isinstance(messages, (list, tuple)) else [{"role": "user", "content": messages}],
        config=invoke_cfg,
    )
    latency = time.monotonic() - t0
    text = _extract_text(result)
    usage = _usage_stats(model_name, result, latency)
    _charge(usage)
    _record(state, {"task": task, "model": model_name, "ok": True, **usage})
    _record_budget_summary(state)
    return text


__all__ = [
    "ResilientFallbackModel",
    "build_chat_model",
    "structured_invoke",
    "plain_invoke",
    "_price_for",
    "LANGSMITH_TRACING_ENABLED",
    "LANGSMITH_PROJECT",
    "budget_total",
    "budget_reset",
]
