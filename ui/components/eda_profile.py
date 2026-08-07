"""Tab 2 component: Renders dataset metrics summary cards and embedded interactive ydata-profiling HTML report."""

import streamlit as st
import streamlit.components.v1 as components
from ui.services.pipeline_service import read_html_report


def render_eda_profile(state: dict):
    """Render Tab 2: Dataset Profile & EDA Summary."""
    st.header("📊 Dataset Profile & Exploratory Data Analysis")

    if not state or "profile" not in state or not state["profile"]:
        st.info("No active dataset profile loaded. Run the pipeline in Tab 1 first.")
        return

    profile = state["profile"]

    # --- Top Metric Cards ---
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{profile.get('rows', 0):,}</div>
                <div class="metric-label">Total Rows</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{profile.get('columns', 0)}</div>
                <div class="metric-label">Columns</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{len(profile.get('numeric_columns', []))}</div>
                <div class="metric-label">Numeric Cols</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{len(profile.get('categorical_columns', []))}</div>
                <div class="metric-label">Categorical Cols</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col5:
        missing_count = sum(profile.get("missing_values", {}).values())
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{missing_count}</div>
                <div class="metric-label">Missing Values</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Column Distribution Overview ---
    st.subheader("📋 Detected Columns Classification")
    num_cols = profile.get("numeric_columns", [])
    cat_cols = profile.get("categorical_columns", [])
    dt_cols = profile.get("datetime_columns", [])
    id_cols = profile.get("id_columns", [])

    col_a, col_b = st.columns(2)
    with col_a:
        st.write(f"**Numeric Columns ({len(num_cols)})**: " + (", ".join(f"`{c}`" for c in num_cols) if num_cols else "*None*"))
        st.write(f"**Categorical Columns ({len(cat_cols)})**: " + (", ".join(f"`{c}`" for c in cat_cols) if cat_cols else "*None*"))
    with col_b:
        st.write(f"**DateTime Columns ({len(dt_cols)})**: " + (", ".join(f"`{c}`" for c in dt_cols) if dt_cols else "*None*"))
        st.write(f"**Identifier Columns ({len(id_cols)})**: " + (", ".join(f"`{c}`" for c in id_cols) if id_cols else "*None*"))

    st.markdown("---")

    # --- Embedded HTML Profiling Report ---
    st.subheader("🌐 Interactive Dataset Profiling Report")
    report_path = state.get("profile_report_path")
    html_content = read_html_report(report_path)

    if html_content:
        st.caption(f"Loaded HTML report from: `{report_path}`")
        components.html(html_content, height=800, scrolling=True)
    else:
        st.warning("No interactive HTML profile report available on disk.")
