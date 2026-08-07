"""
Profiler Agent — LangGraph Node (Member 1)

Reads:  state["csv_path"]
Writes: state["profile"], state["profile_report_path"], state["error_log"], state["status"]
"""

import os
import logging
from typing import Dict, Any

import pandas as pd
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from state.graph_state import AgentState
from tools.profiling_tool import ProfilingTool
from agents.profiler_prompts import PROFILER_SYSTEM_PROMPT, PROFILER_USER_PROMPT_TEMPLATE
from agents.profiler_schemas import ProfileOutput

# ---------------------------------------------------------------------------
# Environment & logging
# ---------------------------------------------------------------------------
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

# ---------------------------------------------------------------------------
# LLM — fully configured from .env
# ---------------------------------------------------------------------------
def _build_llm() -> ChatOpenAI:
    """Instantiate ChatOpenAI from environment variables."""
    model = os.getenv("MODEL", "gpt-4.1-nano")
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. "
            "Copy .env.example to .env and fill in your API key."
        )

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )


# Tool instance (stateless, safe to share)
_profiling_tool = ProfilingTool()


# ---------------------------------------------------------------------------
# Helper: extract DataFrame summaries
# ---------------------------------------------------------------------------
def _compute_descriptive_stats(df: pd.DataFrame) -> dict:
    """
    Compute descriptive_stats directly from pandas — never rely on the LLM for this.
    Returns a dict of {col_name: {mean, median, std, min, max}} for all numeric cols
    that are NOT obvious ID columns.
    """
    id_hints = {"id", "key", "code", "num", "no", "number"}
    stats: dict = {}
    numeric_cols = df.select_dtypes(include=["int64", "float64", "int32", "float32"]).columns
    for col in numeric_cols:
        col_lower = col.lower()
        # Skip obvious ID columns
        if any(hint in col_lower for hint in id_hints):
            continue
        s = df[col].dropna()
        if s.empty:
            continue
        stats[col] = {
            "mean":   round(float(s.mean()), 6),
            "median": round(float(s.median()), 6),
            "std":    round(float(s.std()), 6),
            "min":    round(float(s.min()), 6),
            "max":    round(float(s.max()), 6),
        }
    return stats


def _extract_df_info(df: pd.DataFrame, csv_path: str) -> Dict[str, Any]:
    """Return a compact dict of summary strings safe for any LLM context window."""
    missing_counts = df.isnull().sum()
    missing_nonzero = missing_counts[missing_counts > 0]

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

    # Always limit describe to numeric cols only (no string columns that bloat the output)
    # and cap at 20 columns to stay well within context limits
    describe_cols = numeric_cols[:20]
    describe_str = df[describe_cols].describe().to_string() if describe_cols else "(no numeric columns)"

    # Cap dtypes output — list all columns but truncate representation
    MAX_DTYPE_COLS = 80
    if len(df.columns) > MAX_DTYPE_COLS:
        dtypes_str = df.dtypes.head(MAX_DTYPE_COLS).to_string() + (
            f"\n... ({len(df.columns) - MAX_DTYPE_COLS} more columns omitted)"
        )
    else:
        dtypes_str = df.dtypes.to_string()

    # Cap head preview to first 20 columns
    head_str = df.head(5).iloc[:, :20].to_string()

    # Cap nunique to 80 cols
    nunique_str = df.nunique().head(80).to_string() + (
        f"\n... ({len(df.columns) - 80} more columns omitted)" if len(df.columns) > 80 else ""
    )

    return {
        "csv_path": csv_path,
        "shape": df.shape,
        "dtypes": dtypes_str,
        "head": head_str,
        "describe": describe_str,
        "nunique": nunique_str,
        "missing_info": (
            missing_nonzero.to_string() if not missing_nonzero.empty else "No missing values"
        ),
        "duplicates": int(df.duplicated().sum()),
    }


def _build_profile_from_pandas(df: pd.DataFrame, csv_path: str) -> dict:
    """
    Pure pandas fallback — builds the full ProfileOutput-compatible dict
    without any LLM call. Used when the LLM fails on very large/wide datasets.
    """
    import os as _os
    id_hints = {"id", "key", "code", "num", "no", "number"}
    missing_counts = df.isnull().sum()

    numeric_cols, categorical_cols, datetime_cols, id_cols = [], [], [], []
    constant_cols, high_card_cols = [], []

    for col in df.columns:
        col_lower = col.lower()
        dtype = df[col].dtype
        nunique = df[col].nunique(dropna=True)

        is_id_name = any(hint in col_lower for hint in id_hints)

        if is_id_name:
            id_cols.append(col)
        elif dtype in ["int64", "float64", "int32", "float32"]:
            numeric_cols.append(col)
        elif dtype == "object":
            # Try datetime parse on a sample (suppress non-critical format warnings)
            try:
                import warnings as _w, pandas as _pd
                with _w.catch_warnings():
                    _w.simplefilter("ignore")
                    _pd.to_datetime(df[col].dropna().head(20), errors="raise")
                datetime_cols.append(col)
            except Exception:
                if nunique == 1:
                    constant_cols.append(col)
                elif nunique <= 50:
                    categorical_cols.append(col)
                else:
                    high_card_cols.append(col)
        elif str(dtype).startswith("datetime"):
            datetime_cols.append(col)
        else:
            categorical_cols.append(col)

        if df[col].nunique() == 1 and col not in constant_cols:
            constant_cols.append(col)

    stats = _compute_descriptive_stats(df)
    memory_mb = round(df.memory_usage(deep=True).sum() / 1e6, 6)
    filename = _os.path.basename(csv_path)

    return {
        "dataset_name": filename,
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "datetime_columns": datetime_cols,
        "id_columns": id_cols,
        "missing_values": {c: int(v) for c, v in missing_counts.items() if v > 0},
        "duplicates": int(df.duplicated().sum()),
        "constant_columns": constant_cols,
        "high_cardinality_columns": high_card_cols,
        "memory_usage_mb": memory_mb,
        "sample_rows": 5,
        "descriptive_stats": stats,
    }


def _build_minimal_prompt(df: pd.DataFrame, csv_path: str, report_path: str) -> str:
    """
    Build a drastically trimmed prompt used as the second LLM attempt for very
    large/wide datasets. Only sends column names + dtypes + shape — no describe,
    no head, no nunique — just enough for the LLM to classify column types.
    """
    import os as _os
    col_type_lines = "\n".join(
        f"  {col}: {dtype}" for col, dtype in df.dtypes.items()
    )
    missing_counts = df.isnull().sum()
    missing_nonzero = missing_counts[missing_counts > 0]
    missing_str = (
        missing_nonzero.to_string() if not missing_nonzero.empty else "No missing values"
    )
    return (
        f"CSV file: {_os.path.basename(csv_path)}\n"
        f"Shape: {df.shape[0]} rows x {df.shape[1]} columns\n"
        f"Duplicate rows: {int(df.duplicated().sum())}\n\n"
        f"Column names and dtypes:\n{col_type_lines}\n\n"
        f"Missing values (columns with > 0 missing only):\n{missing_str}\n\n"
        f"Profile report path: {report_path}\n\n"
        "Classify every column into exactly one category and return the structured profile."
    )


# ---------------------------------------------------------------------------
# Core node
# ---------------------------------------------------------------------------
def profiler_node(state: AgentState) -> AgentState:
    """
    LangGraph node: analyzes a CSV file and produces a structured dataset profile.

    Steps:
      1. Validate input file (existence, extension)
      2. Read CSV with encoding fallback
      3. Run ProfilingTool → ydata-profiling HTML report
      4. Build LLM prompt from DataFrame summaries
      5. Call LLM with structured output (ProfileOutput)
      6. Self-validate the profile
      7. Write results back into state
    """
    # Defensive init — ensure mutable lists/dicts exist
    state.setdefault("error_log", [])
    state["status"] = "running"

    csv_path: str = state.get("csv_path", "")

    # ------------------------------------------------------------------
    # 1. Input validation
    # ------------------------------------------------------------------
    if not csv_path:
        state["error_log"].append("csv_path is empty or missing from state.")
        state["status"] = "failed"
        return state

    if not os.path.exists(csv_path):
        state["error_log"].append(f"File not found: {csv_path}")
        state["status"] = "failed"
        return state

    if not csv_path.lower().endswith(".csv"):
        state["error_log"].append(f"Not a CSV file: {csv_path}")
        state["status"] = "failed"
        return state

    logger.info("Profiler node started for: %s", csv_path)

    # ------------------------------------------------------------------
    # 2. Read CSV with encoding fallback
    # ------------------------------------------------------------------
    try:
        try:
            df = pd.read_csv(csv_path, encoding="utf-8")
            logger.info("Read CSV with UTF-8 encoding.")
        except UnicodeDecodeError:
            df = pd.read_csv(csv_path, encoding="latin-1")
            logger.info("Read CSV with latin-1 encoding (UTF-8 failed).")
    except pd.errors.EmptyDataError:
        state["error_log"].append("CSV file is empty.")
        state["status"] = "failed"
        return state
    except Exception as exc:
        state["error_log"].append(f"Failed to read CSV: {exc}")
        state["status"] = "failed"
        return state

    if df.shape[1] == 0:
        state["error_log"].append("CSV has 0 columns.")
        state["status"] = "failed"
        return state

    if df.shape[0] == 0:
        state["error_log"].append("CSV has 0 data rows.")
        state["status"] = "failed"
        return state

    # ------------------------------------------------------------------
    # 3. Run profiling tool → HTML report
    # ------------------------------------------------------------------
    logger.info("Running ProfilingTool...")
    tool_result: str = _profiling_tool.run({"csv_path": csv_path})

    if tool_result.startswith("ERROR"):
        state["error_log"].append(f"ProfilingTool error: {tool_result}")
        state["status"] = "failed"
        return state

    # Parse "SUCCESS: Report saved to <path>"
    report_path = tool_result.replace("SUCCESS: Report saved to ", "").strip()
    logger.info("Profile report written to: %s", report_path)

    # ------------------------------------------------------------------
    # 4. Build LLM prompt
    # ------------------------------------------------------------------
    info = _extract_df_info(df, csv_path)

    # Compute descriptive_stats directly from pandas — always reliable, no LLM needed
    computed_stats = _compute_descriptive_stats(df)

    user_prompt = PROFILER_USER_PROMPT_TEMPLATE.format(**info, report_path=report_path)

    # ------------------------------------------------------------------
    # 5. LLM call with structured output (with minimal-prompt retry + pandas fallback)
    # ------------------------------------------------------------------
    logger.info("Calling LLM (model=%s) for structured profile...", os.getenv("MODEL", "gpt-4.1-nano"))
    profile_dict: dict | None = None

    for attempt, prompt in enumerate([user_prompt, _build_minimal_prompt(df, csv_path, report_path)], start=1):
        try:
            llm = _build_llm()
            structured_llm = llm.with_structured_output(ProfileOutput, method="function_calling")
            profile_obj: ProfileOutput = structured_llm.invoke(
                [
                    {"role": "system", "content": PROFILER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ]
            )
            profile_dict = profile_obj.model_dump()
            logger.info("LLM returned a valid ProfileOutput (attempt %d).", attempt)
            break
        except EnvironmentError as env_err:
            state["error_log"].append(str(env_err))
            state["status"] = "failed"
            return state
        except Exception as exc:
            logger.warning("LLM attempt %d failed: %s", attempt, exc)
            if attempt == 2:
                # Both LLM attempts failed — fall back to pure pandas profiling
                logger.warning("Both LLM attempts failed. Using pandas-only fallback.")
                profile_dict = _build_profile_from_pandas(df, csv_path)

    # Always overwrite descriptive_stats with the pandas-computed version.
    # This guarantees it is never missing or wrong, regardless of LLM context limits.
    profile_dict["descriptive_stats"] = computed_stats
    logger.info("Merged pandas-computed descriptive_stats (%d columns).", len(computed_stats))

    # ------------------------------------------------------------------
    # 6. Self-validation
    # ------------------------------------------------------------------
    if profile_dict["rows"] == 0 or profile_dict["columns"] == 0:
        state["error_log"].append(
            f"Profile shows {profile_dict['rows']} rows / {profile_dict['columns']} columns — invalid."
        )
        state["status"] = "failed"
        return state

    if (
        not profile_dict["numeric_columns"]
        and not profile_dict["categorical_columns"]
        and not profile_dict["datetime_columns"]
    ):
        state["error_log"].append(
            "No numeric, categorical, or datetime columns found — profile is unusable."
        )
        state["status"] = "failed"
        return state

    if not os.path.exists(report_path):
        state["error_log"].append(f"Report file not found after generation: {report_path}")
        state["status"] = "failed"
        return state

    # ------------------------------------------------------------------
    # 7. Write to state
    # ------------------------------------------------------------------
    state["profile"] = profile_dict
    state["profile_report_path"] = os.path.abspath(report_path)
    state["status"] = "completed"

    logger.info(
        "Profiler node completed. Rows=%d, Cols=%d, Numeric=%d, Categorical=%d",
        profile_dict["rows"],
        profile_dict["columns"],
        len(profile_dict["numeric_columns"]),
        len(profile_dict["categorical_columns"]),
    )
    return state
