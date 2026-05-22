import io
import streamlit as st
import pandas as pd
from simulation_engine import simulate_input_data, run_single_factor_experiments, \
    run_robustness_tests, run_sensitivity_analysis

st.set_page_config(page_title="Data Analysis", layout="wide")

st.title("Data Analysis")
st.markdown("Run structured experiments to understand workflow sensitivity and robustness.")

default_rate = 30.0
if "fitted_params" in st.session_state:
    default_rate = float(st.session_state.fitted_params.get("arrival_rate_per_hour", 30.0))

for key in ["sfe_results", "robust_results", "sens_results"]:
    if key not in st.session_state:
        st.session_state[key] = None


def to_csv(df):
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# Section 1: Single-Factor Experiments
# ---------------------------------------------------------------------------
with st.expander("1. Single-Factor Experiments", expanded=False):
    st.markdown(
        "Test the impact of adding one unit of each resource relative to a baseline configuration."
    )
    col1, col2, col3, col4 = st.columns(4)
    sfe_phleb = col1.number_input("Baseline phlebotomists", min_value=1, max_value=10,
                                   value=1, key="sfe_phleb")
    sfe_an = col2.number_input("Baseline analysers", min_value=1, max_value=5,
                                value=1, key="sfe_an")
    sfe_tech = col3.number_input("Baseline technicians", min_value=1, max_value=10,
                                  value=2, key="sfe_tech")
    sfe_reps = col4.number_input("Replications", min_value=1, max_value=500,
                                  value=10, key="sfe_reps")
    sfe_btn = st.button("Run Single-Factor Experiments", key="btn_sfe")

    if sfe_btn:
        df_input = simulate_input_data(n=300, arrival_rate_per_hour=default_rate)
        baseline_cfg = {
            "n_phleb": int(sfe_phleb),
            "n_analyzer": int(sfe_an),
            "n_tech": int(sfe_tech),
            "n_centrifuge": 1,
        }
        with st.spinner("Running single-factor experiments..."):
            res = run_single_factor_experiments(df_input, baseline_cfg, n_reps=int(sfe_reps))
        st.session_state.sfe_results = res

    if st.session_state.sfe_results is not None:
        tat_df = st.session_state.sfe_results["tat_data"]
        util_df = st.session_state.sfe_results["util_data"]
        summary = tat_df.groupby("experiment")["p95_tat"].agg(
            ["mean", "std", "min", "max"]
        ).round(2).reset_index()
        summary.columns = ["Experiment", "Mean P95 TAT", "Std", "Min", "Max"]
        st.dataframe(summary, use_container_width=True)
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button("Download TAT CSV", data=to_csv(tat_df),
                               file_name="sfe_tat.csv", mime="text/csv", key="dl_sfe_tat")
        with col_dl2:
            st.download_button("Download Utilisation CSV", data=to_csv(util_df),
                               file_name="sfe_util.csv", mime="text/csv", key="dl_sfe_util")


# ---------------------------------------------------------------------------
# Section 2: Robustness Testing
# ---------------------------------------------------------------------------
with st.expander("2. Robustness Testing", expanded=False):
    st.markdown(
        "Test the optimal configuration against different arrival rates (15, 30, 45, 60 samples/hr)."
    )
    col1, col2, col3, col4 = st.columns(4)
    rob_phleb = col1.number_input("Optimal phlebotomists", min_value=1, max_value=10,
                                   value=3, key="rob_phleb")
    rob_an = col2.number_input("Optimal analysers", min_value=1, max_value=5,
                                value=2, key="rob_an")
    rob_tech = col3.number_input("Optimal technicians", min_value=1, max_value=10,
                                  value=2, key="rob_tech")
    rob_reps = col4.number_input("Replications", min_value=1, max_value=500,
                                  value=10, key="rob_reps")
    rob_btn = st.button("Run Robustness Tests", key="btn_rob")

    if rob_btn:
        optimal_cfg = {
            "n_phleb": int(rob_phleb),
            "n_analyzer": int(rob_an),
            "n_tech": int(rob_tech),
            "n_centrifuge": 1,
        }
        with st.spinner("Running robustness tests across arrival rates..."):
            res = run_robustness_tests(optimal_cfg, arrival_rates=[15, 30, 45, 60],
                                       n_samples=300, n_reps=int(rob_reps))
        st.session_state.robust_results = res

    if st.session_state.robust_results is not None:
        tat_df = st.session_state.robust_results["tat_data"]
        util_df = st.session_state.robust_results["util_data"]
        summary = tat_df.groupby("lambda")["p95_tat"].agg(
            ["mean", "std", "min", "max"]
        ).round(2).reset_index()
        summary.columns = ["Arrival Rate (λ)", "Mean P95 TAT", "Std", "Min", "Max"]
        st.dataframe(summary, use_container_width=True)
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button("Download TAT CSV", data=to_csv(tat_df),
                               file_name="robustness_tat.csv", mime="text/csv", key="dl_rob_tat")
        with col_dl2:
            st.download_button("Download Utilisation CSV", data=to_csv(util_df),
                               file_name="robustness_util.csv", mime="text/csv", key="dl_rob_util")


# ---------------------------------------------------------------------------
# Section 3: Sensitivity Analysis
# ---------------------------------------------------------------------------
with st.expander("3. Sensitivity Analysis", expanded=False):
    st.markdown(
        "Test 7 scenarios varying cost, arrival rate, and service time by ±15–20%."
    )
    col1, col2, col3, col4 = st.columns(4)
    sens_phleb = col1.number_input("Optimal phlebotomists", min_value=1, max_value=10,
                                    value=3, key="sens_phleb")
    sens_an = col2.number_input("Optimal analysers", min_value=1, max_value=5,
                                 value=2, key="sens_an")
    sens_tech = col3.number_input("Optimal technicians", min_value=1, max_value=10,
                                   value=2, key="sens_tech")
    sens_reps = col4.number_input("Replications", min_value=1, max_value=500,
                                   value=10, key="sens_reps")
    sens_btn = st.button("Run Sensitivity Analysis", key="btn_sens")

    if sens_btn:
        df_input = simulate_input_data(n=300, arrival_rate_per_hour=default_rate)
        optimal_cfg = {
            "n_phleb": int(sens_phleb),
            "n_analyzer": int(sens_an),
            "n_tech": int(sens_tech),
            "n_centrifuge": 1,
            "t_collect_mean": 6,
            "t_analyze": 12,
            "t_validate_mean": 4,
            "arrival_rate_per_hour": default_rate,
        }
        with st.spinner("Running sensitivity analysis (7 scenarios)..."):
            res = run_sensitivity_analysis(df_input, optimal_cfg, n_reps=int(sens_reps))
        st.session_state.sens_results = res

    if st.session_state.sens_results is not None:
        tat_df = st.session_state.sens_results["tat_data"]
        util_df = st.session_state.sens_results["util_data"]
        summary = tat_df.groupby("scenario")["p95_tat"].agg(
            ["mean", "std", "min", "max"]
        ).round(2).reset_index()
        summary.columns = ["Scenario", "Mean P95 TAT", "Std", "Min", "Max"]
        st.dataframe(summary, use_container_width=True)
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button("Download TAT CSV", data=to_csv(tat_df),
                               file_name="sensitivity_tat.csv", mime="text/csv", key="dl_sens_tat")
        with col_dl2:
            st.download_button("Download Utilisation CSV", data=to_csv(util_df),
                               file_name="sensitivity_util.csv", mime="text/csv", key="dl_sens_util")
