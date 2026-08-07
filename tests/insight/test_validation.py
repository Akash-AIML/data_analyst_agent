"""Tests for the deterministic validation engine."""

from __future__ import annotations

import math

from agents.insight.validation import (
    extract_evidence,
    norm_key,
    validate_results,
)
from tests.insight import fixtures



def test_healthy_results_pass():
    report = validate_results(fixtures.profile_dict(), fixtures.healthy_results())
    assert report["status"] == "passed"
    assert not report["errors"]
    names = {c["name"] for c in report["checks"]}
    assert "results_present" in names
    assert "columns_detected" in names


def test_case_insensitive_column_matching():
    profile = fixtures.profile_dict()
    results = [
        {
            "task_id": "t1",
            "title": "Avg Sales",
            "kind": "mean",
            "column": "  SALES ",  # uppercase + padding
            "status": "completed",
            "stats": {"value": 1308.0, "min": 599.4, "max": 2175.0},
        }
    ]
    report = validate_results(profile, results)
    assert report["status"] == "passed", report["errors"]


def test_unknown_column_fails():
    profile = fixtures.profile_dict()
    results = [
        {
            "task_id": "t1",
            "title": "Avg of fake",
            "kind": "mean",
            "column": "not_a_column",
            "status": "completed",
            "stats": {"value": 1.0, "min": 0.0, "max": 2.0},
        }
    ]
    report = validate_results(profile, results)
    assert report["status"] == "failed"
    assert any("column_exists" in c["name"] for c in report["checks"] if not c["ok"])


def test_correlation_out_of_bounds_fails():
    results = [
        {
            "task_id": "t1",
            "title": "corr",
            "kind": "correlation",
            "status": "completed",
            "stats": {"value": 1.7},
        }
    ]
    report = validate_results(fixtures.profile_dict(), results)
    assert report["status"] == "failed"
    assert any("corr_bounds" in c["name"] for c in report["checks"] if not c["ok"])


def test_nan_correlation_from_constant_column_is_warning_not_error():
    results = [
        {
            "task_id": "t1",
            "title": "corr with constant col",
            "kind": "correlation",
            "status": "completed",
            "stats": {"value": math.nan},
        }
    ]
    report = validate_results(fixtures.profile_dict(), results)
    assert report["status"] in ("passed", "warnings")
    assert not report["errors"]
    assert any("corr_nan" in w for w in report["warnings"])


def test_mean_outside_profile_range_fails():
    results = [
        {
            "task_id": "t1",
            "title": "bad mean",
            "kind": "mean",
            "column": "sales",
            "status": "completed",
            "stats": {"value": 9999.0, "min": 599.4, "max": 2175.0},
        }
    ]
    report = validate_results(fixtures.profile_dict(), results)
    assert report["status"] == "failed"
    assert any("mean_vs_max" in c["name"] for c in report["checks"] if not c["ok"])


def test_missing_rate_mismatch_only_warns():
    results = [
        {
            "task_id": "t1",
            "title": "missing units",
            "kind": "missing_rate",
            "column": "units",
            "status": "completed",
            "stats": {"value": 15.0},  # profile says 0 missing
        }
    ]
    report = validate_results(fixtures.profile_dict(), results)
    assert report["status"] == "warnings"
    assert not report["errors"]
    assert any("null_consistency" in w for w in report["warnings"])


def test_percentage_out_of_bounds_fails():
    results = [
        {
            "task_id": "t1",
            "title": "share",
            "kind": "share",
            "status": "completed",
            "stats": {"value": 140.0},
        }
    ]
    report = validate_results(fixtures.profile_dict(), results)
    assert report["status"] == "failed"
    assert any("pct_bounds" in c["name"] for c in report["checks"] if not c["ok"])


def test_empty_results_warn_not_fail():
    report = validate_results(fixtures.profile_dict(), [])
    assert report["status"] == "warnings"
    assert not report["errors"]
    assert any("no_results" in w for w in report["warnings"])


def test_empty_profile_fails():
    report = validate_results({}, [{"task_id": "t1", "title": "x"}])
    assert report["status"] == "failed"
    assert any("profile_present" in c["name"] for c in report["checks"] if not c["ok"])


def test_incomplete_result_fails():
    results = [
        {
            "task_id": "t1",
            "title": "failed task",
            "kind": "mean",
            "status": "failed",
            "stats": {},
        }
    ]
    report = validate_results(fixtures.profile_dict(), results)
    assert report["status"] == "failed"
    assert any("_status" in c["name"] for c in report["checks"] if not c["ok"])


def test_norm_key_is_case_and_space_insensitive():
    assert norm_key("  Sales  ") == norm_key("sales")
    assert norm_key("Order Date") == norm_key("order date")


def test_extract_evidence_excludes_failed_and_non_numeric():
    results = fixtures.healthy_results()
    results.append(
        {
            "task_id": "t9",
            "title": "broken",
            "kind": "mean",
            "status": "failed",
            "stats": {"value": 5.0},
        }
    )
    evidence = extract_evidence(fixtures.profile_dict(), results, {})
    values = {v for e in evidence for v in e["stats"].values()}
    assert 1308.0 in values
    assert 0.92 in values
    assert 5.0 not in values  # failed result never becomes evidence
