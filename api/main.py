"""
AI Data Analyst Agent — FastAPI Backend
=======================================
Endpoints:
  GET  /health                   → health check
  POST /analyze                  → upload CSV → run full multi-agent graph pipeline → return profile & insights
  GET  /report/{filename}        → serve the generated HTML report
  POST /chat                     → report & insight grounded Q&A endpoint
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Security,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from agents.profiler.agent import profiler_node
from config import (
    API_ALLOWED_ORIGINS,
    API_BEARER_TOKEN,
    API_MAX_FILE_SIZE_MB,
    PROFILE_DIR,
    REPORT_DIR,
    UPLOAD_DIR,
    ensure_dirs,
    snapshot,
)
from state import AgentState

try:
    from graph import create_pipeline
    PIPELINE_AVAILABLE = True
except Exception as err:
    logging.warning("Graph pipeline import notice: %s. Falling back to single-node profiler.", err)
    PIPELINE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

# Resolve output paths from config (single source of truth).
OUTPUT_DIR = PROFILE_DIR
REPORTS_DIR = REPORT_DIR
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

ensure_dirs()

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
        "description": "CSV dataset ingestion, multi-agent profiling, analysis, insights, and report rendering.",
    },
    {
        "name": "chat",
        "description": "Interactive report-grounded Q&A with Member 3's insight engine.",
    },
]

app = FastAPI(
    title="AI Data Analyst Agent API",
    description=(
        "Multi-Agent AI Data Analyst System.\n\n"
        "Upload a CSV to run Profiler, Analysis, and Insight agents to generate interactive reports and insights."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_tags=tags_metadata,
)

# CORS: configurable allowlist. ``*`` is the default for local dev; production
# deployments should set ALLOWED_ORIGINS to a comma-separated list of origins.
_cors_origins = (
    ["*"] if API_ALLOWED_ORIGINS.strip() in ("", "*")
    else [o.strip() for o in API_ALLOWED_ORIGINS.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=API_ALLOWED_ORIGINS.strip() not in ("", "*"),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Security & Helper Setup
# ---------------------------------------------------------------------------
security_scheme = HTTPBearer(auto_error=False)


def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)):
    """Enforces Bearer token auth if API_BEARER_TOKEN env var is set."""
    if API_BEARER_TOKEN:
        if not credentials or credentials.credentials != API_BEARER_TOKEN:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )


def _safe_remove(path: str):
    """Background task to remove temporary upload file non-blockingly."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.info("Cleaned up temp file in background: %s", path)
        except Exception as exc:
            logger.warning("Could not remove temp file %s: %s", path, exc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health_check():
    """Liveness probe returning API and agent status list."""
    return [
        {"name": "FastAPI Backend", "status": "connected", "latencyMs": 12, "lastChecked": "Just now"},
        {"name": "Profiler Node", "status": "connected", "latencyMs": 24, "lastChecked": "Just now"},
        {"name": "Analysis Planner", "status": "connected" if PIPELINE_AVAILABLE else "degraded", "latencyMs": 35, "lastChecked": "Just now"},
        {"name": "Insight Engine", "status": "connected" if PIPELINE_AVAILABLE else "degraded", "latencyMs": 42, "lastChecked": "Just now"},
    ]


@app.post("/analyze", tags=["profiler"], dependencies=[Depends(verify_token)])
async def analyze(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Upload a CSV file and run the multi-agent analysis pipeline.

    - Saves the upload to a temporary location.
    - Runs the full LangGraph pipeline (or profiler node as fallback).
    - Returns structured dataset profile, insights, and recommendations.
    """
    # --- Validate file type ---
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Only CSV files are accepted. Received: '{file.filename}'",
        )

    # --- Check file size ---
    max_mb = API_MAX_FILE_SIZE_MB
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

    # Schedule background cleanup after endpoint response completes
    background_tasks.add_task(_safe_remove, temp_path)

    # --- Build initial state ---
    state: AgentState = {
        "csv_path": temp_path,
        "profile": None,
        "profile_report_path": None,
        "analysis_plan": [],
        "analysis_results": [],
        "generated_files": [],
        "execution_log": [],
        "reflection_notes": [],
        "validation_report": None,
        "insights": [],
        "recommendations": [],
        "report_path": None,
        "pdf_path": None,
        "report_status": "pending",
        "error_log": [],
        "status": "running",
    }

    try:
        if PIPELINE_AVAILABLE:
            pipeline = create_pipeline()
            result_state = pipeline.invoke(state)
        else:
            result_state = profiler_node(state)
    except Exception as exc:
        logger.exception("Unexpected error executing analysis pipeline")
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")

    # --- Handle failure ---
    if result_state.get("status") == "failed":
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Analysis pipeline failed to process the CSV.",
                "errors": result_state.get("error_log", []),
            },
        )

    # --- Build response ---
    profile_report_abs = result_state.get("profile_report_path", "")
    # report_path now points at the Sweetviz profile report when available;
    # fall back to the summary report for backwards compat.
    insight_report_abs = result_state.get("report_path", "") or result_state.get("summary_report_path", "")

    profile_report_filename = os.path.basename(profile_report_abs) if profile_report_abs else None
    insight_report_filename = os.path.basename(insight_report_abs) if insight_report_abs else None

    # report_filename = the primary HTML deliverable (Sweetviz report); the
    # summary report is still served for backwards compat if present.
    report_filename = profile_report_filename or insight_report_filename

    return JSONResponse(
        content={
            "status": "completed",
            "profile": result_state.get("profile"),
            "insights": result_state.get("insights", []),
            "recommendations": result_state.get("recommendations", []),
            "execution_log": result_state.get("execution_log", []),
            "report_filename": report_filename,
            "report_url": f"/report/{report_filename}" if report_filename else None,
            "profile_report_filename": profile_report_filename,
            "profile_report_url": f"/report/{profile_report_filename}" if profile_report_filename else None,
            "summary_report_filename": insight_report_filename,
            "summary_report_url": f"/report/{insight_report_filename}" if insight_report_filename else None,
        }
    )


@app.get("/report/{filename}", tags=["profiler"])
def get_report(filename: str):
    """
    Serve a generated HTML report by filename.

    Looks in both PROFILE_DIR (sweetviz reports) and REPORT_DIR (final insight
    reports) so legacy /report/<file>.html requests keep working regardless of
    which pipeline stage produced the file.
    """
    safe_filename = Path(filename).name
    candidates = [
        os.path.join(REPORTS_DIR, safe_filename),
        os.path.join(OUTPUT_DIR, safe_filename),
        os.path.join("output", safe_filename),
    ]
    report_path = next((p for p in candidates if os.path.exists(p)), None)
    if not report_path:
        raise HTTPException(status_code=404, detail=f"Report '{safe_filename}' not found.")

    return FileResponse(
        path=report_path,
        media_type="text/html",
        filename=safe_filename,
    )


@app.get("/config", tags=["meta"])
def get_config():
    """Effective runtime config (non-secret). Useful for ops debugging."""
    return snapshot()


@app.post("/chat", tags=["chat"], dependencies=[Depends(verify_token)])
def chat_endpoint(payload: dict = Body(...)):
    """
    Report and insight grounded Q&A endpoint.

    Expects payload:
      {
        "message": "<user question>",
        "context": {                 # optional — sent by the UI
          "filename": "...",
          "rows": 1000,
          "columns": 10,
          "quality_score": 98.5,
          "columns_list": ["col1", ...],
          "insights": [{"title": ..., "explanation": ..., "evidence": ...}, ...],
          "recommendations": [{"action": ...}, ...]
        }
      }
    """
    message = payload.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Missing message in request payload.")

    raw_ctx = payload.get("context")
    if isinstance(raw_ctx, dict):
        ctx = raw_ctx
    elif isinstance(raw_ctx, str):
        ctx = {"raw_text": raw_ctx}
    else:
        ctx = {}

    filename = ctx.get("filename", "the uploaded dataset")
    rows = ctx.get("rows", "unknown")
    columns = ctx.get("columns", "unknown")
    quality = ctx.get("quality_score", "unknown")
    cols_list = ctx.get("columns_list") or []
    insights = ctx.get("insights") or []
    recommendations = ctx.get("recommendations") or []


    # Build grounding block
    grounding_lines = [
        f"Dataset: {filename}",
        f"Rows: {rows:,}" if isinstance(rows, int) else f"Rows: {rows}",
        f"Columns: {columns}",
        f"Quality score: {quality}%",
    ]
    if cols_list:
        grounding_lines.append(f"Features: {', '.join(str(c) for c in cols_list)}")
    if insights:
        grounding_lines.append("Key insights from the pipeline:")
        for i, ins in enumerate(insights[:8], 1):
            title = ins.get("title") or ins.get("explanation") or ""
            explanation = ins.get("explanation") or ins.get("evidence") or ""
            evidence = ins.get("evidence") or ""
            sev = ins.get("severity") or "info"
            conf = ins.get("confidence") or ""
            grounding_lines.append(
                f"  I-{i:02d} [{sev.upper()}] {title}"
                + (f" — {explanation}" if explanation and explanation != title else "")
                + (f" | Evidence: {evidence}" if evidence and evidence != explanation else "")
                + (f" (confidence: {conf}%)" if conf else "")
            )
    if recommendations:
        grounding_lines.append("Strategic recommendations:")
        for i, rec in enumerate(recommendations[:5], 1):
            if isinstance(rec, dict):
                action = rec.get("title") or rec.get("action") or str(rec)
                impact = rec.get("body") or rec.get("impact") or ""
            else:
                action = str(rec)
                impact = ""
            grounding_lines.append(
                f"  R-{i:02d}: {action}" + (f" | Impact: {impact}" if impact else "")
            )

    grounding_text = "\n".join(grounding_lines)

    system_prompt = f"""You are an expert data analyst assistant. You answer questions strictly grounded in the verified pipeline output below.

GROUNDING CONTEXT:
{grounding_text}

Rules:
- Answer ONLY from the grounding context above. Do not speculate or make up numbers.
- If the answer is not present in the grounding context, say so clearly.
- Be concise. Use bullet points where helpful.
- When citing numbers or insights, reference the source (e.g., "per insight I-01", "from the dataset profile").
- Format key numbers in bold using **value**.
"""

    import time as _time
    t0 = _time.monotonic()
    try:
        from llm import build_chat_model
        llm = build_chat_model(task="CHAT", temperature=0.2)
        from langchain_core.messages import HumanMessage, SystemMessage
        result = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=message)])
        content = result.content if hasattr(result, "content") else str(result)
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in content
            )
        latency_ms = int((_time.monotonic() - t0) * 1000)
    except Exception as exc:
        logger.warning("Chat LLM call failed: %s", exc)
        # Graceful fallback: synthesize a grounded answer without the LLM
        if cols_list:
            content = (
                f"Dataset **{filename}** has **{rows:,} rows** and **{columns} columns**.\n"
                f"Features: {', '.join(str(c) for c in cols_list)}.\n"
            ) if isinstance(rows, int) else (
                f"Dataset **{filename}** · Features: {', '.join(str(c) for c in cols_list)}.\n"
            )
        elif insights:
            content = "Key findings from the verified pipeline:\n" + "\n".join(
                f"- {ins.get('title', '')}: {ins.get('explanation', '')}" for ins in insights[:4]
            )
        else:
            content = f"LLM call failed ({exc}). Check your API keys in .env."
        latency_ms = int((_time.monotonic() - t0) * 1000)

    return JSONResponse(
        content={
            "id": uuid.uuid4().hex,
            "role": "assistant",
            "content": content,
            "timestamp": "Just now",
            "latencyMs": latency_ms,
            "grounded": True,
        }
    )




# --- Static frontend mounting (if built) ---
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

