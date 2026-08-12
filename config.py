"""Single source of truth for filesystem paths and tunables.

Centralizes the four output directories the pipeline writes to so we never
have to chase a hardcoded ``"output/..."`` string across modules. Also exposes
the LLM-budget, pacing, and sandbox tunables with safe defaults so tests can
monkeypatch the module-level constants without re-reading env on every call.

Usage::

    from config import OUTPUT_ROOT, REPORT_DIR, ensure_dirs
    ensure_dirs()  # idempotent
    html_path = os.path.join(REPORT_DIR, "report.html")
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------

OUTPUT_ROOT: str = os.getenv("OUTPUT_ROOT", "output")
UPLOAD_DIR: str = os.path.abspath(os.getenv("UPLOAD_DIR", "uploads"))

PROFILE_DIR: str = os.path.abspath(
    os.getenv("PROFILE_DIR", os.path.join(OUTPUT_ROOT, "profiles"))
)
ANALYSIS_DIR: str = os.path.abspath(
    os.getenv("ANALYSIS_DIR", os.path.join(OUTPUT_ROOT, "analysis"))
)
REPORT_DIR: str = os.path.abspath(
    os.getenv("REPORT_DIR", os.path.join(OUTPUT_ROOT, "reports"))
)
LLM_CACHE_PATH: str = os.path.abspath(
    os.getenv("LLM_CACHE_PATH", os.path.join(OUTPUT_ROOT, "llm_cache.json"))
)

# Re-exported legacy aliases some modules already use.
OUTPUT_DIR = PROFILE_DIR  # api/main.py uses OUTPUT_DIR for profile reports


def ensure_dirs() -> Dict[str, str]:
    """Create every output directory if missing; return their resolved paths."""
    paths = {
        "OUTPUT_ROOT": OUTPUT_ROOT,
        "UPLOAD_DIR": UPLOAD_DIR,
        "PROFILE_DIR": PROFILE_DIR,
        "ANALYSIS_DIR": ANALYSIS_DIR,
        "REPORT_DIR": REPORT_DIR,
        "LLM_CACHE_PATH": LLM_CACHE_PATH,
    }
    for name, p in paths.items():
        if name == "LLM_CACHE_PATH":
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        else:
            os.makedirs(p, exist_ok=True)
    return paths


# ---------------------------------------------------------------------------
# Tunables (LLM pacing / budget / sandbox)
# ---------------------------------------------------------------------------

LLM_BUDGET_US: float = _float("LLM_BUDGET_US", 1.0)
LLM_MIN_INTERVAL_S: float = _float("LLM_MIN_INTERVAL_S", 1.0)
LLM_BUDGET_WARN_RATIO: float = _float("LLM_BUDGET_WARN_RATIO", 0.8)
LLM_CACHE_ENABLED: bool = _bool("LLM_CACHE_ENABLED", False)
LLM_CACHE_CAP: int = _int("LLM_CACHE_CAP", 512)

# Sandbox executor tunables.
EXECUTION_TIMEOUT: int = _int("EXECUTION_TIMEOUT", 30)
EXEC_CPU_LIMIT_S: int = _int("EXEC_CPU_LIMIT_S", EXECUTION_TIMEOUT)
EXEC_MEM_LIMIT_MB: int = _int("EXEC_MEM_LIMIT_MB", 1536)

# Verify-by-recompute gate.
RECOMPUTE_TOLERANCE: float = _float("RECOMPUTE_TOLERANCE", 0.03)
RECOMPUTE_ABS_TOLERANCE: float = _float("RECOMPUTE_ABS_TOLERANCE", 1e-4)

# Profiling tunables.
PROFILE_MAX_FILE_SIZE_MB: float = _float("MAX_FILE_SIZE_MB", 50.0)
PROFILE_PAIRWISE_COL_LIMIT: int = _int("PAIRWISE_COL_LIMIT", 15)

# Reporting tunables. PDF generation is disabled by default; the HTML report
# (the Sweetviz profile report) is the primary deliverable.
ENABLE_PDF: bool = _bool("ENABLE_PDF", False)

# API tunables.
API_MAX_FILE_SIZE_MB: float = _float("MAX_FILE_SIZE_MB", 200.0)
API_ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")
API_BEARER_TOKEN: str = os.getenv("API_BEARER_TOKEN", "")


def snapshot() -> Dict[str, Any]:
    """Return a dict of every tunable; useful for /config debug endpoint."""
    return {
        "paths": {
            "OUTPUT_ROOT": OUTPUT_ROOT,
            "UPLOAD_DIR": UPLOAD_DIR,
            "PROFILE_DIR": PROFILE_DIR,
            "ANALYSIS_DIR": ANALYSIS_DIR,
            "REPORT_DIR": REPORT_DIR,
            "LLM_CACHE_PATH": LLM_CACHE_PATH,
        },
        "llm": {
            "LLM_BUDGET_US": LLM_BUDGET_US,
            "LLM_MIN_INTERVAL_S": LLM_MIN_INTERVAL_S,
            "LLM_BUDGET_WARN_RATIO": LLM_BUDGET_WARN_RATIO,
            "LLM_CACHE_ENABLED": LLM_CACHE_ENABLED,
            "LLM_CACHE_CAP": LLM_CACHE_CAP,
        },
        "sandbox": {
            "EXECUTION_TIMEOUT": EXECUTION_TIMEOUT,
            "EXEC_CPU_LIMIT_S": EXEC_CPU_LIMIT_S,
            "EXEC_MEM_LIMIT_MB": EXEC_MEM_LIMIT_MB,
        },
        "validation": {
            "RECOMPUTE_TOLERANCE": RECOMPUTE_TOLERANCE,
            "RECOMPUTE_ABS_TOLERANCE": RECOMPUTE_ABS_TOLERANCE,
        },
        "profiler": {
            "MAX_FILE_SIZE_MB": PROFILE_MAX_FILE_SIZE_MB,
            "PAIRWISE_COL_LIMIT": PROFILE_PAIRWISE_COL_LIMIT,
        },
        "reporting": {
            "ENABLE_PDF": ENABLE_PDF,
        },
        "api": {
            "MAX_FILE_SIZE_MB": API_MAX_FILE_SIZE_MB,
            "ALLOWED_ORIGINS": API_ALLOWED_ORIGINS,
            "AUTH_ENABLED": bool(API_BEARER_TOKEN),
        },
    }


__all__ = [
    "OUTPUT_ROOT", "UPLOAD_DIR", "PROFILE_DIR", "ANALYSIS_DIR", "REPORT_DIR",
    "LLM_CACHE_PATH", "OUTPUT_DIR", "ensure_dirs",
    "LLM_BUDGET_US", "LLM_MIN_INTERVAL_S", "LLM_BUDGET_WARN_RATIO",
    "LLM_CACHE_ENABLED", "LLM_CACHE_CAP",
    "EXECUTION_TIMEOUT", "EXEC_CPU_LIMIT_S", "EXEC_MEM_LIMIT_MB",
    "RECOMPUTE_TOLERANCE", "RECOMPUTE_ABS_TOLERANCE",
    "PROFILE_MAX_FILE_SIZE_MB", "PROFILE_PAIRWISE_COL_LIMIT",
    "ENABLE_PDF", "API_MAX_FILE_SIZE_MB", "API_ALLOWED_ORIGINS",
    "API_BEARER_TOKEN", "snapshot",
]

