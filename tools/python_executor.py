# tools/python_executor.py

import subprocess
import os
import sys
import uuid
import tempfile

EXECUTION_TIMEOUT = 30  # seconds
MAX_OUTPUT_BYTES = 100_000

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

# Load the data
df = pd.read_csv('{csv_path}')

# Ensure output directory exists
import os
os.makedirs('output/analysis', exist_ok=True)

# User code starts here
{user_code}
"""

def _sanitize_generated_code(code: str) -> str:
    """
    Strip lines that load a file via pd.read_csv / open() since df is already
    injected by the sandbox template.  Catches common LLM hallucination patterns.
    """
    import re
    bad_patterns = [
        r"^\s*df\s*=\s*pd\.read_csv\(",
        r"^\s*data\s*=\s*pd\.read_csv\(",
        r"^\s*df\s*=\s*pd\.read_excel\(",
        r"^\s*with\s+open\(",
    ]
    sanitized = []
    skip_block = False
    for line in code.splitlines():
        # Skip the try/except block wrapping a read_csv if the pattern spans lines
        if any(re.match(p, line) for p in bad_patterns):
            continue
        sanitized.append(line)
    return "\n".join(sanitized)


def execute_code(code: str, csv_path: str) -> dict:

    """
    Executes Python code in a subprocess sandbox.
    
    Args:
        code: Python code string to execute (uses 'df' variable)
        csv_path: Path to CSV file to load as df
    
    Returns:
        dict with keys: success (bool), stdout (str), stderr (str), 
                        generated_files (list), error (str or None)
    """
    # Generate unique script file to avoid conflicts, and use OS temp directory (works on Windows)
    script_id = str(uuid.uuid4())[:8]
    temp_dir = tempfile.gettempdir()
    script_path = os.path.join(temp_dir, f"analysis_script_{script_id}.py")
    
    # Sanitize: strip any pd.read_csv() calls the LLM may have hallucinated
    code = _sanitize_generated_code(code)

    # Build the full sandbox script
    full_script = SANDBOX_TEMPLATE.format(

        csv_path=os.path.abspath(csv_path).replace('\\', '\\\\'),
        user_code=code
    )
    
    # Write script to temp file
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(full_script)
    
    # Track files before execution to find newly created ones
    analysis_dir = 'output/analysis'
    before_files = set()
    if os.path.exists(analysis_dir):
        before_files = {os.path.abspath(os.path.join(analysis_dir, f)) for f in os.listdir(analysis_dir)}
    
    try:
        # Execute in subprocess (reuse the current interpreter so deps resolve)
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=EXECUTION_TIMEOUT,
            cwd=os.getcwd()  # Run from project root so output/analysis/ works
        )
        
        stdout = result.stdout[:MAX_OUTPUT_BYTES]
        stderr = result.stderr[:MAX_OUTPUT_BYTES]
        
        # Check for new files generated in output/analysis/
        generated_files = []
        if os.path.exists(analysis_dir):
            for f in os.listdir(analysis_dir):
                fpath = os.path.abspath(os.path.join(analysis_dir, f))
                if os.path.isfile(fpath) and fpath not in before_files:
                    # Convert path to relative or absolute as needed, keep standard slashes
                    rel_path = os.path.relpath(fpath, os.getcwd()).replace('\\', '/')
                    generated_files.append(rel_path)
        
        success = result.returncode == 0 and not stderr.strip()
        
        return {
            "success": success,
            "stdout": stdout,
            "stderr": stderr,
            "generated_files": generated_files,
            "error": stderr if not success else None
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "generated_files": [],
            "error": f"Execution timed out after {EXECUTION_TIMEOUT} seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "generated_files": [],
            "error": str(e)
        }
    finally:
        # Cleanup temp script
        if os.path.exists(script_path):
            try:
                os.remove(script_path)
            except Exception:
                pass
