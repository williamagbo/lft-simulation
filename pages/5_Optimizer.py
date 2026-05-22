import io
import streamlit as st
import plotly.express as px
from simulation_engine import simulate_input_data, run_optimization_grid

st.set_page_config(page_title="Optimiser", layout="wide")

st.title("Resource Optimiser")
st.markdown("Grid search across 18 resource configurations to minimise total cost.")

if "opt_results" not in st.session_state:
    st.session_state.opt_results = None

default_rate = 30.0
if "fitted_params" in st.session_state:
    default_rate = float(st.session_state.fitted_params.get("arrival_rate_per_hour", 30.0))

# --- Inputs ---
col1, col2 = st.columns(2)
with col1:
    ward_beds = st.number_input("Ward beds", min_value=10, max_value=1000, value=150)
    occupancy = st.slider("Ward occupancy (%)", min_value=50, max_value=99, value=85)
    revenue = st.number_input("Revenue per admission (GHS)", min_value=100, max_value=10000, value=2500)
with col2:
    sla_target = st.number_input("SLA target TAT (minutes)", min_value=10, max_value=1440, value=60)
    cost_an = st.number_input("Analyser operating cost (GHS/hr)", min_value=1, max_value=500, value=50)
    cost_tech = st.number_input("Staff hourly rate (GHS/hr)", min_value=1, max_value=500, value=20)

n_reps = st.number_input("Replications per configuration", min_value=1, max_value=500, value=10, step=1)
n_samples = st.number_input("Samples to simulate", min_value=50, max_value=2000, value=300, step=50)

st.info("Pw = 15% (blocked admission probability — from published paper)")

run_btn = st.button("Run Optimisation", type="primary")

if run_btn:
    df_input = simulate_input_data(n=n_samples, arrival_rate_per_hour=default_rate)
    pw = 0.15
    with st.spinner("Running optimisation grid (18 configurations × replications)..."):
        results = run_optimization_grid(
            df_input,
            cost_tech=cost_tech,
            cost_an=cost_an,
            target_tat=sla_target,
            revenue_per_admission=revenue,
            pw=pw,
            n_reps=int(n_reps),
        )
    st.session_state.opt_results = results

if st.session_state.opt_results is not None:
    results = st.session_state.opt_results

    best = results.loc[results["Total_Cost"].idxmin()]
    st.success(
        f"Optimal: {int(best['Phleb'])} Ph | {int(best['Analyzer'])} An | {int(best['Tech'])} Te "
        f"— Total Cost: GHS {best['Total_Cost']:.2f}"
    )

    # Scatter: P95 TAT vs Total Cost
    results["Config"] = results.apply(
        lambda r: f"P{int(r.Phleb)} A{int(r.Analyzer)} T{int(r.Tech)}", axis=1
    )
    fig = px.scatter(
        results, x="P95_TAT", y="Total_Cost",
        color="SLA_Compliance",
        color_continuous_scale="plasma",
        hover_data=["Config", "Labor_Cost", "Delay_Penalty"],
        title="Cost Frontier — P95 TAT vs Total Cost",
        labels={"P95_TAT": "P95 TAT (minutes)", "Total_Cost": "Total Cost (GHS)",
                "SLA_Compliance": "SLA Compliance (%)"},
        text="Config",
    )
    fig.add_vline(x=sla_target, line_dash="dash", line_color="red",
                  annotation_text=f"SLA target ({sla_target} min)")
    fig.update_traces(textposition="top center")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(results.drop(columns="Config").sort_values("Total_Cost"), use_container_width=True)

    def to_csv(df):
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        return buf.getvalue().encode("utf-8")

    st.download_button("Download Optimisation Grid CSV",
                       data=to_csv(results),
                       file_name="optimisation_grid.csv",
                       mime="text/csv")
