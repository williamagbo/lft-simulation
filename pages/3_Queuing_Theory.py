import streamlit as st
import math

st.set_page_config(page_title="Queuing Theory", layout="wide")

st.title("Queuing Theory — M/M/c Erlang-C")
st.markdown(
    "Compute theoretical queue metrics using the Erlang-C formula for a multi-server queue."
)

# Ensure fitted params available
default_rate = 30.0
if "fitted_params" in st.session_state:
    default_rate = float(st.session_state.fitted_params.get("arrival_rate_per_hour", 30.0))

col1, col2, col3 = st.columns(3)
with col1:
    lam = st.number_input(
        "Arrival rate λ (samples/hour)", min_value=1.0, max_value=500.0,
        value=default_rate, step=1.0
    )
with col2:
    mu = st.number_input(
        "Service rate μ (samples/hour per server)", min_value=1.0, max_value=500.0,
        value=60.0, step=1.0
    )
with col3:
    c = st.slider("Number of servers (c)", min_value=1, max_value=10, value=1)


def erlang_c(lam, mu, c):
    rho = lam / (c * mu)
    if rho >= 1.0:
        return None, None, rho  # unstable

    a = lam / mu  # traffic intensity

    # Numerator: (a^c / c!) * (1 / (1 - rho))
    numerator = (a ** c / math.factorial(c)) * (1.0 / (1.0 - rho))

    # Denominator: sum_{k=0}^{c-1} a^k / k!  +  numerator
    summation = sum(a ** k / math.factorial(k) for k in range(c))
    denominator = summation + numerator

    C = numerator / denominator

    # Average wait time in queue (hours) -> convert to minutes
    Wq_hours = C / (c * mu * (1.0 - rho))
    Wq_minutes = Wq_hours * 60.0

    return C, Wq_minutes, rho


C, Wq, rho = erlang_c(lam, mu, c)

if C is None:
    st.warning(
        f"⚠️ **Unstable system:** λ ({lam:.1f}) ≥ μ × c ({mu * c:.1f}). "
        "The queue grows without bound. Increase servers or reduce arrival rate."
    )
else:
    m1, m2, m3 = st.columns(3)
    m1.metric("Server Utilisation ρ", f"{rho * 100:.1f}%")
    m2.metric("Erlang-C Probability C(c,ρ)", f"{C:.4f}")
    m3.metric("Avg Wait in Queue Wq", f"{Wq:.2f} min")

    st.markdown("---")
    st.markdown("### Interpretation")
    st.markdown(
        f"""
- **Utilisation {rho*100:.1f}%** — each server is busy {rho*100:.1f}% of the time on average.
- **Erlang-C {C:.4f}** — probability that an arriving sample finds all {c} servers busy and must wait.
- **Average queue wait {Wq:.2f} minutes** — theoretical mean time a sample spends waiting
  before service begins (not including service time).

*Note: Erlang-C assumes Poisson arrivals, exponential service times, and infinite queue capacity.
The DES simulation relaxes these assumptions with empirical service-time distributions and
batch centrifugation.*
        """
    )
