import os
import pandas as pd
from ydata_profiling import ProfileReport
from langchain.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

_OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output/profiles")
_MAX_FILE_SIZE_MB = float(os.getenv("MAX_FILE_SIZE_MB", "50"))


class ProfilingToolInput(BaseModel):
    csv_path: str = Field(description="Absolute or relative path to the CSV file")
    output_dir: str = Field(
        default=_OUTPUT_DIR,
        description="Directory to save the HTML profile report",
    )


class ProfilingTool(BaseTool):
    """
    LangChain BaseTool that wraps ydata-profiling.

    Returns:
        "SUCCESS: Report saved to <path>"  on success
        "ERROR: <reason>"                  on any failure
    """

    name: str = "generate_profile_report"
    description: str = (
        "Generates an interactive HTML profile report for a CSV file using "
        "ydata-profiling. Returns the file path of the generated report."
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
        if file_size_mb > _MAX_FILE_SIZE_MB:
            return (
                f"ERROR: File too large ({file_size_mb:.2f} MB). "
                f"Maximum supported size is {_MAX_FILE_SIZE_MB:.0f} MB."
            )

        # --- Read CSV with encoding fallback ---
        try:
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

        # --- Generate profile report with downsampling for large datasets ---
        try:
            df_sample = df
            if len(df) > 50000:
                df_sample = df.sample(10000, random_state=42)

            profile = ProfileReport(
                df_sample,
                title="Dataset Profile",
                explorative=True,
                minimal=True,  # fast profiling for large datasets
            )
            base_name = os.path.splitext(os.path.basename(csv_path))[0]
            report_path = os.path.join(output_dir, f"{base_name}_profile.html")
            profile.to_file(report_path)
            return f"SUCCESS: Report saved to {report_path}"

        except Exception as e:
            return f"ERROR: Profiling failed - {str(e)}"

    async def _arun(self, csv_path: str, output_dir: str = _OUTPUT_DIR) -> str:
        """Async wrapper — delegates to sync implementation."""
        return self._run(csv_path, output_dir)
