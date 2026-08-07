"""Shared test fixtures: healthy / partial / failed-upstream state sets.

These let Member 3 develop and test before Members 1 & 2 deliver, and double
as the starting point for the Day 2 team integration harness (run the whole
pipeline on 3 diverse CSVs).
"""

from __future__ import annotations

import base64
import os
from typing import Any, Dict

from agents.state import build_state

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


# ---------------------------------------------------------------------------
# Tiny real CSV + fake images so the report generator can embed real bytes.
# ---------------------------------------------------------------------------

SALES_CSV = os.path.join(DATA_DIR, "sales.csv")

SALES_CSV_ROWS = [
    "region,product,units,price,sales,date",
    "North,WidgetA,120,9.99,1198.80,2024-01-05",
    "North,WidgetB,90,14.50,1305.00,2024-01-08",
    "South,WidgetA,80,9.99,799.20,2024-02-12",
    "South,WidgetC,210,7.25,1522.50,2024-02-20",
    "East,WidgetB,150,14.50,2175.00,2024-03-03",
    "East,WidgetA,60,9.99,599.40,2024-03-15",
    "West,WidgetC,175,7.25,1268.75,2024-04-02",
    "West,WidgetB,110,14.50,1595.00,2024-04-18",
]


def ensure_fixture_files() -> None:
    """Write the sample CSV and tiny valid PNGs if they don't exist yet."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SALES_CSV):
        with open(SALES_CSV, "w", encoding="utf-8") as fh:
            fh.write("\n".join(SALES_CSV_ROWS) + "\n")

    png = (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n\x2d\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    for name in ("sales_by_region.png", "sales_trend.png", "missing_rates.png"):
        path = os.path.join(DATA_DIR, name)
        if not os.path.exists(path):
            with open(path, "wb") as fh:
                fh.write(png)


# ---------------------------------------------------------------------------
# State builders
# ---------------------------------------------------------------------------

def profile_dict() -> Dict[str, Any]:
    """A typical Member-1 profile for the sales CSV."""
    return {
        "rows": 8,
        "columns_count": 6,
        "numeric_columns": ["units", "price", "sales"],
        "categorical_columns": ["region", "product"],
        "id_columns": [],
        "datetime_columns": ["date"],
        "columns": {
            "region": {"type": "categorical", "unique": 4, "missing": 0},
            "product": {"type": "categorical", "unique": 3, "missing": 0},
            "units": {"type": "numeric", "min": 60, "max": 210, "missing": 0},
            "price": {"type": "numeric", "min": 7.25, "max": 14.5, "missing": 0},
            "sales": {"type": "numeric", "min": 599.4, "max": 2175.0, "missing": 0},
            "date": {"type": "datetime", "unique": 8, "missing": 0},
        },
    }


def healthy_results() -> list:
    return [
        {
            "task_id": "t1",
            "title": "Sales by region",
            "kind": "category_frequency",
            "column": "region",
            "status": "completed",
            "stats": {"value": 4, "top": "North", "share": 25.0},
            "files": ["sales_by_region.png"],
        },
        {
            "task_id": "t2",
            "title": "Sales correlation with units",
            "kind": "correlation",
            "column": "sales",
            "status": "completed",
            "stats": {"value": 0.92},
            "files": ["sales_trend.png"],
        },
        {
            "task_id": "t3",
            "title": "Average sales",
            "kind": "mean",
            "column": "sales",
            "status": "completed",
            "stats": {"value": 1308.0, "min": 599.4, "max": 2175.0},
            "files": [],
        },
        {
            "task_id": "t4",
            "title": "Missing rate on units",
            "kind": "missing_rate",
            "column": "units",
            "status": "completed",
            "stats": {"value": 0.0},
            "files": ["missing_rates.png"],
        },
    ]


def healthy_state() -> Dict[str, Any]:
    """Fully successful upstream run."""
    ensure_fixture_files()
    files = [
        os.path.join(DATA_DIR, "sales_by_region.png"),
        os.path.join(DATA_DIR, "sales_trend.png"),
        os.path.join(DATA_DIR, "missing_rates.png"),
    ]
    return build_state(
        csv_path=SALES_CSV,
        profile=profile_dict(),
        profile_report_path=os.path.join(DATA_DIR, "profile.html"),
        analysis_results=healthy_results(),
        generated_files=files,
        execution_log=[{"task": "planner", "msg": "planned 4 tasks"}],
        reflection_notes=["4 tasks planned, none skipped"],
        status="in_progress",
    )


def partial_results() -> list:
    results = healthy_results()
    # Drop one image result, inject a constant-column NaN correlation and a
    # missing-rate mismatch warning.
    results[1]["stats"] = {"value": float("nan")}          # constant col
    results[2]["stats"]["value"] = 1308.0                  # keep mean valid
    results[3]["stats"]["value"] = 15.0                    # mismatch w/ profile
    return [r for r in results if r["task_id"] != "t1"]


def partial_state() -> Dict[str, Any]:
    """Upstream succeeded but produced warnings + missing charts."""
    ensure_fixture_files()
    files = [
        os.path.join(DATA_DIR, "sales_trend.png"),
        os.path.join(DATA_DIR, "missing_rates.png"),
    ]
    return build_state(
        csv_path=SALES_CSV,
        profile=profile_dict(),
        analysis_results=partial_results(),
        generated_files=files,
        execution_log=[],
        reflection_notes=[],
        status="in_progress",
    )


def failed_state() -> Dict[str, Any]:
    """Upstream failed - Member 3 must degrade gracefully."""
    return build_state(
        csv_path=SALES_CSV,
        profile=profile_dict(),
        analysis_results=[],
        generated_files=[],
        execution_log=[
            {"task": "planner", "msg": "planned 3 tasks"},
            {"task": "t1", "msg": "ModuleNotFoundError: sklearn not installed"},
        ],
        reflection_notes=["all plot tasks failed"],
        error_log=["t1 failed: sklearn missing", "t2 failed: timeout"],
        status="failed",
    )


def evidence_for(state: Dict[str, Any]) -> list:
    """Deterministic evidence snapshot for insight-prompt tests."""
    from agents.insight.validation import extract_evidence

    return extract_evidence(state["profile"], state["analysis_results"], {})


def decode_png(path: str) -> str:
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")
