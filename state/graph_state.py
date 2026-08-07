from typing import TypedDict, List, Dict, Any, Optional


class AgentState(TypedDict):
    """
    Shared state contract for the LangGraph pipeline.

    Member 1 (Profiler Agent):
        - Reads:  csv_path
        - Writes: profile, profile_report_path, error_log, status
    """

    csv_path: str                          # input: path to uploaded CSV
    profile: Optional[Dict[str, Any]]      # structured dataset profile dict
    profile_report_path: Optional[str]     # absolute path to ydata-profiling HTML report
    error_log: List[str]                   # list of error messages (appended, never cleared)
    status: str                            # "running" | "completed" | "failed"
