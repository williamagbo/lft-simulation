import streamlit as st
from data_utils import load_raw_data, clean_data, fit_parameters

st.set_page_config(
    page_title="LFT Lab Simulation",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load data once at startup
if "lft_data" not in st.session_state:
    try:
        raw = load_raw_data("data/lft_records.csv")
        df_clean, summary = clean_data(raw)
        params = fit_parameters(df_clean)
        st.session_state.lft_data = df_clean
        st.session_state.data_summary = summary
        st.session_state.fitted_params = params
        st.session_state.data_loaded = True
    except Exception as e:
        st.session_state.data_loaded = False
        st.session_state.data_error = str(e)
        st.session_state.fitted_params = {
            "arrival_rate_per_hour": 30.0,
            "median_tat": 120.0,
            "p95_tat": 847.0,
            "p99_tat": 1200.0,
            "date_range": ("N/A", "N/A"),
            "daily_volume": 33.0,
        }

st.sidebar.title("LFT Lab Simulation")
st.sidebar.markdown("Navigate using the pages above.")
st.markdown("# Welcome")
st.markdown("Use the sidebar to navigate to a page.")
