"""Deterministic code templates for standard Analysis tasks (no LLM).

The executor's standard tasks - descriptive statistics, category frequency,
correlation matrix, outlier detection, distribution plots, missing values -
are pure pandas; shipping them through an LLM just to re-print the same
operations costs money and triptoes rate limits (429s), and every 429 turns
into a wasted failover call. So we hand-write the code here.

``template_for(task_name, profile)`` returns a code string that runs inside
``python_executor``'s sandbox (``df`` already loaded) and populates
``RESULT_JSON`` with recomputable stat keys, or ``None`` when the task is not
covered (the executor then falls back to the LLM).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Task names the deterministic templates cover. Anything else goes to the LLM.
TEMPLATED_KINDS = {
    "descriptive_statistics",
    "category_frequency",
    "correlation_analysis",
    "outlier_detection",
    "distribution_plots",
    "missing_value_analysis",
}

_HDR = "# deterministic template (no LLM)"

_DESCRIPTIVE_STATS = {
    "value": "per-column mean/median/mode/std/min/max",
    "code": """
""" + _HDR + """
RESULT_JSON = {}
_numeric = df.select_dtypes(include=["number"]).columns.tolist()
for _c in _numeric:
    _s = df[_c].dropna()
    if _s.empty:
        continue
    RESULT_JSON[f"{_c}_mean"] = float(_s.mean())
    RESULT_JSON[f"{_c}_median"] = float(_s.median())
    RESULT_JSON[f"{_c}_std"] = float(_s.std())
    RESULT_JSON[f"{_c}_min"] = float(_s.min())
    RESULT_JSON[f"{_c}_max"] = float(_s.max())
    _mode = _s.mode()
    RESULT_JSON[f"{_c}_mode"] = float(_mode.iloc[0]) if not _mode.empty else None
""",
}

_CATEGORY_FREQUENCY = {
    "value": "top value counts for categorical columns",
    "code": """
import pandas as pd
cats = df.select_dtypes(include=["object", "category"]).columns.tolist()
RESULT_JSON = {}
for _c in cats:
    _vc = df[_c].value_counts(dropna=False)
    if _vc.empty:
        continue
    _top = _vc.index[0]
    RESULT_JSON[f"top_{_c}"] = str(_top)
    RESULT_JSON[f"top_count_{_c}"] = int(_vc.iloc[0])
    RESULT_JSON[f"unique_{_c}"] = int(df[_c].nunique())
""",
}

_CORRELATION = {
    "value": "pairwise pearson correlation of numeric columns",
    "code": """
import itertools
nums = df.select_dtypes(include=["number"]).columns.tolist()
RESULT_JSON = {}
for _a, _b in itertools.combinations(nums, 2):
    _corr = df[_a].corr(df[_b])
    if _corr is not None:
        RESULT_JSON[f"corr_{_a}_{_b}"] = float(_corr)
""",
}

_OUTLIERS = {
    "value": "IQR outlier counts for numeric columns",
    "code": """
nums = df.select_dtypes(include=["number"]).columns.tolist()
RESULT_JSON = {}
for _c in nums:
    _s = df[_c].dropna()
    if _s.empty:
        continue
    _q1, _q3 = _s.quantile(0.25), _s.quantile(0.75)
    _iqr = _q3 - _q1
    _lo, _hi = _q1 - 1.5 * _iqr, _q3 + 1.5 * _iqr
    _mask = (_s < _lo) | (_s > _hi)
    _n = int(_mask.sum())
    RESULT_JSON[f"{_c}_num_outliers"] = _n
    RESULT_JSON[f"{_c}_percentage_outliers"] = float(_n / len(_s) * 100)
""",
}

_DISTRIBUTION_PLOTS = {
    "value": "histograms per numeric column saved into output/analysis",
    "code": """
import uuid
nums = df.select_dtypes(include=["number"]).columns.tolist()
RESULT_JSON = {}
if nums:
    _ncols = 2
    _nrows = max(1, (len(nums) + _ncols - 1) // _ncols)
    fig, axes = plt.subplots(_nrows, _ncols, figsize=(5 * _ncols, 4 * _nrows))
    axes = np.array(axes).reshape(-1)
    for _i, _c in enumerate(nums):
        _s = df[_c].dropna()
        if _s.empty:
            continue
        axes[_i].hist(_s, bins=min(30, max(5, int(_s.nunique()))), color="steelblue", alpha=0.8)
        axes[_i].set_title(_c)
        axes[_i].grid(alpha=0.3)
        RESULT_JSON[f"{_c}_n"] = int(len(_s))
    _path = os.path.join("output", "analysis", f"distribution_{uuid.uuid4().hex[:8]}.png")
    fig.tight_layout()
    fig.savefig(_path, dpi=90)
    plt.close(fig)
    RESULT_JSON["plot_file"] = _path
""",
}

_MISSING_VALUES = {
    "value": "missing count / rate per column",
    "code": """
RESULT_JSON = {}
for _c in df.columns:
    _missing = int(df[_c].isna().sum())
    RESULT_JSON[f"missing_{_c}"] = _missing
    RESULT_JSON[f"missing_rate_{_c}"] = float(_missing / len(df) * 100)
""",
}

_TEMPLATES: Dict[str, Dict[str, str]] = {
    "descriptive_statistics": _DESCRIPTIVE_STATS,
    "category_frequency": _CATEGORY_FREQUENCY,
    "correlation_analysis": _CORRELATION,
    "outlier_detection": _OUTLIERS,
    "distribution_plots": _DISTRIBUTION_PLOTS,
    "missing_value_analysis": _MISSING_VALUES,
}


def templated_kinds() -> List[str]:
    return sorted(TEMPLATED_KINDS)


def template_for(task_name: str, profile: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Return deterministic sandbox code for a known task, or ``None``."""
    if not task_name:
        return None
    key = task_name.strip().lower()
    if key not in _TEMPLATES:
        return None
    return _TEMPLATES[key]["code"]


def supports(task_name: str) -> bool:
    return (task_name or "").strip().lower() in TEMPLATED_KINDS