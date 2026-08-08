"""HTML (Jinja2) + PDF (weasyprint) report compiler.

Resilience design (Member 3 devil's-advocate review):
  * Chart images are only rendered if the file exists and has an allowed
    extension, embedded as base64 data URIs so the report works offline and
    survives HTML -> PDF conversion.
  * Zero charts hides the section entirely; partial sets render only the
    files that exist. A broken <img> is impossible.
  * PDF generation degrades gracefully: if weasyprint fails at runtime the
    HTML is still delivered and ``pdf_path`` stays None with an error note.
"""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agents.insight.validation import validate_results

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".svg"}

_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def _image_mime(ext: str) -> str:
    return {"svg": "image/svg+xml"}.get(ext[1:], f"image/{ext[1:]}").lower()


def _valid_image(path: str) -> bool:
    if not path or not os.path.isfile(path):
        return False
    return os.path.splitext(path)[1].lower() in ALLOWED_IMAGE_EXT


def collect_charts(generated_files: List[str]) -> List[Dict[str, Any]]:
    """Base64-encode only the image files that actually exist."""
    charts: List[Dict[str, Any]] = []
    for path in generated_files or []:
        if not _valid_image(path):
            continue
        ext = os.path.splitext(path)[1].lower()
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        charts.append(
            {
                "caption": os.path.basename(path),
                "format": _image_mime(ext),
                "data_uri": b64,
            }
        )
    return charts


def render_html(
    title: str,
    csv_path: str,
    profile: Dict[str, Any],
    validation: Dict[str, Any],
    insights: List[Dict[str, Any]],
    recommendations: List[Dict[str, Any]],
    contradictions: List[Dict[str, Any]],
    charts: List[Dict[str, Any]],
    execution_log: List[Dict[str, Any]],
    error_log: List[str],
    report_status: str,
    status: str,
    generated_at: str,
    pdf_generated: bool = False,
) -> str:
    tpl = _env.get_template("report_template.html")
    return tpl.render(
        title=title,
        csv_path=csv_path,
        profile=profile or {},
        validation=validation or {},
        insights=insights or [],
        recommendations=recommendations or [],
        contradictions=contradictions or [],
        charts=charts or [],
        execution_log=execution_log or [],
        error_log=error_log or [],
        report_status=report_status,
        status=status,
        generated_at=generated_at,
        pdf_generated=pdf_generated,
    )


def write_report(state: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """Compile HTML + PDF from the pipeline state. Never raises.

    Returns a dict with ``report_path``, ``pdf_path``, ``report_status`` and
    ``error_log`` additions (already merged into ``state`` by the caller).
    """
    errors: List[str] = []

    profile = dict(state.get("profile") or {})
    if not isinstance(profile.get("columns"), dict):
        profile["columns_count"] = profile.get("columns_count") or (profile.get("columns") if isinstance(profile.get("columns"), (int, float)) else 0)
        profile["columns"] = {}

    insights = state.get("insights") or []
    recommendations = state.get("recommendations") or []
    contradictions = state.get("contradictions") or []
    validation = state.get("validation_report") or {}


    # Re-run the deterministic validation so the report always reflects the
    # latest results even if the node-level validation was skipped.
    if not validation:
        validation = validate_results(profile, state.get("analysis_results") or [])
        state["validation_report"] = validation

    report_status = state.get("report_status", "ok")
    if validation.get("errors"):
        report_status = "degraded"
    elif state.get("status") == "failed" and report_status == "ok":
        report_status = "degraded"

    charts = collect_charts(state.get("generated_files") or [])
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    os.makedirs(output_dir, exist_ok=True)
    safe_name = os.path.splitext(os.path.basename(state.get("csv_path") or "report"))[0] or "report"
    html_path = os.path.join(output_dir, f"{safe_name}_report.html")

    try:
        html = render_html(
            title=f"Data Analysis Report — {safe_name}",
            csv_path=state.get("csv_path") or "",
            profile=profile,
            validation=validation,
            insights=insights,
            recommendations=recommendations,
            contradictions=contradictions,
            charts=charts,
            execution_log=state.get("execution_log") or [],
            error_log=state.get("error_log") or [],
            report_status=report_status,
            status=state.get("status") or "in_progress",
            generated_at=generated_at,
        )
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(html)
    except OSError as exc:
        errors.append(f"could not write HTML report: {exc}")
    except Exception as exc:  # noqa: BLE001 - graceful degradation
        errors.append(f"could not render HTML report: {exc}")

    pdf_path = None
    if "could not render HTML report" not in "\n".join(errors):
        try:
            pdf_path = _render_pdf(html, output_dir, safe_name)
        except Exception:
            pdf_path = None

    state["report_path"] = html_path
    state["pdf_path"] = pdf_path
    state["report_status"] = report_status
    state["error_log"] = (state.get("error_log") or []) + errors

    if errors:
        state["report_status"] = "degraded"
    if "could not render HTML report" in "\n".join(errors):
        state["report_status"] = "failed"

    return state


def _render_pdf(html: str, output_dir: str, safe_name: str) -> Optional[str]:
    """HTML -> PDF via weasyprint; returns path or None on failure."""
    try:
        from weasyprint import HTML  # imported lazily
        pdf_path = os.path.join(output_dir, f"{safe_name}_report.pdf")
        HTML(string=html, base_url=output_dir).write_pdf(pdf_path)
        return pdf_path if os.path.exists(pdf_path) else None
    except Exception:
        # Return None gracefully if native dependencies (libpango/GTK) are missing
        return None
