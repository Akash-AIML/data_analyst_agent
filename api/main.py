"""
Profiler Agent — FastAPI Backend
=================================
Endpoints:
  GET  /health                   → health check
  POST /analyze                  → upload CSV → run profiler node → return profile JSON
  GET  /report/{filename}        → serve the generated HTML report
"""

import os
import shutil
import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

from state import AgentState
from agents.profiler.agent import profiler_node


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output/profiles")
UPLOAD_DIR = "uploads"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
tags_metadata = [
    {
        "name": "meta",
        "description": "Health checks, API status, and documentation endpoints.",
    },
    {
        "name": "profiler",
        "description": "CSV dataset ingestion, LangGraph profiling node, and HTML report rendering.",
    },
]

app = FastAPI(
    title="Profiler Agent API",
    description=(
        "Member 1 — LangGraph Profiler Agent.\n\n"
        "Upload a CSV to receive a structured dataset profile and an interactive HTML report."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # restrict to your UI origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health_check():
    """Liveness probe."""
    return {"status": "ok", "service": "profiler-agent"}




@app.post("/analyze", tags=["profiler"])
async def analyze(file: UploadFile = File(...)):
    """
    Upload a CSV file and receive a structured dataset profile.

    - Saves the upload to a temporary location.
    - Runs the LangGraph `profiler_node`.
    - Returns the full profile JSON on success.
    - Returns a 422 with error details on failure.

    The HTML report can be retrieved via GET /report/{filename}.
    """
    # --- Validate file type ---
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Only CSV files are accepted. Received: '{file.filename}'",
        )

    # --- Check file size ---
    max_mb = float(os.getenv("MAX_FILE_SIZE_MB", "200"))
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > max_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {size_mb:.1f} MB (limit: {max_mb:.0f} MB).",
        )

    # --- Save upload to a unique temp path ---
    unique_id = uuid.uuid4().hex
    safe_name = f"{unique_id}_{file.filename}"
    temp_path = os.path.join(UPLOAD_DIR, safe_name)

    try:
        with open(temp_path, "wb") as f:
            f.write(contents)
        logger.info("Saved upload to %s", temp_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {exc}")
    finally:
        await file.close()

    # --- Build initial state and run profiler node ---
    state: AgentState = {
        "csv_path": temp_path,
        "profile": None,
        "profile_report_path": None,
        "error_log": [],
        "status": "running",
    }

    try:
        result_state = profiler_node(state)
    except Exception as exc:
        logger.exception("Unexpected error in profiler_node")
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")
    finally:
        # Clean up uploaded temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.info("Cleaned up temp file: %s", temp_path)

    # --- Handle failure ---
    if result_state["status"] == "failed":
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Profiler agent failed to process the CSV.",
                "errors": result_state["error_log"],
            },
        )

    # --- Build response ---
    report_abs = result_state.get("profile_report_path", "")
    report_filename = os.path.basename(report_abs) if report_abs else None

    return JSONResponse(
        content={
            "status": "completed",
            "profile": result_state["profile"],
            "report_filename": report_filename,
            "report_url": f"/report/{report_filename}" if report_filename else None,
        }
    )


@app.get("/report/{filename}", tags=["profiler"])
def get_report(filename: str):
    """
    Serve a generated ydata-profiling HTML report by filename.
    """
    # Sanitize — prevent directory traversal
    safe_filename = Path(filename).name
    report_path = os.path.join(OUTPUT_DIR, safe_filename)

    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail=f"Report '{safe_filename}' not found.")

    return FileResponse(
        path=report_path,
        media_type="text/html",
        filename=safe_filename,
    )
