# tools/python_executor.py

import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from typing import List, Optional

EXECUTION_TIMEOUT = int(os.getenv("EXECUTION_TIMEOUT", "30"))  # seconds
MAX_OUTPUT_BYTES = 100_000
# Hard resource limits for the child process (POSIX only). CPU and memory are
# configured independently: a tight CPU cap (default = wall timeout) prevents
# runaway loops; memory cap (default 1.5 GB) bounds pandas/matplotlib peaks.
_CPU_LIMIT_S = int(os.getenv("EXEC_CPU_LIMIT_S", str(EXECUTION_TIMEOUT)))
_MEM_LIMIT_MB = int(os.getenv("EXEC_MEM_LIMIT_MB", "1536"))

BASE_SANDBOX_HEADER = """
import pandas as pd
import numpy as np
import itertools
import json
import sys
import traceback
import os
"""

PLOT_SANDBOX_HEADER = """
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
"""

SANDBOX_BODY = """
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
    """Two-layer sanitizer for LLM-generated analysis snippets.

    Layer 1 (AST, authoritative): refuses any call into a banned builtin
    (``exec``, ``eval``, ``compile``, ``__import__``, ``breakpoint``) or a
    banned module (``os``, ``subprocess``, ``shutil``, ``ctypes``, ``socket``).
    This is the security gate — a clever prompt like
    ``__import__('os').system('...')`` or
    ``getattr(__builtins__, 'eval')('...')`` is rejected at parse time, not
    merely silently stripped.

    Layer 2 (regex, cosmetic): line-strips the most common LLM hallucination
    patterns (``df = pd.read_csv(...)`` shadowing the injected df, ``open(...)``
    with arbitrary paths, ``import os`` at the top of the snippet, etc.). This
    is purely for cleanliness so the child subprocess doesn't get noisy stderr
    from redundant code; it is NOT a security boundary.

    The function returns the sanitized source when safe, raises
    ``SecurityError`` when the AST detects a banned construct, and returns
    the source unchanged (after regex stripping) when the code has a syntax
    error — so the child subprocess can still surface the real Python error
    instead of us hiding it.
    """
    # Layer 1: AST gate (runs on the ORIGINAL source so strip-then-AST can't
    # hide things the AST should see).
    try:
        import ast as _ast
        tree = _ast.parse(code)
    except SyntaxError:
        return _line_strip(code)

    blocked_builtins = {"exec", "eval", "compile", "__import__", "breakpoint",
                        "getattr", "setattr", "delattr", "globals", "locals",
                        "vars", "open"}
    # Calls whose leaf attribute name matches one of these are forbidden when
    # the chain starts from a blocked module. We match on the LEAF (last
    # attribute) instead of the root so that ``os.path.basename`` (legitimate)
    # still works while ``os.system`` (dangerous) is blocked.
    blocked_module_calls = {
        "os": {"system", "popen", "exec", "execv", "execve", "spawn", "kill",
               "remove", "unlink", "rmdir", "removedirs", "rename", "chmod",
               "chown", "truncate", "putenv", "environ", "fork", "setuid"},
        "subprocess": {"run", "Popen", "call", "check_call", "check_output",
                       "getoutput", "getstatusoutput"},
        "shutil": {"rmtree", "move", "copy", "copytree", "disk_usage"},
        "ctypes": {"CDLL", "WinDLL", "PyDLL", "addressof", "cast"},
        "socket": {"socket", "create_connection", "gethostbyname"},
    }

    def _attr_chain(node: _ast.AST) -> Optional[List[str]]:
        """Return the dotted attribute chain of ``node`` as a list, or None
        if the call target isn't a static ``Name.attr1.attr2...`` chain."""
        names: List[str] = []
        cur = node
        while isinstance(cur, _ast.Attribute):
            names.append(cur.attr)
            cur = cur.value
        if isinstance(cur, _ast.Name):
            names.append(cur.id)
            names.reverse()
            return names
        return None

    # Pass 1: imports — refuse ``from <banned_module> import <anything>`` so
    # ``from shutil import rmtree`` cannot reintroduce the blocked call.
    for node in _ast.walk(tree):
        if isinstance(node, _ast.ImportFrom) and node.module in blocked_module_calls:
            names = [a.name for a in node.names]
            raise SecurityError(
                f"importing from module '{node.module}' is not allowed "
                f"(names: {names})"
            )

    # Pass 2: walk all calls and check the function target.
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Call):
            # Direct banned builtin calls (incl. getattr/setattr/eval/exec).
            if isinstance(node.func, _ast.Name) and node.func.id in blocked_builtins:
                raise SecurityError(
                    f"call to built-in '{node.func.id}'() is not allowed"
                )
            # Attribute chain into a banned module.
            chain = _attr_chain(node.func)
            if chain and len(chain) >= 2 and chain[0] in blocked_module_calls:
                leaf = chain[-1]
                if leaf in blocked_module_calls[chain[0]]:
                    raise SecurityError(
                        f"calls into module '{chain[0]}' are not allowed "
                        f"(e.g. {chain[0]}.{leaf})"
                    )
        elif isinstance(node, _ast.Subscript):
            # ``os.environ['X'] = 'y'`` is a mutating attribute access via
            # __setitem__. Block any subscript whose value chain starts at
            # a banned module + blocked leaf.
            chain = _attr_chain(node.value)
            if chain and len(chain) >= 2 and chain[0] in blocked_module_calls:
                leaf = chain[-1]
                if leaf in blocked_module_calls[chain[0]]:
                    raise SecurityError(
                        f"subscript on module '{chain[0]}.{leaf}' is not allowed"
                    )

    # Layer 2: cosmetic regex strip after we've already authorized the source.
    return _line_strip(code)


def _line_strip(code: str) -> str:
    bad_patterns = [
        r"^\s*df\s*=\s*pd\.read_csv\(",
        r"^\s*data\s*=\s*pd\.read_csv\(",
        r"^\s*df\s*=\s*pd\.read_excel\(",
        r"^\s*with\s+open\(",
        r"^\s*os\.system\(",
        r"^\s*os\.popen\(",
        r"^\s*subprocess\s*\.\s*(run|Popen|call)\(",
        r"^\s*import\s+os\s*$",
        r"^\s*import\s+subprocess",
        r"\beval\(",
        r"\bexec\(",
    ]
    sanitized: List[str] = []
    for line in code.splitlines():
        if any(re.match(p, line) for p in bad_patterns):
            continue
        sanitized.append(line)
    return "\n".join(sanitized)


class SecurityError(RuntimeError):
    """Raised when generated code attempts an operation the sandbox forbids."""


def _rlimits():
    """Set CPU + address-space rlimits for the child before exec (POSIX).

    Sets RLIMIT_CPU to ``_CPU_LIMIT_S`` (seconds of CPU time; default mirrors
    the wall-clock timeout so a tight loop gets killed, not just throttled)
    and RLIMIT_AS to ``_MEM_LIMIT_MB`` bytes of address space so a misbehaving
    allocation fails fast instead of swapping the host.

    Silently no-ops on platforms where ``resource`` is unavailable (e.g.
    Windows); the subprocess still gets the wall-clock timeout via
    ``subprocess.run(timeout=...)``.
    """
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
        # Some platforms expose RLIMIT_CPU as (soft, hard) with hard == RLIM_INFINITY;
        # bound by the smaller of the env-derived cap and the existing hard limit.
        cap = min(_CPU_LIMIT_S, hard) if hard else _CPU_LIMIT_S
        resource.setrlimit(resource.RLIMIT_CPU, (cap, hard))
    except (ImportError, OSError, ValueError):
        pass
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        limit = _MEM_LIMIT_MB * 1024 * 1024
        if soft:
            target = min(soft, limit)
        else:
            target = limit
        if hard:
            target = min(target, hard)
        resource.setrlimit(resource.RLIMIT_AS, (target, hard or target))
    except (ImportError, OSError, ValueError):
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
    try:
        code = _sanitize_generated_code(code)
    except SecurityError as exc:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "generated_files": [],
            "stats": {},
            "error": f"security policy violation: {exc}",
        }

    # Build the full sandbox script (only import matplotlib/seaborn when needed)
    needs_plot = any(kw in code for kw in ("plt", "sns", "matplotlib", "seaborn"))
    header = BASE_SANDBOX_HEADER + (PLOT_SANDBOX_HEADER if needs_plot else "")
    full_script = (header + SANDBOX_BODY).format(
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
