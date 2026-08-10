# tools/python_executor.py

import os
import re
import sys
import json
import uuid
import subprocess
import tempfile

EXECUTION_TIMEOUT = int(os.getenv("EXECUTION_TIMEOUT", "30"))  # seconds
MAX_OUTPUT_BYTES = 100_000
# Hard resource limits for the child process (POSIX only).
_CPU_LIMIT_S = int(os.getenv("EXEC_CPU_LIMIT_S", str(EXECUTION_TIMEOUT)))  # wall CPU
_MEM_LIMIT_MB = int(os.getenv("EXEC_MEM_LIMIT_MB", "1536"))  # soft address space

SANDBOX_TEMPLATE = """
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import json
import sys
import traceback
import os

os.makedirs('output/analysis', exist_ok=True)

# Load the data
df = pd.read_csv('{csv_path}')

# Capture analysis metrics (dict of scalar -> float/int), optional
_ai_cap = globals().get('RESULT_JSON', {{}})

# User code starts here
{code}

# ---- structured-result capture (executor protocol) --------------------
_captured = {{}}
try:
    _cand = globals().get('RESULT_JSON', None)
    if isinstance(_cand, dict):
        _captured = _cand
except Exception:
    _captured = {{}}
print("__AI_RESULT__:" + json.dumps(_captured, default=str))
"""


def _sanitize_generated_code(code: str) -> str:
    """
    Strip lines that load a file via pd.read_csv / open() since df is already
    injected by the sandbox template.  Catches common LLM hallucination patterns.
    Also strip obvious shell/process escapeladders (os.system, subprocess, etc.)
    """
    bad_patterns = [
        r"^\s*df\s*=\s*pd\.read_csv\(",
        r"^\s*data\s*=\s*pd\.read_csv\(",
        r"^\s*df\s*=\s*pd\.read_excel\(",
        r"^\s*with\s+open\(",
        r"^\s*os\.system\(",
        r"^\s*os\.popen\(",
        r"^\s*subprocess\s*\.\s*(run|Popen|call)\(",
        r"^\s*import\s+os",
        r"^\s*import\s+subprocess",
        r"\beval\(",
        r"\bexec\(",
    ]
    sanitized = []
    for line in code.splitlines():
        if any(re.match(p, line) for p in bad_patterns):
            continue
        sanitized.append(line)
    return "\n".join(sanitized)


def _rlimits():
    """Set CPU + address-space rlimits for the child before exec (POSIX)."""
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (_MEM_LIMIT_MB, _MEM_LIMIT_MB))
    except Exception:
        pass
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        limit = _MEM_LIMIT_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (min(soft, limit) if soft else limit,
                                                 hard or limit))
    except Exception:
        pass


def _parse_stats(stdout: str):
    """Extract the ``__AI_RESULT__:`` payload from child stdout."""
    stats: dict = {}
    for line in stdout.splitlines():
        if line.startswith("__AI_RESULT__:"):
            raw = line[len("__AI_RESULT__:"):]
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    stats = data
            except json.JSONDecodeError:
                continue
    # coerce numpy scalars to native python for safe json/serialization
    return {k: float(v) if isinstance(v, (int, float)) else v for k, v in stats.items()}


def execute_code(code: str, csv_path: str) -> dict:
    """
    Executes Python code in a subprocess sandbox.

    Args:
        code: Python code string to execute (uses 'df' variable)
        csv_path: Path to CSV file to load as df

    Returns:
        dict with keys: success (bool), stdout (str), stderr (str),
                        generated_files (list), error (str or None),
                        stats (dict parsed from __AI_RESULT__ protocol)
    """
    # Generate unique script file to avoid conflicts, and use OS temp directory
    script_id = str(uuid.uuid4())[:8]
    temp_dir = tempfile.gettempdir()
    script_path = os.path.join(temp_dir, f"analysis_script_{script_id}.py")

    # Sanitize: strip pd.read_csv(), os/subprocess escapes the LLM hallucinated
    code = _sanitize_generated_code(code)

    # Build the full sandbox script
    full_script = SANDBOX_TEMPLATE.format(
        csv_path=os.path.abspath(csv_path).replace('\\', '\\\\'),
        code=code,
    )

    # Write script to temp file
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(full_script)

    # Track files before execution to find newly created ones
    analysis_dir = "output/analysis"
    before_files = set()
    if os.path.exists(analysis_dir):
        before_files = {os.path.abspath(os.path.join(analysis_dir, f)) for f in os.listdir(analysis_dir)}

    # Restricted environment for the child: strip ambient secrets etc.
    clean_env = {
        k: v for k, v in os.environ.items()
        if not k.startswith(("OPENAI_", "GROQ_", "GEMINI_", "GOOGLE_", "NVIDIA_", "NVAPI", "NIM_"))
    }
    clean_env.setdefault("TMPDIR", tempfile.gettempdir())

    run_kwargs: dict = {
        "capture_output": True,
        "text": True,
        "timeout": EXECUTION_TIMEOUT,
        "cwd": os.getcwd(),  # project root so output/analysis/ works
        "env": clean_env,
    }
    if os.name != "nt":
        run_kwargs["preexec_fn"] = _rlimits

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            **run_kwargs
        )

        stdout = result.stdout[:MAX_OUTPUT_BYTES]
        stderr = result.stderr[:MAX_OUTPUT_BYTES]

        generated_files = []
        if os.path.exists(analysis_dir):
            for f in os.listdir(analysis_dir):
                fpath = os.path.abspath(os.path.join(analysis_dir, f))
                if os.path.isfile(fpath) and fpath not in before_files:
                    rel_path = os.path.relpath(fpath, os.getcwd()).replace("\\", "/")
                    generated_files.append(rel_path)

        success = result.returncode == 0
        stats = _parse_stats(stdout)

        return {
            "success": success,
            "stdout": stdout,
            "stderr": stderr,
            "generated_files": generated_files,
            "stats": stats,
            "error": stderr if not success else None,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "generated_files": [],
            "stats": {},
            "error": f"Execution timed out after {EXECUTION_TIMEOUT} seconds",
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "generated_files": [],
            "stats": {},
            "error": str(e),
        }
    finally:
        # Cleanup temp script
        if os.path.exists(script_path):
            try:
                os.remove(script_path)
            except Exception:
                pass