"""Tests for the HTML + PDF report generator (image + fallback resilience)."""

from __future__ import annotations

import os

import pytest

from agents.insight import report_generator
from tests.insight import fixtures



@pytest.fixture(scope="module")
def out_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("reports")
    yield str(d)


def _run(state, out_dir):
    fixtures.ensure_fixture_files()
    return report_generator.write_report(dict(state), out_dir)


def _with_insights(state):
    state = dict(state)
    state["insights"] = [
        {
            "id": 1,
            "title": "Average sale value",
            "body": "Average sales per transaction is solid.",
            "evidence": "1308.0",
            "metric": "mean_sales",
            "value": 1308.0,
            "confidence": 0.95,
        }
    ]
    state["recommendations"] = ["Investigate East pricing"]
    return state


def test_healthy_report_writes_html_and_pdf(out_dir):
    state = _run(_with_insights(fixtures.healthy_state()), out_dir)
    assert os.path.exists(state["report_path"])
    if state["pdf_path"]:
        assert os.path.exists(state["pdf_path"])
    with open(state["report_path"], encoding="utf-8") as fh:
        html = fh.read()
    assert "Data Analysis Report" in html
    assert "Executive Summary" in html
    assert "sales_by_region.png" in html  # chart captions rendered
    assert "data:image/png;base64," in html


def test_zero_charts_hides_charts_section(out_dir):
    state = fixtures.healthy_state()
    state["generated_files"] = []
    state = _run(state, out_dir)
    with open(state["report_path"], encoding="utf-8") as fh:
        html = fh.read()
    assert "<h2>Charts</h2>" not in html
    assert "<figure>" not in html
    assert '<img ' not in html


def test_missing_chart_files_are_skipped(out_dir):
    state = fixtures.healthy_state()
    state["generated_files"] = [
        os.path.join(fixtures.DATA_DIR, "sales_by_region.png"),
        os.path.join(fixtures.DATA_DIR, "does_not_exist.png"),
        "not_an_image.txt",
    ]
    state = _run(state, out_dir)
    with open(state["report_path"], encoding="utf-8") as fh:
        html = fh.read()
    assert "sales_by_region.png" in html
    assert "does_not_exist.png" not in html
    assert "not_an_image.txt" not in html


def test_partial_state_renders_warnings(out_dir):
    state = fixtures.partial_state()
    state["report_status"] = "degraded"  # node marks this before rendering
    state = _run(state, out_dir)
    assert state["report_status"] == "degraded"
    with open(state["report_path"], encoding="utf-8") as fh:
        html = fh.read()
    assert "Degraded report" in html


def test_failed_upstream_still_produces_report(out_dir):
    state = _run(_with_insights(fixtures.failed_state()), out_dir)
    assert os.path.exists(state["report_path"])
    with open(state["report_path"], encoding="utf-8") as fh:
        html = fh.read()
    assert "Error Log" in html
    assert "sklearn" in html
    assert state["report_status"] in ("degraded", "failed")


def test_pdf_fallback_when_weasyprint_fails(out_dir, monkeypatch):
    state = fixtures.healthy_state()
    monkeypatch.setattr(
        report_generator, "_render_pdf",
        lambda *a, **k: None,
    )
    state = _run(state, out_dir)
    # HTML still delivered, PDF absent.
    assert os.path.exists(state["report_path"])
    assert state["pdf_path"] is None


def test_write_report_never_raises(out_dir, monkeypatch):
    monkeypatch.setattr(
        report_generator, "_render_pdf",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        report_generator, "render_html",
        lambda **k: (_ for _ in ()).throw(ValueError("template broke")),
    )
    state = _run(fixtures.healthy_state(), out_dir)
    assert "could not render HTML report" in "\n".join(state["error_log"])
    assert state["report_status"] == "failed"
