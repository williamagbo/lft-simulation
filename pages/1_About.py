import streamlit as st
from data_utils import load_raw_data, clean_data, fit_parameters

st.set_page_config(page_title="About", layout="wide")

# Ensure data is loaded
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

st.title("Prescriptive Analytics for Laboratory Workflow Optimisation")
st.subheader("A Digital Twin of the LFT Workflow — St. Michael's Hospital, Pramso, Ghana")

if st.session_state.get("data_loaded"):
    summary = st.session_state.data_summary
    params = st.session_state.fitted_params
    st.info(
        f"""
**Real-World Data Summary**

- **Total records loaded (raw):** {summary['n_raw']:,}
- **Records after cleaning:** {summary['n_cleaned']:,}
- **Outliers removed:** {summary['n_removed']:,} ({summary['n_removed']/summary['n_raw']*100:.1f}%)
- **Date range:** {params['date_range'][0]} to {params['date_range'][1]}
- **Median TAT:** {summary['median_tat']:.1f} min
- **P95 TAT:** {params['p95_tat']:.1f} min
- **P99 TAT:** {params['p99_tat']:.1f} min
- **Estimated arrival rate:** {params['arrival_rate_per_hour']:.1f} samples/hour
- **Average daily volume:** {params['daily_volume']:.0f} samples/day
        """
    )
else:
    st.warning("Data file not found. Using hardcoded defaults. Please ensure `data/lft_records.csv` is present.")
    params = st.session_state.fitted_params

st.markdown(
    """
## About This Tool

This application is a **discrete-event simulation (DES) digital twin** of the Liver Function Test
(LFT) laboratory workflow at a district-level hospital in Ghana. It was developed as a prescriptive
analytics tool to identify bottlenecks and optimise resource configurations within the clinical
laboratory.

The simulation models the full specimen journey: phlebotomy → centrifugation (batch process) →
biochemical analysis → technician result validation. The original simulation engine was built in
**R simmer** as part of peer-reviewed research; this application is a Python reimplementation using
**SimPy**, deployable as a Streamlit Cloud application.

### Key Features
- **Queuing Theory** — Erlang-C M/M/c closed-form calculations
- **DES Simulation** — Multi-replication stochastic simulation with configurable resources
- **Optimiser** — Cost-frontier grid search across resource configurations
- **Data Analysis** — Single-factor experiments, robustness tests, sensitivity analysis

### Research Context
The simulation is parameterised from real operational data collected at St. Michael's Hospital,
Pramso, Ghana — a 150-bed district hospital. The goal is to support laboratory managers in making
evidence-based staffing and equipment decisions without disrupting live operations.

**Preprint:** [Agbo et al. (2025) — ResearchSquare](https://www.researchsquare.com/article/rs-9423252/v1)
    """
)

st.caption("Built with Python SimPy + Streamlit. Original simulation engine in R simmer.")
