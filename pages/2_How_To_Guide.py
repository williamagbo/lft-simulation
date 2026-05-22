import streamlit as st

st.set_page_config(page_title="How To Guide", layout="wide")

st.title("How To Guide")
st.markdown(
    "This guide explains how to use each section of the LFT Lab Simulation dashboard."
)

with st.expander("1 — About Page", expanded=False):
    st.markdown(
        """
        The **About** page loads on startup and displays a summary of the real operational data
        collected at St. Michael's Hospital, Pramso. Key statistics include:
        - Total records and outlier removal
        - Date range of observations
        - Empirical TAT percentiles (Median, P95, P99)
        - Estimated arrival rate (samples/hour)

        These values are automatically derived from `data/lft_records.csv` using the P95
        outlier-removal rule described in the published paper.
        """
    )

with st.expander("2 — Queuing Theory (M/M/c)", expanded=False):
    st.markdown(
        """
        The **Queuing Theory** page applies the **Erlang-C formula** to estimate theoretical wait
        times under different resource configurations.

        **Inputs:**
        - **Arrival rate** (λ) — samples/hour
        - **Service rate** (μ) — samples/hour per machine
        - **Number of analysers** (c) — 1 to 3

        **Outputs:**
        - Server utilisation ρ = λ / (c × μ)
        - Erlang-C probability C(c, ρ)
        - Average wait time in queue Wq

        **Warning:** The system displays an instability warning if λ ≥ μ × c.
        Use this page to get a quick theoretical baseline before running the full DES.
        """
    )

with st.expander("3 — DES Simulation", expanded=False):
    st.markdown(
        """
        The **DES Simulation** page runs a stochastic multi-replication simulation of the full
        LFT workflow.

        **Workflow stages modelled:**
        1. Patient/sample **arrives** (exponential inter-arrival times)
        2. **Phlebotomist** collects specimen (Normal distribution, ~6 min)
        3. Sample **waits for batch** (10 samples OR 20 min timeout) then **centrifuge spins** (12 min)
        4. Each sample proceeds to **biochemical analyser** (12 min)
        5. **Technician** validates and dispatches result (Normal, ~4 min)

        **Sidebar inputs:**
        - Sample size, arrival rate, STAT share
        - Number of replications (1–500)
        - Resource counts: phlebotomists, analysers, technicians
        - Batch size, SLA target

        **Outputs:**
        - P95 TAT, average completed samples, SLA compliance %
        - Histogram of P95 TAT across replications
        - Resource utilisation bar chart
        - Downloadable CSVs

        **Validation note:** Under the baseline config (1 phlebotomist, 1 analyser, 2 technicians)
        with 300 samples at 30/hour, the simulation should produce a P95 TAT close to ~847 minutes,
        matching the published paper. A warning appears if the deviation exceeds 15%.
        """
    )

with st.expander("4 — Optimiser", expanded=False):
    st.markdown(
        """
        The **Optimiser** page runs a grid search across 18 resource configurations:
        - Phlebotomists: 1, 2, or 3
        - Analysers: 1 or 2
        - Technicians: 1, 2, or 3

        For each configuration, it runs the specified number of replications and computes:
        - **P95 TAT** (mean across replications)
        - **Labour cost** (staff + equipment per day)
        - **Delay penalty** (revenue lost from TAT exceeding SLA target)
        - **Total cost** = Labour cost + Delay penalty
        - **SLA compliance %** (% of replications where P95 TAT ≤ target)

        **Inputs:**
        - Ward beds, occupancy %, revenue per admission (GHS)
        - SLA target (minutes), staff/equipment hourly costs
        - Replications per configuration

        **Output:** A scatter plot of P95 TAT vs Total Cost, coloured by SLA compliance,
        plus a sortable table of all 18 configurations.

        The **optimal configuration** is highlighted as the lowest Total Cost configuration.
        """
    )

with st.expander("5 — Data Analysis", expanded=False):
    st.markdown(
        """
        The **Data Analysis** page provides three experiment suites for deeper analytical insight:

        ### Single-Factor Experiments
        Tests the impact of adding one unit of each resource type (phlebotomist, analyser,
        technician) relative to a baseline configuration. Useful for identifying the most
        impactful marginal investment.

        ### Robustness Testing
        Tests the optimal configuration against four different arrival rates (15, 30, 45, 60
        samples/hour) to assess performance stability under varying demand conditions.

        ### Sensitivity Analysis
        Tests seven scenarios varying cost, arrival rate (λ), and service time by ±15–20%
        to assess how robust the optimal decision is to uncertainty in input parameters.

        All sections have **Download CSV** buttons for TAT and utilisation data.
        """
    )
