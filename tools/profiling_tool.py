import contextlib
import io
import os
from typing import Type

import pandas as pd
import sweetviz as sv
from dotenv import load_dotenv
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from config import PROFILE_DIR, PROFILE_MAX_FILE_SIZE_MB, PROFILE_PAIRWISE_COL_LIMIT

load_dotenv()

_OUTPUT_DIR = PROFILE_DIR
_MAX_FILE_SIZE_MB = PROFILE_MAX_FILE_SIZE_MB
# sweetviz pairwise correlation cost grows quadratically with column count;
# disable it for wide datasets to keep profiling fast and memory-light.
_PAIRWISE_COL_LIMIT = PROFILE_PAIRWISE_COL_LIMIT


class ProfilingToolInput(BaseModel):
    csv_path: str = Field(description="Absolute or relative path to the CSV file")
    output_dir: str = Field(
        default=_OUTPUT_DIR,
        description="Directory to save the HTML profile report",
    )


class ProfilingTool(BaseTool):
    """
    LangChain BaseTool that wraps sweetviz.

    Generates a self-contained interactive HTML exploratory data analysis
    report (per-column distributions, missingness, correlations, type
    detection). Returns an absolute path to a standalone HTML file.

    Returns:
        "SUCCESS: Report saved to <path>"  on success
        "ERROR: <reason>"                  on any failure
    """

    name: str = "generate_profile_report"
    description: str = (
        "Generates an interactive HTML profile report for a CSV file using "
        "sweetviz. Returns the file path of the generated report."
    )
    args_schema: Type[BaseModel] = ProfilingToolInput

    def _run(self, csv_path: str, output_dir: str = _OUTPUT_DIR) -> str:
        """Execute the profiler and return the report path or an error string."""
        # --- Directory setup ---
        os.makedirs(output_dir, exist_ok=True)

        # --- File existence check ---
        if not os.path.exists(csv_path):
            return f"ERROR: File not found: {csv_path}"

        # --- Extension check ---
        if not csv_path.lower().endswith(".csv"):
            return f"ERROR: File does not have .csv extension: {csv_path}"

        # --- Size check ---
        file_size_mb = os.path.getsize(csv_path) / (1024 * 1024)
        from config import API_MAX_FILE_SIZE_MB
        if file_size_mb > API_MAX_FILE_SIZE_MB:
            return (
                f"ERROR: File too large ({file_size_mb:.2f} MB). "
                f"Maximum supported size is {API_MAX_FILE_SIZE_MB:.0f} MB."
            )

        # --- Read CSV with chunked downsample support for >50MB files ---
        try:
            if file_size_mb > _MAX_FILE_SIZE_MB:
                # Streaming read for large files to avoid memory pressure
                chunks = []
                total_rows = 0
                sample_per_chunk = 5000
                target_total = 50000
                try:
                    reader = pd.read_csv(csv_path, chunksize=20000, encoding="utf-8")
                    for chunk in reader:
                        if chunk.empty:
                            continue
                        chunk_sample = chunk.sample(min(len(chunk), sample_per_chunk), random_state=42)
                        chunks.append(chunk_sample)
                        total_rows += len(chunk_sample)
                        if total_rows >= target_total:
                            break
                except UnicodeDecodeError:
                    reader = pd.read_csv(csv_path, chunksize=20000, encoding="latin-1")
                    for chunk in reader:
                        if chunk.empty:
                            continue
                        chunk_sample = chunk.sample(min(len(chunk), sample_per_chunk), random_state=42)
                        chunks.append(chunk_sample)
                        total_rows += len(chunk_sample)
                        if total_rows >= target_total:
                            break
                if not chunks:
                    return "ERROR: CSV file is empty."
                df = pd.concat(chunks, ignore_index=True)
            else:
                try:
                    df = pd.read_csv(csv_path, encoding="utf-8")
                except UnicodeDecodeError:
                    df = pd.read_csv(csv_path, encoding="latin-1")
        except pd.errors.EmptyDataError:
            return "ERROR: CSV file is empty."
        except Exception as e:
            return f"ERROR: Could not read CSV - {str(e)}"

        if df.empty or df.shape[1] == 0:
            return "ERROR: CSV has no usable data."

        # --- Generate profile report: downsample rows and disable pairwise
        # correlation on > N columns so sweetviz stays fast and lightweight ---
        try:
            df_sample = df
            if len(df) > 50000:
                df_sample = df.sample(10000, random_state=42)


            pairwise = "on" if df_sample.shape[1] <= _PAIRWISE_COL_LIMIT else "off"

            # sweetviz prints an animated progress bar; swallow it for logs
            with contextlib.redirect_stdout(io.StringIO()):
                report = sweetviz_analyze(df_sample, pairwise_analysis=pairwise)

            base_name = os.path.splitext(os.path.basename(csv_path))[0]
            report_path = os.path.join(output_dir, f"{base_name}_profile.html")
            with contextlib.redirect_stdout(io.StringIO()):
                report.show_html(filepath=report_path, open_browser=False)

            if not os.path.exists(report_path):
                return f"ERROR: Profiling failed - report file not created at {report_path}"
            return f"SUCCESS: Report saved to {report_path}"

        except Exception as e:
            return f"ERROR: Profiling failed - {str(e)}"

    async def _arun(self, csv_path: str, output_dir: str = _OUTPUT_DIR) -> str:
        """Async wrapper — delegates to sync implementation."""
        return self._run(csv_path, output_dir)


def sweetviz_analyze(df: pd.DataFrame, pairwise_analysis: str = "on"):
    """Thin wrapper over ``sweetviz.analyze`` so the tool stays swappable."""
    return sv.analyze(df, pairwise_analysis=pairwise_analysis)
