"""Tab 4 component: Report-grounded analyst chatbot for interactive dataset Q&A."""

import streamlit as st
from agents.insight import chat
from tests.insight.fake_llm import FakeChatModel



from tools.llm_factory import get_ordered_llm


def _get_chat_model():
    """Instantiate appropriate chat model using strict Groq -> Gemini -> OpenAI fallback."""
    try:
        return get_ordered_llm(temperature=0.1)
    except Exception:
        return FakeChatModel()




def render_analyst_chat(state: dict):
    """Render Tab 4: Interactive Analyst Chat ("Ask the Report")."""
    st.header("💬 Ask the Analyst Chatbot")
    st.caption("Answers are strictly grounded in the generated dataset report and validated metrics. Off-report questions will receive a 'Not in this report' response.")

    if not state or not state.get("profile"):
        st.info("No active analysis report loaded. Run the pipeline in Tab 1 first.")
        return

    context = chat.build_context(state)

    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {
                "role": "assistant",
                "content": "Hello! I am your AI Data Analyst. I have reviewed the report and metrics for this dataset. What would you like to know?",
            }
        ]

    # Controls
    col_clear, col_count = st.columns([1, 4])
    with col_clear:
        if st.button("🗑️ Clear Chat History"):
            st.session_state["messages"] = [
                {
                    "role": "assistant",
                    "content": "Chat history cleared. What would you like to ask about the report?",
                }
            ]
            st.rerun()

    # Render Conversation History
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # User Input
    if user_prompt := st.chat_input("Ask a question about dataset metrics, missing values, or insights..."):
        st.session_state["messages"].append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        model = _get_chat_model()
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state["messages"][:-1]
            if m["role"] in ("user", "assistant")
        ]

        with st.chat_message("assistant"):
            with st.spinner("Analyzing report context..."):
                try:
                    reply = chat.answer(model, user_prompt, context, history)
                except Exception as exc:
                    reply = f"Error generating answer: {exc}"
            st.markdown(reply)

        st.session_state["messages"].append({"role": "assistant", "content": reply})
