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
    "value": "category frequency charts and interactive counts",
    "code": """
import os, matplotlib.pyplot as plt
cats = df.select_dtypes(include=["object", "category", "str"]).columns.tolist()
RESULT_JSON = {}
if "charts" not in RESULT_JSON:
    RESULT_JSON["charts"] = []
for _c in cats:
    _vc = df[_c].value_counts(dropna=False).head(10)
    if _vc.empty:
        continue
    _top = _vc.index[0]
    RESULT_JSON[f"top_{_c}"] = str(_top)
    RESULT_JSON[f"top_count_{_c}"] = int(_vc.iloc[0])
    RESULT_JSON[f"unique_{_c}"] = int(df[_c].nunique())

    _chart_data = [{"label": str(k), "value": int(v)} for k, v in _vc.items()]
    RESULT_JSON[f"chart_data_{_c}"] = _chart_data

    fig, ax = plt.subplots(figsize=(6, 4))
    _vc.plot(kind="bar", ax=ax, color="#10b981", edgecolor="#047857", alpha=0.85)
    ax.set_title(f"Top Values: {_c}", fontsize=12, fontweight="bold")
    ax.set_ylabel("Count")
    plt.xticks(rotation=45, ha="right")
    ax.grid(True, linestyle="--", alpha=0.5)
    fig.tight_layout()
    _fname = f"cat_{_c}.png"
    _fpath = os.path.join("output", "analysis", _fname)
    fig.savefig(_fpath, dpi=120)
    plt.close(fig)
    RESULT_JSON["charts"].append({
        "column": _c,
        "title": f"Category Breakdown: {_c}",
        "kind": "bar",
        "data": _chart_data,
        "image_file": _fname
    })
""",
}

_CORRELATION = {
    "value": "pairwise pearson correlation matrix and heatmap",
    "code": """
import itertools
import os
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
nums = df.select_dtypes(include=["number"]).columns.tolist()
RESULT_JSON = {}
if "charts" not in RESULT_JSON:
    RESULT_JSON["charts"] = []
if len(nums) >= 2:
    _corr_df = df[nums].corr()
    _chart_data = []
    for _a, _b in itertools.combinations(nums, 2):
        _val = _corr_df.loc[_a, _b]
        if pd.notna(_val):
            RESULT_JSON[f"corr_{_a}_{_b}"] = float(_val)
            _chart_data.append({"label": f"{_a} vs {_b}", "value": round(float(_val), 3)})
    RESULT_JSON["chart_data_correlation"] = _chart_data

    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(_corr_df, annot=True, fmt=".2f", cmap="coolwarm", ax=ax, cbar=True)
    ax.set_title("Correlation Matrix", fontsize=12, fontweight="bold")
    fig.tight_layout()
    _fname = "correlation_matrix.png"
    _fpath = os.path.join("output", "analysis", _fname)
    fig.savefig(_fpath, dpi=120)
    plt.close(fig)
    RESULT_JSON["charts"].append({
        "column": "all",
        "title": "Correlation Matrix",
        "kind": "bar",
        "data": _chart_data[:10],
        "image_file": _fname
    })
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
    "value": "histograms per numeric column saved as individual files",
    "code": """
import os, numpy as np, matplotlib.pyplot as plt
nums = df.select_dtypes(include=["number"]).columns.tolist()
RESULT_JSON = {}
if "charts" not in RESULT_JSON:
    RESULT_JSON["charts"] = []

def _fmt_b(v):
    try:
        fv = float(v)
        if abs(fv) >= 1_000_000:
            return f"{fv/1_000_000:.1f}M"
        if abs(fv) >= 10_000:
            return f"{fv/1_000:.1f}k"
        if abs(fv) >= 1_000:
            return f"{fv:,.0f}"
        if fv.is_integer():
            return f"{int(fv)}"
        return f"{fv:.1f}"
    except Exception:
        return str(v)

for _c in nums:
    _s = df[_c].dropna()
    if _s.empty:
        continue
    _nbins = min(12, max(5, int(_s.nunique())))
    _counts, _edges = np.histogram(_s, bins=_nbins)
    _chart_data = [
        {"label": f"{_fmt_b(_edges[i])} - {_fmt_b(_edges[i+1])}", "value": int(_counts[i])}
        for i in range(len(_counts))
    ]
    RESULT_JSON[f"chart_data_{_c}"] = _chart_data

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(_s, bins=_nbins, color="#3b82f6", edgecolor="#1d4ed8", alpha=0.85)
    ax.set_title(f"Distribution of {_c}", fontsize=12, fontweight="bold")
    ax.set_xlabel(_c)
    ax.set_ylabel("Frequency")
    ax.grid(True, linestyle="--", alpha=0.5)
    fig.tight_layout()
    _fname = f"dist_{_c}.png"
    _fpath = os.path.join("output", "analysis", _fname)
    fig.savefig(_fpath, dpi=120)
    plt.close(fig)
    RESULT_JSON["charts"].append({
        "column": _c,
        "title": f"Distribution of {_c}",
        "kind": "bar",
        "data": _chart_data,
        "image_file": _fname
    })
    RESULT_JSON[f"{_c}_n"] = int(len(_s))
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
