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
def _extract_df_info(df: pd.DataFrame, csv_path: str) -> Dict[str, Any]:
    """Return a dict of summary strings for the LLM prompt."""
    missing_counts = df.isnull().sum()
    missing_nonzero = missing_counts[missing_counts > 0]

    return {
        "csv_path": csv_path,
        "shape": df.shape,
        "dtypes": df.dtypes.to_string(),
        "head": df.head(5).to_string(),
        "describe": df.describe(include="all").to_string(),
        "nunique": df.nunique().to_string(),
        "missing_info": (
            missing_nonzero.to_string() if not missing_nonzero.empty else "No missing values"
        ),
        "duplicates": int(df.duplicated().sum()),
    }


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
    user_prompt = PROFILER_USER_PROMPT_TEMPLATE.format(**info, report_path=report_path)

    # ------------------------------------------------------------------
    # 5. LLM call with structured output
    # ------------------------------------------------------------------
    logger.info("Calling LLM (model=%s) for structured profile...", os.getenv("MODEL", "gpt-4.1-nano"))
    try:
        llm = _build_llm()
        structured_llm = llm.with_structured_output(ProfileOutput, method="function_calling")
        profile_obj: ProfileOutput = structured_llm.invoke(
            [
                {"role": "system", "content": PROFILER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )
        profile_dict = profile_obj.model_dump()
        logger.info("LLM returned a valid ProfileOutput.")
    except EnvironmentError as env_err:
        state["error_log"].append(str(env_err))
        state["status"] = "failed"
        return state
    except Exception as exc:
        state["error_log"].append(f"LLM profiling failed: {exc}")
        state["status"] = "failed"
        return state

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
