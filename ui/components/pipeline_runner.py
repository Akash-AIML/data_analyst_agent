"""Tab 1 component: Handles dataset selection, file uploading, and non-blocking pipeline execution."""

import os
import streamlit as st
from ui.services.pipeline_service import (
    save_uploaded_csv,
    run_pipeline,
    get_available_samples,
)


def render_pipeline_runner():
    """Render Tab 1: Ingestion & Pipeline Runner interface."""
    st.header("🚀 Run Autonomous Data Analysis")
    st.write("Select a sample dataset or upload your own CSV file to trigger the multi-agent analysis pipeline.")

    col1, col2 = st.columns([1, 1])

    samples = get_available_samples()
    uploaded_path = None

    with col1:
        st.subheader("📁 Upload CSV File")
        uploaded_file = st.file_uploader(
            "Drag and drop a CSV file here",
            type=["csv"],
            help="Maximum file size: 50MB. File names are automatically sanitized.",
        )
        if uploaded_file is not None:
            try:
                uploaded_path = save_uploaded_csv(uploaded_file)
                st.success(f"Uploaded: **{uploaded_file.name}** ({len(uploaded_file.getvalue()) / 1024:.1f} KB)")
            except ValueError as val_err:
                st.error(str(val_err))

    with col2:
        st.subheader("📊 Choose Sample Dataset")
        combined_options = {}
        if uploaded_path and os.path.exists(uploaded_path):
            upload_key = f"📎 Uploaded: {uploaded_file.name}"
            combined_options[upload_key] = uploaded_path
        
        combined_options.update(samples)

        selected_sample = st.selectbox(
            "Available Sample Datasets",
            options=list(combined_options.keys()),
            index=0 if combined_options else None,
        )
        if selected_sample:
            target_csv_path = combined_options[selected_sample]
            st.info(f"Selected: **{selected_sample}**")

    st.markdown("---")

    if target_csv_path and os.path.exists(target_csv_path):
        st.subheader("⚡ Execute Pipeline")
        st.write(f"Target CSV: `{target_csv_path}`")

        if st.button("🚀 Start Multi-Agent Pipeline", type="primary", use_container_width=True):
            status_container = st.status("Pipeline Execution in Progress...", expanded=True)

            try:
                status_container.write("🔍 **Stage 1: Profiler Agent** — Ingesting dataset and generating profiling report...")
                # Run complete graph pipeline
                final_state = run_pipeline(target_csv_path)

                status_container.write("🧠 **Stage 2: Analysis Planner** — Decomposing dataset into execution plan...")
                status_container.write("⚡ **Stage 3: Analysis Executor** — Executing Python code & generating plots...")
                status_container.write("🔄 **Stage 4: Reflector Agent** — Reviewing plan completeness...")
                status_container.write("💡 **Stage 5: Insight Agent** — Validating evidence & compiling executive report...")

                report_status = final_state.get("report_status", "unknown")
                if report_status in ("ok", "degraded"):
                    status_container.update(
                        label=f"✅ Pipeline Completed! Report Status: {report_status.upper()}",
                        state="complete",
                        expanded=False,
                    )
                    st.success("Pipeline run finished successfully! View results in the tabs above.")
                else:
                    status_container.update(
                        label="⚠️ Pipeline Completed with Degraded/Failed Output",
                        state="error",
                        expanded=True,
                    )
                    st.warning("Pipeline finished with warnings. Inspect the diagnostics tab for details.")

                # Persist final state in Streamlit session state
                st.session_state["state"] = final_state
                st.session_state["report_status"] = report_status
                st.rerun()


            except Exception as exc:
                status_container.update(
                    label=f"❌ Pipeline Execution Failed: {exc}",
                    state="error",
                    expanded=True,
                )
                st.error(f"Execution Error: {exc}")
    else:
        st.info("Please upload a CSV or select a sample dataset above to enable execution.")
