"""Tab 5 component: Pipeline execution logs, task plan breakdown, thinking narrative, and raw state inspection."""

import json
import streamlit as st


def render_diagnostics(state: dict):
    """Render Tab 5: Agent Thinking & Diagnostics."""
    st.header("🛠️ Agent Thinking & System Diagnostics")

    if not state:
        st.info("No active pipeline state loaded. Run the pipeline in Tab 1 first.")
        return

    # --- Section 1: Analysis Plan Breakdown ---
    st.subheader("📋 Analysis Plan Tasks")
    analysis_plan = state.get("analysis_plan", [])
    if analysis_plan:
        for task in analysis_plan:
            t_id = task.get("task_id")
            t_name = task.get("task_name")
            t_desc = task.get("description", "")
            t_status = task.get("status", "unknown")
            t_code = task.get("code")

            with st.expander(f"Task #{t_id}: {t_name} — Status: {t_status.upper()}"):
                st.write(f"**Description**: {t_desc}")
                st.write(f"**Attempts**: {task.get('attempts', 0)} / {task.get('max_retries', 3)}")
                if t_code:
                    st.markdown("**Generated Code**:")
                    st.code(t_code, language="python")
                if task.get("last_error"):
                    st.error(f"Last Error: {task['last_error']}")
    else:
        st.info("No analysis plan tasks found in state.")

    st.markdown("---")

    # --- Section 2: Thinking & Reflection Narrative ---
    st.subheader("🧠 Thinking Logs & Reflection Notes")
    thinking_logs = state.get("thinking_log", [])
    reflection_notes = state.get("reflection_notes", [])

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Agent Thinking Log**:")
        if thinking_logs:
            for line in thinking_logs:
                st.write(f"• `{line}`")
        else:
            st.info("No thinking logs recorded.")

    with col_b:
        st.markdown("**Reflector Agent Notes**:")
        if reflection_notes:
            for note in reflection_notes:
                st.write(f"• {note}")
        else:
            st.info("No reflection notes recorded.")

    st.markdown("---")

    # --- Section 3: Error Log ---
    st.subheader("⚠️ Pipeline Error Log")
    error_log = state.get("error_log", [])
    if error_log:
        for err in error_log:
            st.error(err)
    else:
        st.success("No system errors recorded during this run.")

    st.markdown("---")

    # --- Section 4: Raw AgentState JSON Inspector ---
    st.subheader("🔍 Raw AgentState Inspector")
    with st.expander("View Full AgentState JSON"):
        st.json(state)
