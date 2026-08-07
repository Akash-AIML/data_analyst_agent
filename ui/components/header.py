"""Header component: injects custom CSS styling and renders top branding banner."""

import streamlit as st


def inject_custom_styles():
    """Inject modern dark-mode CSS styling, typography, and glassmorphism card aesthetics."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Top Banner Glassmorphism */
        .hero-banner {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%);
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-radius: 16px;
            padding: 24px 32px;
            margin-bottom: 28px;
        }

        .hero-title {
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(90deg, #38BDF8 0%, #818CF8 50%, #C084FC 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
        }

        .hero-subtitle {
            color: #94A3B8;
            font-size: 1.05rem;
            font-weight: 400;
        }

        /* Status Badge Pills */
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .status-ok {
            background-color: rgba(16, 185, 129, 0.15);
            color: #34D399;
            border: 1px solid rgba(52, 211, 153, 0.4);
        }
        .status-degraded {
            background-color: rgba(245, 158, 11, 0.15);
            color: #FBBF24;
            border: 1px solid rgba(251, 191, 36, 0.4);
        }
        .status-failed {
            background-color: rgba(239, 68, 68, 0.15);
            color: #F87171;
            border: 1px solid rgba(248, 113, 113, 0.4);
        }

        /* Glassmorphism Metric Cards */
        .metric-card {
            background: rgba(30, 41, 59, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 18px 20px;
            text-align: center;
        }
        .metric-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #F8FAFC;
        }
        .metric-label {
            font-size: 0.85rem;
            color: #94A3B8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 4px;
        }

        /* Insight Item Cards */
        .insight-card {
            background: rgba(15, 23, 42, 0.7);
            border-left: 4px solid #6366F1;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 14px;
        }
        .insight-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #F1F5F9;
            margin-bottom: 6px;
        }
        .insight-body {
            font-size: 0.95rem;
            color: #CBD5E1;
            line-height: 1.5;
        }
        .insight-meta {
            font-size: 0.8rem;
            color: #64748B;
            margin-top: 8px;
        }

        /* Recommendations Cards */
        .rec-card {
            background: rgba(30, 41, 59, 0.4);
            border-left: 4px solid #10B981;
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 10px;
            color: #E2E8F0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header():
    """Render top hero banner."""
    inject_custom_styles()
    st.markdown(
        """
        <div class="hero-banner">
            <div class="hero-title">🤖 AI Data Analyst Agent</div>
            <div class="hero-subtitle">Autonomous Multi-Agent Intelligence Pipeline • Profiler → Analysis → Insight Validation → Executive Reporting</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
