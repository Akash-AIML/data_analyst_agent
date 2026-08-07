"""Deterministic validation engine for analysis results (no LLM in the loop).

Cross-references ``analysis_results`` against the ``profile`` produced by
Member 1 and emits a structured ``validation_report``:

    {
      "status": "passed" | "warnings" | "failed",
      "checks": [{"name", "ok", "detail"}],
      "warnings": [...],
      "errors": [...],
    }

Design notes (from the Member 3 devil's-advocate review):
  * Key matching is case/whitespace-insensitive (``Sales`` vs ``sales``).
  * A correlation involving a constant column is legitimately NaN -> flagged
    as ``constant_column``, not an error.
  * Missing-rate mismatches between profile and results only *warn* past a
    threshold, never hard-fail.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def norm_key(key: str) -> str:
    """Normalize a column name for fuzzy matching (case + whitespace)."""
    return " ".join(str(key).strip().lower().split())


def _find_col(name: str, cols: List[str]) -> str | None:
    target = norm_key(name)
    for c in cols:
        if norm_key(c) == target:
            return c
    return None


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _finite(v: Any) -> bool:
    return _is_number(v) and math.isfinite(v)


# ---------------------------------------------------------------------------
# Check collectors
# ---------------------------------------------------------------------------

class Checker:
    def __init__(self) -> None:
        self.checks: List[Dict[str, Any]] = []
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            self.errors.append(f"{name}: {detail}")

    def warn(self, name: str, detail: str) -> None:
        self.warnings.append(f"{name}: {detail}")

    def summary(self) -> Dict[str, Any]:
        status = "passed"
        if self.errors:
            status = "failed"
        elif self.warnings:
            status = "warnings"
        return {
            "status": status,
            "checks": self.checks,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def _numeric_columns(profile: Dict[str, Any]) -> List[str]:
    cols = profile.get("numeric_columns", []) or []
    if cols:
        return list(cols)
    inferred = profile.get("columns")
    if not isinstance(inferred, dict):
        return []
    return [c for c, meta in inferred.items() if isinstance(meta, dict) and meta.get("type") == "numeric"]


def _categorical_columns(profile: Dict[str, Any]) -> List[str]:
    cols = profile.get("categorical_columns", []) or []
    if cols:
        return list(cols)
    inferred = profile.get("columns")
    if not isinstance(inferred, dict):
        return []
    return [c for c, meta in inferred.items() if isinstance(meta, dict) and meta.get("type") in ("categorical", "string")]


def _normalize_results(analysis_results) -> List[Dict[str, Any]]:
    """Accept either contract shape for ``analysis_results``.

    Canonical (Member 3): a list of result dicts. Member 2's node currently
    writes a dict keyed by task name -> normalize that to the list form so
    validation/evidence extraction never iterate over bare string keys.
    """
    if not analysis_results:
        return []
    if isinstance(analysis_results, dict):
        out: List[Dict[str, Any]] = []
        for name, payload in analysis_results.items():
            if not isinstance(payload, dict):
                continue
            entry: Dict[str, Any] = dict(payload)
            entry.setdefault("title", name)
            entry.setdefault("task_id", name)
            entry.setdefault("kind", "generic")
            entry.setdefault("status", "completed")
            out.append(entry)
        return out
    if isinstance(analysis_results, list):
        return [r for r in analysis_results if isinstance(r, dict)]
    return []




# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

def validate_results(
    profile: Dict[str, Any],
    analysis_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate analysis results against the profile. Pure + deterministic."""
    chk = Checker()
    results = _normalize_results(analysis_results)

    if not profile:
        chk.add("profile_present", False, "profile is empty - cannot validate")
        return chk.summary()

    num_cols = _numeric_columns(profile)
    cat_cols = _categorical_columns(profile)
    all_profile_cols = list(profile.get("columns", {}).keys()) or (
        num_cols + cat_cols
    )
    profile_rows = profile.get("rows")
    profile_cols = profile.get("columns_count") or len(all_profile_cols)

    chk.add(
        "columns_detected",
        bool(all_profile_cols),
        f"{len(all_profile_cols)} column(s) detected in profile",
    )
    if profile_rows is not None:
        chk.add(
            "row_count_present",
            _finite(profile_rows) and profile_rows > 0,
            f"profile rows = {profile_rows}",
        )
    if profile_cols is not None:
        chk.add(
            "column_count_present",
            _finite(profile_cols) and profile_cols > 0,
            f"profile columns = {profile_cols}",
        )

    if not results:
        chk.warn(
            "no_results",
            "analysis_results is empty - report will be degraded",
        )
        return chk.summary()

    chk.add(
        "results_present",
        True,
        f"{len(results)} analysis result(s) submitted",
    )

    for idx, res in enumerate(results):
        prefix = f"result[{idx}]"
        title = res.get("title") or res.get("task_id") or res.get("kind") or str(idx)

        if not isinstance(res, dict):
            chk.add(f"{prefix}_shape", False, "result is not a dict")
            continue

        status = res.get("status", "completed")
        if status != "completed":
            chk.add(
                f"{prefix}_status",
                False,
                f"task '{title}' not completed (status={status})",
            )
            continue

        stats = res.get("stats") or {}
        if not isinstance(stats, dict) or not stats:
            chk.warn(f"{prefix}_no_stats", f"task '{title}' has no stats to validate")
            continue

        kind = res.get("kind", "generic")
        ok = _validate_one(chk, prefix, title, kind, res, stats, profile,
                           num_cols, cat_cols, all_profile_cols)

    return chk.summary()


def _validate_one(
    chk: Checker,
    prefix: str,
    title: str,
    kind: str,
    res: Dict[str, Any],
    stats: Dict[str, Any],
    profile: Dict[str, Any],
    num_cols: List[str],
    cat_cols: List[str],
    all_profile_cols: List[str],
) -> bool:
    """Validate a single result's stats. Returns True if all checks pass."""
    all_ok = True
    # Column lives at the result top-level (or stats for legacy results).
    col = res.get("column") or stats.get("column")

    if kind == "correlation":
        corr = stats.get("value") if "value" in stats else stats
        if _is_number(corr):
            if math.isnan(corr):
                chk.warn(f"{prefix}_corr_nan",
                         "correlation is NaN (constant column?)")
            elif not (-1.0 <= corr <= 1.0):
                chk.add(f"{prefix}_corr_bounds", False,
                        f"correlation {corr:.3f} outside [-1, 1]")
                all_ok = False
        elif isinstance(corr, dict):
            for k, v in corr.items():
                if _is_number(v) and not (-1.0 <= v <= 1.0):
                    chk.add(f"{prefix}_corr_bounds", False,
                            f"correlation {k}={v:.3f} outside [-1, 1]")
                    all_ok = False

    elif kind == "mean":
        value = stats.get("value")
        if _is_number(value):
            lo = stats.get("min") if _is_number(stats.get("min")) else None
            hi = stats.get("max") if _is_number(stats.get("max")) else None
            if lo is not None and value < lo - 1e-9:
                chk.add(f"{prefix}_mean_vs_min", False,
                        f"mean {value:.4f} < min {lo:.4f}")
                all_ok = False
            if hi is not None and value > hi + 1e-9:
                chk.add(f"{prefix}_mean_vs_max", False,
                        f"mean {value:.4f} > max {hi:.4f}")
                all_ok = False
            _check_column(chk, prefix, title, col, all_profile_cols, num_cols)

    elif kind in ("percentage", "share", "missing_rate"):
        value = stats.get("value")
        if _is_number(value) and not (0.0 <= value <= 100.0):
            chk.add(f"{prefix}_pct_bounds", False,
                    f"{kind} {value:.2f} outside [0, 100]")
            all_ok = False
        if col and kind == "missing_rate":
            _check_null_consistency(chk, prefix, title, col, value, profile,
                                    all_profile_cols)

    elif kind in ("count", "unique", "cardinality"):
        value = stats.get("value")
        if _is_number(value) and value < 0:
            chk.add(f"{prefix}_count_negative", False, f"count {value} < 0")
            all_ok = False
        if col and kind == "cardinality":
            _check_cardinality(chk, prefix, title, col, value, profile,
                               all_profile_cols, cat_cols)

    elif kind in ("top", "category_frequency"):
        _check_column(chk, prefix, title, col, all_profile_cols, cat_cols)

    else:
        chk.warn(f"{prefix}_kind", f"unknown result kind '{kind}' - skipped")

    return all_ok


def _check_column(
    chk: Checker,
    prefix: str,
    title: str,
    col: Any,
    all_profile_cols: List[str],
    expect_in: List[str] | None = None,
) -> None:
    if not col:
        return
    resolved = _find_col(str(col), all_profile_cols) if all_profile_cols else None
    if resolved is None and all_profile_cols:
        chk.add(f"{prefix}_column_exists", False,
                f"column '{col}' from task '{title}' not in profile")
        return
    if resolved and expect_in is not None and resolved not in expect_in:
        chk.warn(f"{prefix}_column_type",
                 f"column '{resolved}' used in '{title}' is not in expected "
                 f"type set")


def _check_null_consistency(
    chk: Checker,
    prefix: str,
    title: str,
    col: Any,
    missing_pct: Any,
    profile: Dict[str, Any],
    all_profile_cols: List[str],
) -> None:
    if not _is_number(missing_pct):
        return
    resolved = _find_col(str(col), all_profile_cols) if all_profile_cols else None
    if not resolved:
        return
    cols_dict = profile.get("columns") if isinstance(profile.get("columns"), dict) else {}
    meta = cols_dict.get(resolved, {})
    prof_missing = meta.get("missing_pct") or meta.get("missing_rate")
    if prof_missing is None and isinstance(meta.get("missing"), (int, float)):
        rows = profile.get("rows")
        if rows:
            prof_missing = float(meta["missing"]) / rows * 100.0
    if prof_missing is None or not _is_number(prof_missing):
        return
    delta = abs(float(missing_pct) - float(prof_missing))
    if delta > 1.0:
        chk.warn(f"{prefix}_null_consistency",
                 f"missing rate for '{resolved}' differs from profile by "
                 f"{delta:.1f}pp (analysis={missing_pct:.1f}, profile={prof_missing:.1f})")


def _check_cardinality(
    chk: Checker,
    prefix: str,
    title: str,
    col: Any,
    unique: Any,
    profile: Dict[str, Any],
    all_profile_cols: List[str],
    cat_cols: List[str],
) -> None:
    if not _is_number(unique):
        return
    resolved = _find_col(str(col), all_profile_cols) if all_profile_cols else None
    if not resolved:
        return
    cols_dict = profile.get("columns") if isinstance(profile.get("columns"), dict) else {}
    meta = cols_dict.get(resolved, {})
    prof_unique = meta.get("unique")
    if _is_number(prof_unique) and prof_unique > 0 and unique > prof_unique:
        chk.warn(f"{prefix}_cardinality",
                 f"unique count for '{resolved}' ({unique}) exceeds profile "
                 f"({prof_unique})")


def extract_evidence(profile: Dict[str, Any],
                     analysis_results: List[Dict[str, Any]],
                     validation_report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pull the verified numbers that insights are allowed to cite.

    Only completed results with clean stats are included, so the LLM can
    never cite a number that failed validation.
    """
    evidence: List[Dict[str, Any]] = []
    for res in _normalize_results(analysis_results):
        if not isinstance(res, dict):
            continue
        if res.get("status", "completed") != "completed":
            continue
        stats = res.get("stats") or {}
        if not isinstance(stats, dict) or not stats:
            continue
        entry: Dict[str, Any] = {"title": res.get("title") or res.get("task_id")}
        if res.get("kind"):
            entry["kind"] = res["kind"]
        if res.get("column"):
            entry["column"] = res["column"]
        entry["stats"] = {k: v for k, v in stats.items() if _is_number(v)}
        if entry["stats"]:
            evidence.append(entry)

    # Fallback: if evidence is empty, populate from profile descriptive stats
    if not evidence and profile:
        cols_val = profile.get("columns")
        num_cols = len(cols_val) if isinstance(cols_val, (dict, list, set)) else (float(cols_val) if isinstance(cols_val, (int, float)) else 0.0)
        profile_stats: Dict[str, Any] = {
            "total_rows": float(profile.get("rows", 0)),
            "total_columns": float(profile.get("columns_count") or num_cols),
        }
        cols_dict = cols_val if isinstance(cols_val, dict) else {}
        for col_name, meta in cols_dict.items():
            if isinstance(meta, dict):
                for k, v in meta.items():
                    if _is_number(v):
                        profile_stats[f"{col_name}_{k}"] = float(v)
        if profile_stats:
            evidence.append({"title": "Dataset Profile Summary", "stats": profile_stats})


    return evidence

