"""
Profiler Agent — Edge Case Test Suite
======================================
Run with:  python -m pytest tests/test_profiler.py -v

LLM-dependent tests are automatically skipped when OPENAI_API_KEY is not set.
File-validation tests run without any API key.
"""

import io
import os
import sys
import pytest

# Ensure project root is on the path when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state.graph_state import AgentState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(csv_path: str) -> AgentState:
    return {
        "csv_path": csv_path,
        "profile": None,
        "profile_report_path": None,
        "error_log": [],
        "status": "running",
    }


def _has_api_key() -> bool:
    from dotenv import load_dotenv
    load_dotenv()
    return bool(os.getenv("OPENAI_API_KEY"))


# ---------------------------------------------------------------------------
# File-validation tests  (no LLM required)
# ---------------------------------------------------------------------------

class TestFileValidation:
    """These tests exercise early-exit logic and require no API key."""

    def test_missing_file_returns_failed(self):
        from agents.profiler_agent import profiler_node
        state = _make_state("data/non_existent_file_xyz.csv")
        result = profiler_node(state)
        assert result["status"] == "failed"
        assert any("not found" in e.lower() for e in result["error_log"])

    def test_non_csv_extension_returns_failed(self):
        # Create a real file with wrong extension
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("col1,col2\n1,2\n")
            tmp_path = f.name
        try:
            from agents.profiler_agent import profiler_node
            state = _make_state(tmp_path)
            result = profiler_node(state)
            assert result["status"] == "failed"
            assert any("csv" in e.lower() for e in result["error_log"])
        finally:
            os.unlink(tmp_path)

    def test_empty_csv_returns_failed(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            f.write("")   # completely empty
            tmp_path = f.name
        try:
            from agents.profiler_agent import profiler_node
            state = _make_state(tmp_path)
            result = profiler_node(state)
            assert result["status"] == "failed"
        finally:
            os.unlink(tmp_path)

    def test_empty_csv_path_returns_failed(self):
        from agents.profiler_agent import profiler_node
        state = _make_state("")
        result = profiler_node(state)
        assert result["status"] == "failed"
        assert any("empty" in e.lower() or "missing" in e.lower() for e in result["error_log"])

    def test_error_log_is_populated_on_failure(self):
        from agents.profiler_agent import profiler_node
        state = _make_state("totally_wrong_path.csv")
        result = profiler_node(state)
        assert len(result["error_log"]) > 0

    def test_no_exception_escapes(self):
        """Node must never raise; all errors go to error_log."""
        from agents.profiler_agent import profiler_node
        try:
            state = _make_state("does/not/exist.csv")
            profiler_node(state)
        except Exception as exc:
            pytest.fail(f"profiler_node raised an exception: {exc}")


# ---------------------------------------------------------------------------
# Integration tests  (require OPENAI_API_KEY)
# ---------------------------------------------------------------------------

LLM_SKIP = pytest.mark.skipif(
    not _has_api_key(),
    reason="OPENAI_API_KEY not set — skipping LLM integration tests",
)


@LLM_SKIP
class TestIntegration:
    """Full end-to-end tests that call the real LLM."""

    def test_normal_csv_completes(self):
        from agents.profiler_agent import profiler_node
        state = _make_state("data/sample_sales.csv")
        result = profiler_node(state)
        assert result["status"] == "completed", f"Errors: {result['error_log']}"

        profile = result["profile"]
        assert profile["rows"] > 0
        assert profile["columns"] > 0
        assert isinstance(profile["numeric_columns"], list)
        assert isinstance(profile["categorical_columns"], list)
        assert isinstance(profile["missing_values"], dict)
        assert isinstance(profile["descriptive_stats"], dict)

    def test_report_file_exists_after_run(self):
        from agents.profiler_agent import profiler_node
        state = _make_state("data/sample_sales.csv")
        result = profiler_node(state)
        assert result["status"] == "completed"
        assert result["profile_report_path"] is not None
        assert os.path.exists(result["profile_report_path"]), "HTML report file not found on disk"

    def test_id_columns_not_in_numeric(self):
        """Order_ID and Customer_ID must NOT appear in numeric_columns."""
        from agents.profiler_agent import profiler_node
        state = _make_state("data/sample_sales.csv")
        result = profiler_node(state)
        assert result["status"] == "completed"
        numeric = result["profile"]["numeric_columns"]
        assert "Order_ID" not in numeric
        assert "Customer_ID" not in numeric

    def test_missing_values_is_dict(self):
        from agents.profiler_agent import profiler_node
        state = _make_state("data/sample_sales.csv")
        result = profiler_node(state)
        assert result["status"] == "completed"
        mv = result["profile"]["missing_values"]
        assert isinstance(mv, dict)
        # sample_sales.csv has missing values in Sales and Quantity
        assert len(mv) >= 1

    def test_all_missing_column_still_profiled(self):
        """A CSV with one column being all NaN should still complete."""
        import tempfile, csv
        rows = [
            ["ID", "Value", "AllMissing"],
            ["1", "10.5", ""],
            ["2", "20.3", ""],
            ["3", "15.0", ""],
        ]
        with tempfile.NamedTemporaryFile(
            suffix=".csv", delete=False, mode="w", newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerows(rows)
            tmp_path = f.name
        try:
            from agents.profiler_agent import profiler_node
            state = _make_state(tmp_path)
            result = profiler_node(state)
            assert result["status"] == "completed"
            assert "AllMissing" in result["profile"]["missing_values"]
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Entry point for direct execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import subprocess
    subprocess.run(["python", "-m", "pytest", __file__, "-v"], check=False)
