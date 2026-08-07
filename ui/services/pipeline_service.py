"""Pipeline service layer: abstracts graph pipeline execution, upload sanitization, and caching for Streamlit UI."""

import os
import uuid
import json
import logging
from typing import Dict, Any, Optional

from state import build_state
from graph import create_pipeline

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.abspath("uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks."""
    basename = os.path.basename(filename)
    safe_chars = [c for c in basename if c.isalnum() or c in (".", "_", "-")]
    return "".join(safe_chars) if safe_chars else "upload.csv"


def save_uploaded_csv(uploaded_file, max_size_mb: float = 50.0) -> str:
    """Save Streamlit UploadedFile securely with UUID prefix.

    Raises ValueError if invalid file type or exceeds size limit.
    """
    if not uploaded_file.name.lower().endswith(".csv"):
        raise ValueError(f"Invalid file type: '{uploaded_file.name}'. Only CSV files are accepted.")

    contents = uploaded_file.getvalue()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"File size ({size_mb:.1f} MB) exceeds maximum allowed limit of {max_size_mb:.0f} MB.")

    safe_name = sanitize_filename(uploaded_file.name)
    unique_id = uuid.uuid4().hex[:8]
    dest_path = os.path.join(UPLOAD_DIR, f"{unique_id}_{safe_name}")

    with open(dest_path, "wb") as f:
        f.write(contents)

    logger.info("Saved secure upload to %s", dest_path)
    return os.path.abspath(dest_path)


def run_pipeline(csv_path: str) -> Dict[str, Any]:
    """Run the multi-agent pipeline on a target CSV path and return final AgentState dict."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset file not found: {csv_path}")

    pipeline = create_pipeline()
    initial_state = build_state(
        csv_path=os.path.abspath(csv_path),
        status="running",
    )

    logger.info("Starting pipeline execution for %s", csv_path)
    final_state = pipeline(initial_state)
    logger.info("Pipeline execution finished with report status: %s", final_state.get("report_status"))
    return final_state


def read_html_report(report_path: Optional[str]) -> Optional[str]:
    """Safely read HTML report content if file exists."""
    if not report_path or not os.path.exists(report_path):
        return None
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as exc:
        logger.error("Failed to read HTML report at %s: %s", report_path, exc)
        return None


def get_available_samples() -> Dict[str, str]:
    """Return dictionary of sample datasets {display_name: filepath}."""
    samples = {}
    sales_path = os.path.abspath("data/sample_sales.csv")
    if os.path.exists(sales_path):
        samples["Sample Sales Dataset (30 rows, 10 columns)"] = sales_path

    mock_path = os.path.abspath("mocks/mock_data.csv")
    if os.path.exists(mock_path):
        samples["Mock Employee Dataset"] = mock_path

    return samples
