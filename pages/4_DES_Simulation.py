import io
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from simulation_engine import simulate_input_data, run_des, summarise_kpis

st.set_page_config(page_title="DES Simulation", layout="wide")

st.title("Discrete-Event Simulation")
st.markdown("Run multi-replication stochastic simulation of the LFT lab workflow.")

# Default arrival rate
default_rate = 30.0
if "fitted_params" in st.session_state:
    default_rate = float(st.session_state.fitted_params.get("arrival_rate_per_hour", 30.0))

# Initialise session state
for key in ["des_results", "des_tat_df", "des_util_df"]:
    if key not in st.session_state:
        st.session_state[key] = None

# --- Sidebar ---
with st.sidebar:
    st.header("Simulation Parameters")
    n_samples = st.number_input("Number of samples", min_value=10, max_value=2000, value=300, step=10)
    arrival_rate = st.slider("Arrival rate (samples/hr)", min_value=5, max_value=120,
                             value=int(default_rate), step=1)
    stat_share = st.slider("STAT share", min_value=0.0, max_value=0.5, value=0.15, step=0.01)
    n_reps = st.number_input("Replications", min_value=1, max_value=500, value=10, step=1)
    st.subheader("Resources")
    n_phleb = st.number_input("Phlebotomists", min_value=1, max_value=10, value=1)
    n_analyzers = st.number_input("Analysers", min_value=1, max_value=5, value=1)
    n_tech = st.number_input("Technicians", min_value=1, max_value=10, value=2)
    st.subheader("Process Parameters")
    batch_size = st.number_input("Batch size", min_value=1, max_value=30, value=10)
    target_tat = st.number_input("SLA target TAT (min)", min_value=10, max_value=1440, value=60)

run_btn = st.button("Run Descriptive Simulation", type="primary")

if run_btn:
    df_input = simulate_input_data(n=n_samples, arrival_rate_per_hour=arrival_rate,
                                   stat_share=stat_share)
    config = dict(
        n_phleb=n_phleb, n_centrifuge=1, n_analyzer=n_analyzers, n_tech=n_tech,
        batch_size=batch_size,
    )

    progress = st.progress(0, text="Running replications...")
    tat_rows, util_rows = [], []

    for i in range(1, int(n_reps) + 1):
        result = run_des(df_input, **config, seed=i)
        kpis = summarise_kpis(result)
        t_row = kpis["tat"].copy()
        t_row["replication"] = i
        tat_rows.append(t_row)
        u_row = kpis["utilization"].copy()
        u_row["replication"] = i
        util_rows.append(u_row)
        progress.progress(i / n_reps, text=f"Replication {i}/{n_reps}")

    progress.empty()

    tat_df = pd.concat(tat_rows, ignore_index=True)
    util_df = pd.concat(util_rows, ignore_index=True)

    st.session_state.des_tat_df = tat_df
    st.session_state.des_util_df = util_df

    # Validation check vs paper
    median_p95 = tat_df["p95_tat"].median()
    paper_p95 = 847.03
    deviation = abs(median_p95 - paper_p95) / paper_p95
    if n_phleb == 1 and n_analyzers == 1 and n_tech == 2 and deviation > 0.15:
        st.warning(
            f"Validation note: Simulated P95 TAT ({median_p95:.1f} min) deviates "
            f"{deviation*100:.1f}% from the paper's reported value ({paper_p95} min)."
        )

# --- Display results ---
if st.session_state.des_tat_df is not None:
    tat_df = st.session_state.des_tat_df
    util_df = st.session_state.des_util_df

    p95_median = tat_df["p95_tat"].median()
    avg_completed = tat_df["n_completed"].mean()
    sla_pct = (tat_df["p95_tat"] <= target_tat).mean() * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("P95 TAT (median across reps)", f"{p95_median:.1f} min")
    c2.metric("Avg Completed Samples", f"{avg_completed:.0f}")
    c3.metric("SLA Compliance", f"{sla_pct:.1f}%")

    # Plot 1: Histogram of P95 TAT
    fig1 = px.histogram(
        tat_df, x="p95_tat", nbins=30,
        title="Distribution of P95 TAT Across Replications",
        labels={"p95_tat": "P95 TAT (minutes)"},
        color_discrete_sequence=["#1f77b4"],
    )
    fig1.add_vline(x=target_tat, line_dash="dash", line_color="red",
                   annotation_text=f"SLA target ({target_tat} min)")
    st.plotly_chart(fig1, use_container_width=True)

    # Plot 2: Resource utilisation
    util_mean = util_df.groupby("resource")["utilization"].mean().reset_index()
    util_mean["utilization_pct"] = util_mean["utilization"] * 100
    fig2 = px.bar(
        util_mean, x="utilization_pct", y="resource", orientation="h",
        title="Mean Resource Utilisation (%)",
        labels={"utilization_pct": "Utilisation (%)", "resource": "Resource"},
        color_discrete_sequence=["#2ca02c"],
    )
    fig2.update_layout(xaxis_range=[0, 100])
    st.plotly_chart(fig2, use_container_width=True)

    # Downloads
    def to_csv(df):
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        return buf.getvalue().encode("utf-8")

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button("Download TAT CSV", data=to_csv(tat_df),
                           file_name="baseline_tat.csv", mime="text/csv")
    with col_dl2:
        st.download_button("Download Utilisation CSV", data=to_csv(util_df),
                           file_name="baseline_utilisation.csv", mime="text/csv")
