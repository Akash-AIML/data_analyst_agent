"""Unit tests for the verify-by-recompute gate (no LLM needed)."""

from __future__ import annotations

import os

import pandas as pd
import pytest

from agents.insight.prompts import Insight
from agents.insight.verify import verify_by_recompute


@pytest.fixture()
def csv_path(tmp_path):
    path = tmp_path / "tiny.csv"
    pd.DataFrame({
        "units": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "sales": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0],
        "region": ["a", "b", "a", "b", "a", "b", "a", "b", "a", "b"],
    }).to_csv(path, index=False)
    return str(path)


def _ins(metric: str, value: float, idx: int = 1) -> Insight:
    return Insight(
        id=idx,
        title=metric,
        body="t",
        evidence=str(value),
        metric=metric,
        value=value,
        confidence=0.9,
    )


def test_correct_mean_passes(csv_path):
    """10 rows of 1..10 -> mean = 5.5. Must pass."""
    kept, rejects = verify_by_recompute(
        [_ins("mean_units", 5.5)], csv_path,
    )
    assert len(kept) == 1
    assert rejects == []


def test_small_rounding_error_passes_within_tolerance(csv_path):
    """5.51 vs 5.5 (0.18% off) is within default 3% relative tolerance."""
    kept, rejects = verify_by_recompute(
        [_ins("mean_units", 5.51)], csv_path,
    )
    assert len(kept) == 1
    assert rejects == []


def test_large_error_fails(csv_path):
    """8.0 vs 5.5 is ~45% off -> must be rejected."""
    kept, rejects = verify_by_recompute(
        [_ins("mean_units", 8.0)], csv_path,
    )
    assert kept == []
    assert len(rejects) == 1
    assert "mean_units" in rejects[0]


def test_strict_tolerance_rejects_rounding(csv_path):
    """0.1% relative tolerance should reject a 0.18% rounding error."""
    kept, rejects = verify_by_recompute(
        [_ins("mean_units", 5.51)], csv_path,
        tolerance=0.001,
    )
    assert kept == []
    assert rejects


def test_abs_tolerance_handles_small_values(csv_path):
    """Tiny magnitudes: relative tol is useless, abs tol carries the day."""
    # mean of units is 5.5; report 5.5001 -> 0.002% off.
    kept, rejects = verify_by_recompute(
        [_ins("mean_units", 5.5001)], csv_path,
        tolerance=0.0, abs_tolerance=1e-3,
    )
    assert len(kept) == 1
    assert rejects == []


def test_env_override_relaxed(monkeypatch, csv_path):
    monkeypatch.setenv("RECOMPUTE_TOLERANCE", "0.5")
    # 8.0 vs 5.5 -> 45% off, but with 50% tolerance it passes.
    kept, _ = verify_by_recompute(
        [_ins("mean_units", 8.0)], csv_path,
    )
    assert len(kept) == 1


def test_env_override_strict(monkeypatch, csv_path):
    monkeypatch.setenv("RECOMPUTE_TOLERANCE", "0.0")
    monkeypatch.setenv("RECOMPUTE_ABS_TOLERANCE", "0.0")
    # Even a tiny delta must be rejected when both tolerances are zero.
    kept, rejects = verify_by_recompute(
        [_ins("mean_units", 5.5000001)], csv_path,
    )
    assert kept == []
    assert rejects


def test_non_recomputable_metric_passes_through(csv_path):
    """Metrics outside the recompute vocabulary must not hard-fail; they fall
    through to the evidence-membership gate in verify_insights."""
    ins = _ins("unknown_metric", 42.0)
    kept, rejects = verify_by_recompute([ins], csv_path)
    assert len(kept) == 1
    assert rejects == []


def test_non_numeric_value_rejected(csv_path):
    """Insight whose value isn't a number must be rejected outright."""
    # model_construct bypasses Pydantic validation so we can simulate a model
    # that returned a non-numeric ``value`` (e.g. NaN-coerced by an upstream
    # provider). The gate must still reject.
    ins = Insight.model_construct(
        id=1, title="t", body="b", evidence="x",
        metric="mean_units", value=float("nan"),
        confidence=0.5,
    )
    kept, rejects = verify_by_recompute([ins], csv_path)
    assert kept == []
    assert rejects and "not numeric" in rejects[0]
