"""Tab 3 component: Executive insights, recommendations, chart image grid gallery, and report downloads."""

import os
import json
import streamlit as st


def render_insights_gallery(state: dict):
    """Render Tab 3: Executive Insights & Visualizations."""
    st.header("💡 Executive Insights & Generated Visualizations")

    if not state:
        st.info("No active pipeline state loaded. Run the pipeline in Tab 1 first.")
        return

    insights = state.get("insights", [])
    recommendations = state.get("recommendations", [])
    generated_files = state.get("generated_files", [])

    # --- Top Status Summary ---
    status = state.get("report_status", "unknown")
    st.markdown(
        f"""
        <div style="margin-bottom: 20px;">
            <span>Report Validation Status: </span>
            <span class="status-badge status-{status}">{status}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Verified Insights ---
    st.subheader(f"🔍 Verified Insights ({len(insights)})")
    if insights:
        for idx, item in enumerate(insights, start=1):
            title = item.get("title", f"Insight #{idx}")
            body = item.get("body", "")
            metric = item.get("metric", "")
            val = item.get("value", "")
            conf = item.get("confidence", 1.0)
            evidence = item.get("evidence", "")

            st.markdown(
                f"""
                <div class="insight-card">
                    <div class="insight-title">#{idx} {title}</div>
                    <div class="insight-body">{body}</div>
                    <div class="insight-meta">
                        <b>Metric:</b> {metric} | <b>Value:</b> {val} | <b>Confidence:</b> {conf * 100:.0f}% | <b>Evidence Citation:</b> {evidence}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("No verified insights generated for this dataset.")

    st.markdown("---")

    # --- Recommendations ---
    st.subheader(f"🎯 Actionable Recommendations ({len(recommendations)})")
    if recommendations:
        for idx, rec in enumerate(recommendations, start=1):
            st.markdown(
                f"""
                <div class="rec-card">
                    <b>Recommendation #{idx}:</b> {rec}
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("No recommendations derived.")

    st.markdown("---")

    # --- Generated Chart Images Gallery ---
    st.subheader("📈 Generated Analysis Visualizations")
    image_files = [f for f in generated_files if f.lower().endswith((".png", ".jpg", ".jpeg")) and os.path.exists(f)]

    if image_files:
        cols = st.columns(2)
        for idx, img_path in enumerate(image_files):
            col = cols[idx % 2]
            with col:
                st.image(img_path, caption=os.path.basename(img_path), use_container_width=True)
    else:
        st.info("No chart image files generated.")

    st.markdown("---")

    # --- Download Deliverables Section ---
    st.subheader("📥 Download Deliverables")
    dl_col1, dl_col2, dl_col3 = st.columns(3)

    report_html_path = state.get("report_path")
    pdf_path = state.get("pdf_path")

    with dl_col1:
        if report_html_path and os.path.exists(report_html_path):
            with open(report_html_path, "r", encoding="utf-8") as f:
                html_bytes = f.read().encode("utf-8")
            st.download_button(
                "📄 Download Executive HTML Report",
                data=html_bytes,
                file_name=os.path.basename(report_html_path),
                mime="text/html",
                use_container_width=True,
            )

    with dl_col2:
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            st.download_button(
                "📕 Download Executive PDF Report",
                data=pdf_bytes,
                file_name=os.path.basename(pdf_path),
                mime="application/pdf",
                use_container_width=True,
            )

    with dl_col3:
        state_json = json.dumps(state, indent=2, default=str)
        st.download_button(
            "💾 Download Complete AgentState (JSON)",
            data=state_json.encode("utf-8"),
            file_name="agent_state.json",
            mime="application/json",
            use_container_width=True,
        )
