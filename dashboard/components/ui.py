"""Shared visual language and reusable dashboard components."""
import streamlit as st


def apply_theme() -> None:
    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    .stApp { background: #071326; color: #eef3fb; font-family: 'DM Sans', sans-serif; }
    section[data-testid="stSidebar"] { background: #0a192d; border-right: 1px solid #1a2d47; }
    .block-container { max-width: 1480px; padding-top: 1.4rem; padding-bottom: 3rem; }
    h1,h2,h3 { font-family: 'Manrope', sans-serif; letter-spacing: -.025em; color: #f5f7fb; }
    [data-testid="stMetric"] { background: #0d1d34; border: 1px solid #1a2e49; padding: 1rem 1.1rem; border-radius: 14px; }
    [data-testid="stMetricLabel"] { color: #9aabc2; }
    [data-testid="stMetricValue"] { color: #f4f7fc; font-family: 'Manrope', sans-serif; }
    .hero { background: linear-gradient(115deg,#102744,#10203a 58%,#251c39); border: 1px solid #233d5c; padding: 1.6rem 1.8rem; border-radius: 20px; margin: .4rem 0 1.4rem; }
    .hero h1 { margin: .2rem 0 .4rem; }
    .hero p { color: #bdcadd; }
    .eyebrow { color: #ff799e; font-weight: 700; text-transform: uppercase; font-size: .72rem; letter-spacing: .14em; }
    @media (max-width: 800px) { .block-container { padding-left: 1rem; padding-right: 1rem; } }
    </style>""", unsafe_allow_html=True)


def page_header(title: str, description: str) -> None:
    st.title(title)
    st.caption(description)


def empty_data_notice() -> None:
    st.info("No source data is available in `data/raw/`. Validated submission artifacts remain viewable where present.")


def read_markdown(path) -> None:
    if path.is_file():
        st.markdown(path.read_text(encoding="utf-8"))
    else:
        st.info("This report is not available in the current project package.")
