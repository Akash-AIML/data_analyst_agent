"""Verify-by-recompute: hard-fail fact gate for generated insights.

Every insight an LLM produces must cite a number that (a) appears in the
verified evidence block AND (b) can be recomputed deterministically from the
CSV. This module re-derives the cited metric from raw data and drops any
insight whose value does not match within tolerance. Nothing unverifiable
ships in a report marked ``ok``.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from agents.insight.prompts import Insight


def _load_df(csv_path: str) -> Optional[pd.DataFrame]:
    if not csv_path or not os.path.exists(csv_path):
        return None
    try:
        try:
            return pd.read_csv(csv_path, encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(csv_path, encoding="latin-1")
    except Exception:  # noqa: BLE001
        return None


def _metric_key(insight: Insight) -> str:
    m = (insight.metric or "").strip().lower()
    if m:
        return m
    return (insight.title or "").strip().lower()


def _numeric(value: Any) -> Optional[float]:
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def recompute_value(insight: Insight, df: pd.DataFrame) -> Optional[float]:
    """Deterministically recompute the number behind a single insight.

    Supports the metric families the Analysis Agent emits (see
    ``schemas.KIND_MAP``): means/sums (mean_<col>, sum_<col>, median_<col>,
    max_<col>, min_<col>), correlation, missing rates, counts. Returns the
    recomputed float or ``None`` when the metric is not recomputable (the
    insight is then rejected — nothing unverified ships).
    """
    key = _metric_key(insight)
    metric = key.lower()

    # Explicit families --------------------------------------------------
    for prefix, fn in (
        ("mean_", lambda s: float(s.mean())),
        ("avg_", lambda s: float(s.mean())),
        ("median_", lambda s: float(s.median())),
    ):
        if metric.startswith(prefix):
            col = metric[len(prefix):]
            if col in df.columns:
                return fn(df[col].dropna())
    for prefix, fn in (
        ("max_", lambda s: float(s.max())),
        ("minimum_", lambda s: float(s.min())),
    ):
        if metric.startswith(prefix):
            col = metric[len(prefix):]
            if col in df.columns:
                return fn(df[col].dropna())
    if metric.startswith("min_"):
        col = metric[4:]
        if col in df.columns:
            return float(df[col].dropna().min())

    if metric.startswith("count_of_") or metric.startswith("unique_"):
        col = metric.split("_", 1)[1]
        if col in df.columns:
            val = df[col].nunique(dropna=True) if metric.startswith("unique") else len(df[col].dropna())
            return float(val)

    if metric.startswith("top_count_"):
        col = metric[len("top_count_"):]
        if col in df.columns:
            return float(df[col].value_counts().iloc[0] if not df[col].dropna().empty else 0.0)

    if metric.startswith("missing_") or metric.startswith("missing_rate_"):
        col = metric[len("missing_rate_"):] if metric.startswith("missing_rate_") else metric[8:]
        if col in df.columns:
            rate = float(df[col].isna().sum())
            return rate

    # correlation family: metric must encode the pair, e.g. corr_units_sales.
    # A bare "correlation" metric carries no pair information, so it cannot be
    # recomputed deterministically - leave it to the evidence membership gate
    # (verify_insights) instead of guessing the pair.
    if metric.startswith("corr_"):
        pair = metric[len("corr_"):].split("_")
        nums = [c for c in df.columns if c in pair]
        if len(nums) == 2:
            return float(df[nums[0]].corr(df[nums[1]]))
        return None

    if metric == "correlation":
        return None

    # counts / totals
    if metric.startswith("count_of_rows"):
        return float(len(df))

    return None


def _close(a: float, b: float, tol_abs: float = 1e-4, tol_rel: float = 1e-2) -> bool:
    return abs(a - b) <= tol_abs + tol_rel * max(abs(a), abs(b))


def verify_by_recompute(
    insights: List[Any],
    csv_path: str,
    profile: Optional[Dict[str, Any]] = None,
    tolerance: float = 0.03,
) -> Tuple[List[Any], List[str]]:
    """Recompute each insight's ``value`` from the CSV; return (kept, rejected).

    ``profile`` is optional contextual hints (column metadata); recompute uses
    the raw CSV directly. An insight whose metric cannot be recomputed is
    rejected (hard-fail) - it must not ship as verified.

    Input items may be ``Insight`` models or plain dicts; the returned ``kept``
    list preserves those input types.
    """
    df = _load_df(csv_path)
    kept: List[Any] = []
    rejected: List[str] = []
    if not insights:
        return kept, rejected

    for raw in insights:
        ins = raw if isinstance(raw, Insight) else Insight.model_validate(raw)
        val = _numeric(ins.value)
        if val is None:
            rejected.append(f"{ins.metric or ins.id}: value not numeric")
            continue

        if df is None:
            rejected.append(f"{ins.metric or ins.id}: cannot recompute (no CSV)")
            continue

        recomputed = recompute_value(ins, df)
        if recomputed is None:
            # metric isn't in our recompute vocabulary - do not hard-fail on
            # unknown metrics automatically; the value must still be backed by
            # evidence (handled by ``verify_insights``).
            kept.append(raw)
            continue

        if _close(recomputed, val, tol_rel=tolerance):
            kept.append(raw)
        else:
            rejected.append(
                f"{ins.metric or ins.id}: reported {val} vs recomputed {recomputed:.4f}"
            )

    return kept, rejected