from typing import Dict, Any, List, TypedDict, Optional

class AgentState(TypedDict):
    csv_path: str
    profile: Dict[str, Any]
    profile_report_path: str
    analysis_plan: Optional[List[Dict[str, Any]]]
    analysis_results: Optional[Dict[str, Any]]
    generated_files: Optional[List[str]]
    execution_log: Optional[List[Dict[str, Any]]]
    reflection_notes: Optional[List[str]]
    validation_report: Optional[Dict[str, Any]]
    insights: Optional[List[Dict[str, Any]]]
    recommendations: Optional[List[str]]
    report_path: Optional[str]
    error_log: List[str]
    status: str
