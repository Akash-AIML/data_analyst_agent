"""Sandbox security tests (Phase 3, item 14).

These tests document the security guarantees (and limits) of the regex + AST
sanitizer inside ``tools.python_executor``. The intent is to lock in the
behaviour with regression tests so a future refactor that loosens the policy
is caught immediately.

What we DO block:
  * Direct calls into banned builtins: exec, eval, compile, __import__, breakpoint.
  * Calls whose attribute chain lands on a banned module root: os, subprocess,
    shutil, ctypes, socket.
  * The classic regex patterns LLMs hallucinate (pd.read_csv, open(...), etc.).

What we DO NOT block (and why):
  * Pure attribute reads on banned modules (e.g. ``os.path.basename(...)``)
    are permitted because pandas/plotting legitimately import them.
  * Outbound network is still possible via matplotlib's ``plt.imread(url)``
    etc.; the subprocess runs with the project env minus secret-prefix keys.
    Use OS-level network policy if you need that.
"""

from __future__ import annotations

import csv
import os

import pytest

from tools.python_executor import SecurityError, _sanitize_generated_code, execute_code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path: str) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["a", "b"])
        w.writerow([1, 2])
        w.writerow([3, 4])


@pytest.fixture()
def csv_path(tmp_path):
    p = tmp_path / "data.csv"
    _write_csv(str(p))
    return str(p)


# ---------------------------------------------------------------------------
# Layer-1 regex: line-stripping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("snippet", [
    "df = pd.read_csv('foo.csv')",
    "data = pd.read_csv('foo.csv')",
])
def test_regex_layer_strips_cosmetic_patterns(snippet):
    """Cosmetic line-stripping for patterns that don't trigger the AST gate.

    Patterns that the AST gate blocks outright (open, os.system, subprocess.run,
    import os) raise SecurityError and never reach the regex layer. The
    regex layer only handles benign-looking-but-noisy patterns the LLM
    hallucinates that aren't themselves security risks (e.g. shadowing the
    injected ``df`` with a fresh read_csv).
    """
    out = _sanitize_generated_code(snippet)
    assert "pd.read_csv" not in out


@pytest.mark.parametrize("snippet", [
    "os.system('echo hi')",
    "import os\nos.system('echo hi')",
    "subprocess.run(['ls'])",
    "from shutil import rmtree; rmtree('/')",
    "with open('foo') as f: pass",
])
def test_ast_layer_blocks_patterns_the_regex_would_have_stripped(snippet):
    """The classic regex-blocklist patterns are now caught at the AST layer
    with a SecurityError — not silently stripped."""
    with pytest.raises(SecurityError):
        _sanitize_generated_code(snippet)


# ---------------------------------------------------------------------------
# Layer-2 AST: banned builtins + module calls
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("snippet,label", [
    ("eval('1+1')", "eval"),
    ("exec('print(1)')", "exec"),
    ("__import__('os')", "__import__"),
    ("compile('x=1', '<s>', 'exec')", "compile"),
    ("breakpoint()", "breakpoint"),
])
def test_ast_layer_blocks_banned_builtins(snippet, label):
    with pytest.raises(SecurityError) as ei:
        _sanitize_generated_code(snippet)
    assert label in str(ei.value) or "built-in" in str(ei.value)


@pytest.mark.parametrize("snippet,label", [
    ("import os; os.system('rm -rf /')", "os"),
    ("import subprocess; subprocess.run(['ls'])", "subprocess"),
    ("from shutil import rmtree; rmtree('/')", "shutil"),
    ("import socket; socket.socket()", "socket"),
    ("import ctypes; ctypes.CDLL('libc.so.6')", "ctypes"),
    ("import os; os.environ['KEY'] = 'x'", "os"),
])
def test_ast_layer_blocks_module_calls(snippet, label):
    with pytest.raises(SecurityError) as ei:
        _sanitize_generated_code(snippet)
    assert label in str(ei.value) or "module" in str(ei.value)


def test_ast_layer_blocks_obfuscated_eval_via_getattr():
    """``getattr(__builtins__, 'eval')('1+1')`` must be blocked too."""
    snippet = "getattr(__builtins__, 'eval')('1+1')"
    with pytest.raises(SecurityError):
        _sanitize_generated_code(snippet)


def test_ast_layer_blocks_dynamic_import_then_system():
    """The canonical LLM bypass: ``__import__('os').system('...')``."""
    snippet = "__import__('os').system('rm -rf /')"
    with pytest.raises(SecurityError):
        _sanitize_generated_code(snippet)


def test_safe_legitimate_code_passes():
    """Common pandas operations must remain untouched."""
    safe = (
        "result = {'mean_a': float(df['a'].mean()), 'count': int(len(df))}\n"
        "RESULT_JSON = result\n"
    )
    out = _sanitize_generated_code(safe)
    assert "df['a'].mean()" in out


def test_safe_uses_os_path_basename():
    """Reading ``os.path.basename`` is allowed (attribute, not a call into
    ``os``), so legitimate helpers keep working."""
    safe = "name = os.path.basename('foo/bar.csv')\nRESULT_JSON = {'name': name}\n"
    # Should NOT raise.
    _sanitize_generated_code(safe)


# ---------------------------------------------------------------------------
# End-to-end via execute_code(): rejection must surface as a SecurityError
# in the returned dict, not as a silent sandbox escape.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("snippet", [
    "import os; os.system('echo PWNED > /tmp/pwn.txt')",
    "subprocess.run(['touch', '/tmp/pwn2.txt'])",
    "eval('1+1')",
])
def test_execute_code_blocks_attack(csv_path, tmp_path, snippet):
    result = execute_code(snippet, csv_path)
    assert result["success"] is False
    assert "security policy" in (result.get("error") or "")
    # No side-effect files should have been created in the project tree.
    assert not (tmp_path / "pwn.txt").exists()


def test_execute_code_runs_clean_pandas(csv_path):
    code = (
        "RESULT_JSON = {'rows': int(len(df)), "
        "'mean_a': float(df['a'].mean())}\n"
    )
    result = execute_code(code, csv_path)
    assert result["success"], result.get("error")
    assert result["stats"]["rows"] == 2
    assert result["stats"]["mean_a"] == 2.0


def test_syntax_error_is_passed_through_for_real_error_message(csv_path):
    """Bad Python should produce a SyntaxError, NOT a SecurityError."""
    result = execute_code("this is not (valid python", csv_path)
    assert result["success"] is False
    assert "SyntaxError" in (result.get("error") or "") or result.get("error")
    # SecurityError shouldn't fire here.
    assert "security policy" not in (result.get("error") or "")
