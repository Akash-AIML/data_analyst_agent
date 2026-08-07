"""Streamlit frontend: report-grounded analyst chatbot.

Run:
    venv/bin/streamlit run agents/insight/streamlit_app.py

Works with NO API key out of the box: it runs the full (M1/M2 stand-in via
fixtures + FakeChatModel) pipeline on a sample CSV and answers from the
resulting report. Flip the "use real OpenAI" toggle (when OPENAI_API_KEY is
set) to switch to live insight + chat generation.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import streamlit as st

from agents.insight import chat, prompts
from agents.insight.insight_node import build_insight_node
from agents.insight.tests import fixtures
from agents.insight.tests.fake_llm import FakeChatModel

st.set_page_config(page_title="Data Analyst — Ask the Report", layout="wide")


SAMPLE_STATE_PATH = "output/reports/report_state.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_model(use_real: bool):
    if use_real:
        return prompts.get_chat_model(temperature=0.1)
    return FakeChatModel()


def _generate_sample(use_real: bool) -> Dict[str, Any]:
    """Run the pipeline (M1/M2 stand-in fixtures) and return + persist state."""
    llm = _make_model(use_real)
    state = build_insight_node(llm, output_dir="reports")(fixtures.healthy_state())
    chat.save_report_state(state, SAMPLE_STATE_PATH)
    return state


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("Data Analyst Chatbot")
    st.caption("Answers are grounded only in the generated report.")

    use_real = st.toggle(
        "Use real OpenAI", value=False,
        help="Requires OPENAI_API_KEY. Off = deterministic built-in demo model.",
    )
    if use_real and not os.getenv("OPENAI_API_KEY"):
        st.warning("OPENAI_API_KEY not set - falling back to the built-in model.")
        use_real = False

    source = st.radio(
        "Report source",
        ["Generate sample report", "Upload report_state.json"],
    )

    context: str | None = None
    state: Dict[str, Any] = {}

    if source == "Generate sample report":
        if st.button("Generate report", type="primary"):
            with st.spinner("Running profiler → analysis → insight → report..."):
                state = _generate_sample(use_real)
            st.session_state["state"] = state
            st.session_state["context"] = chat.build_context(state)
        if "context" in st.session_state:
            context = st.session_state["context"]
            state = st.session_state.get("state", {})
    else:
        uploaded = st.file_uploader("Upload report_state.json", type=["json"])
        if uploaded is not None:
            state = json.loads(uploaded.read().decode("utf-8"))
            st.session_state["state"] = state
            st.session_state["context"] = chat.build_context(state)
        if "context" in st.session_state:
            context = st.session_state["context"]

    if state:
        st.divider()
        st.caption(
            f"Report: **{state.get('report_status', '?')}** · "
            f"insights: {len(state.get('insights', []))} · "
            f"charts: {len(state.get('generated_files', []))}"
        )
        st.download_button(
            "Download report_state.json",
            data=json.dumps(state, indent=2, default=str),
            file_name="report_state.json",
        )


# ---------------------------------------------------------------------------
# Chat pane
# ---------------------------------------------------------------------------

st.title("Ask the Report")
st.caption(
    "Questions are answered strictly from the report content. "
    "Off-report questions get an honest 'not in this report'."
)

if not context:
    st.info(
        "No report loaded yet. Use the sidebar to **generate** the sample "
        "report (no API key needed) or **upload** a report_state.json."
    )
    st.stop()

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": "Report loaded. What would you like to know about it?",
        }
    ]

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Ask about the report..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    model = _make_model(use_real)
    history: List[Dict[str, str]] = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
        if m["role"] != "system"
    ]

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = chat.answer(model, prompt, st.session_state["context"], history)
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})