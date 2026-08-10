"""Streamlit Web Application — Main Entry Point

AI Data Analyst System Dashboard.

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

import sys

# Safeguard against broken PyTorch/transformers DLL initialization on Windows
try:
    import transformers  # noqa: F401
except OSError:
    sys.modules["transformers"] = None
except ImportError:
    pass

import streamlit as st

# Set page config as the very first Streamlit call
st.set_page_config(
    page_title="AI Data Analyst System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui.components.header import render_header
from ui.components.pipeline_runner import render_pipeline_runner
from ui.components.eda_profile import render_eda_profile
from ui.components.insights_gallery import render_insights_gallery
from ui.components.analyst_chat import render_analyst_chat
from ui.components.diagnostics import render_diagnostics


def main():
    """Main application orchestrator."""
    # Top hero header and styling
    render_header()

    # Session state initialization
    if "state" not in st.session_state:
        st.session_state["state"] = {}

    current_state = st.session_state.get("state", {})

    # Create 5-Tab Dashboard Layout
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "🚀 Pipeline Runner",
            "📊 Dataset Profile & EDA",
            "💡 Executive Insights & Charts",
            "💬 Analyst Chat",
            "🛠️ Agent Diagnostics",
        ]
    )

    with tab1:
        render_pipeline_runner()

    with tab2:
        render_eda_profile(current_state)

    with tab3:
        render_insights_gallery(current_state)

    with tab4:
        render_analyst_chat(current_state)

    with tab5:
        render_diagnostics(current_state)


if __name__ == "__main__":
    main()
