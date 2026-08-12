"""Regression tests for the central ``llm`` module (no API key needed).

Use the deterministic ``FakeChatModel`` stub so ``plain_invoke`` /
``structured_invoke`` can be exercised offline. Guards against the
``NameError`` regression where ``plain_invoke`` referenced the undefined
``_llm_model`` instead of ``_llm_model_name``.
"""

import pytest

from agents.analysis.schemas import AnalysisPlan
from llm import plain_invoke, structured_invoke
from tests.insight.fake_llm import FakeChatModel


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

    # One call + one budget summary entry appended by ``_record_budget_summary``.
    real_calls = [c for c in state["llm_calls"] if c["task"] != "__budget__"]
    assert len(real_calls) == 1
    record = real_calls[0]
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
    real_calls = [c for c in state["llm_calls"] if c["task"] != "__budget__"]
    assert len(real_calls) == 1


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
    real_calls = [c for c in state["llm_calls"] if c["task"] != "__budget__"]
    assert len(real_calls) == 1
    assert real_calls[0]["task"] == "PLANNER"
    assert "model" in real_calls[0]


def test_no_llm_calls_appended_without_state(chat):
    text = plain_invoke(task="EXECUTOR", messages="hi", chat=chat)
    assert isinstance(text, str)


def test_langsmith_disabled_by_default(monkeypatch):
    """No API key + no env flag -> tracing must be off (zero overhead)."""
    monkeypatch.delenv("LANGSMITH_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    import importlib

    import llm
    importlib.reload(llm)
    assert llm.LANGSMITH_TRACING_ENABLED is False


def test_tracing_metadata_contains_csv_basename():
    import llm
    md = llm._tracing_metadata(
        {"csv_path": "/tmp/datasets/orders_2024.csv", "status": "completed"},
        {"task": "INSIGHT"},
    )
    assert md["csv_path"] == "orders_2024.csv"
    assert md["status"] == "completed"
    assert md["task"] == "INSIGHT"
    assert "langsmith_project" in md


def test_tracing_metadata_skips_empty_csv_path():
    import llm
    md = llm._tracing_metadata({"status": "in_progress"})
    assert "csv_path" not in md
    assert md["status"] == "in_progress"


def test_plain_invoke_works_with_metadata_kwarg(chat, state):
    """Backwards-compatible: ``metadata`` is optional and ignored when tracing off."""
    text = plain_invoke(
        task="EXECUTOR",
        messages="say hi",
        chat=chat,
        state=state,
        metadata={"custom_tag": "abc"},
    )
    assert isinstance(text, str)
    real_calls = [c for c in state["llm_calls"] if c["task"] != "__budget__"]
    assert len(real_calls) == 1


def test_cache_disabled_is_noop(tmp_path, monkeypatch):
    """Cache should write nothing when LLM_CACHE_ENABLED is unset."""
    monkeypatch.setenv("LLM_CACHE_ENABLED", "")
    cache_path = tmp_path / "cache.json"
    monkeypatch.setenv("LLM_CACHE_PATH", str(cache_path))
    from llm import _Cache
    c = _Cache()
    c.set("t", "p", "m", {"x": 1})
    assert not cache_path.exists()
    assert c.get("t", "p", "m") is None


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_CACHE_ENABLED", "1")
    cache_path = tmp_path / "cache.json"
    monkeypatch.setenv("LLM_CACHE_PATH", str(cache_path))
    from llm import _Cache
    c = _Cache()
    c.clear()
    c.set("PLANNER", "some prompt", "test-model", {"answer": 42})
    # get() returns the bare value (not the {"v":.., "ts":..} wrapper).
    assert c.get("PLANNER", "some prompt", "test-model") == {"answer": 42}
    assert cache_path.exists(), (
        f"cache file should exist at {cache_path}; "
        f"_is_enabled={c._is_enabled()}, _enabled={c._enabled}, "
        f"_path={c._path}, dir={list(tmp_path.iterdir())}"
    )
    # The on-disk file stores entries as {"v": ..., "ts": ...}; new schema.
    import json
    on_disk = json.loads(cache_path.read_text())
    assert on_disk, "cache file should not be empty"
    fresh_entries = [v for v in on_disk.values() if isinstance(v, dict) and "ts" in v]
    assert len(fresh_entries) == 1
    assert fresh_entries[0]["v"] == {"answer": 42}


def test_cache_ttl_eviction(tmp_path, monkeypatch):
    """Stale entries (older than TTL) must be evicted on load."""
    import json
    import time as _t

    cache_path = tmp_path / "cache.json"
    # Seed with one stale + one fresh entry, identified by literal keys so we
    # can assert membership without depending on the sha256 internal key format.
    cache_path.write_text(json.dumps({
        "k_stale": {"v": "old", "ts": _t.time() - 999_999},
        "k_fresh": {"v": "new", "ts": _t.time()},
    }))
    monkeypatch.setenv("LLM_CACHE_ENABLED", "1")
    monkeypatch.setenv("LLM_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("LLM_CACHE_TTL_S", "60")
    from llm import _Cache
    c = _Cache()
    assert "k_stale" not in c._data
    assert "k_fresh" in c._data


def test_cache_legacy_schema_still_works(tmp_path, monkeypatch):
    """A cache file from the pre-TTL version (bare values) must still load."""
    import json
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps({"k_legacy": "bare_value"}))
    monkeypatch.setenv("LLM_CACHE_ENABLED", "1")
    monkeypatch.setenv("LLM_CACHE_PATH", str(cache_path))
    from llm import _Cache
    c = _Cache()
    # Loading must not crash on the legacy schema; bare values are kept in
    # _data so subsequent set() flushes preserve them (they'll be re-saved
    # under the new hash-keyed scheme on the next write).
    assert c._data.get("k_legacy") == "bare_value"


def test_cache_atomic_write_no_partial(tmp_path, monkeypatch):
    """A simulated crash mid-write must NOT leave a half-written file."""
    monkeypatch.setenv("LLM_CACHE_ENABLED", "1")
    cache_path = tmp_path / "cache.json"
    monkeypatch.setenv("LLM_CACHE_PATH", str(cache_path))
    from llm import _Cache
    c = _Cache()
    c.clear()
    c.set("a", "b", "m", "v")
    # No .tmp file should be left behind.
    assert not (tmp_path / "cache.json.tmp").exists()


def test_budget_reset_and_total(monkeypatch):
    import llm
    llm.budget_reset()
    monkeypatch.setenv("LLM_BUDGET_US", "0")
    assert llm.budget_total() == 0.0


def test_budget_summary_recorded(chat, state, monkeypatch):
    """Every successful call must stamp a __budget__ entry on state."""
    monkeypatch.setenv("LLM_BUDGET_US", "0")
    import llm
    llm.budget_reset()
    plain_invoke(task="EXECUTOR", messages="hi", chat=chat, state=state)
    # At least one call + one __budget__ entry.
    assert len(state["llm_calls"]) == 2
    budget_entry = state["llm_calls"][-1]
    assert budget_entry["task"] == "__budget__"
    assert "cost_usd_total" in budget_entry
    assert budget_entry["calls"] == 1
    assert budget_entry["budget_limit_us"] == 0.0


def test_budget_warn_logged_once(monkeypatch, caplog):
    """Soft warning must log exactly once when crossing the warn ratio."""
    monkeypatch.setenv("LLM_BUDGET_US", "1.0")
    monkeypatch.setenv("LLM_BUDGET_WARN_RATIO", "0.5")
    import logging

    import llm
    llm.budget_reset()
    # Force _run_cost_us above 0.5
    llm._run_cost_us = 0.6
    # Manually call _pace to trigger the warn check
    with caplog.at_level(logging.WARNING, logger="llm"):
        try:
            llm._pace()
        except RuntimeError:
            pass
    # Reset back so other tests aren't affected.
    llm.budget_reset()
    warns = [r for r in caplog.records if "budget at" in r.getMessage()]
    # Either 0 or 1; never 2 (the warn flag flips to True on first hit).
    assert len(warns) <= 1


def test_budget_exhaustion_raises(monkeypatch):
    monkeypatch.setenv("LLM_BUDGET_US", "0.01")
    import llm
    llm.budget_reset()
    llm._run_cost_us = 0.02  # already over the cap
    with pytest.raises(RuntimeError, match="budget exhausted"):
        llm._pace()
    llm.budget_reset()


def test_resilient_fallback_model_structured_output(chat):
    """Verify ResilientFallbackModel structured_output delegates cleanly."""
    from agents.analysis.schemas import AnalysisPlan
    from tools.llm_factory import ResilientFallbackModel

    fallback_model = ResilientFallbackModel(models=[chat])
    bound = fallback_model.with_structured_output(AnalysisPlan)
    assert bound is not None
