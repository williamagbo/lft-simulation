# Claude Code Brief: SimPy Migration of LFT Lab Simulation Dashboard

## Project Overview

Migrate an R `simmer`-based discrete-event simulation (DES) of a clinical laboratory LFT
workflow into a Python `SimPy` application with a multi-page Streamlit frontend. The
original app is a prescriptive analytics tool — a digital twin of a Liver Function Test
(LFT) workflow at a district-level hospital in Ghana — used to identify bottlenecks and
optimise resource configurations. The goal is a deployable Streamlit Cloud app suitable
for a data analyst portfolio.

**Preprint reference:** https://www.researchsquare.com/article/rs-9423252/v1

---

## File Structure to Create

```
lft_simulation/
├── app.py                        # Streamlit multi-page entry point
├── simulation_engine.py          # SimPy core (mirror of simulation_engine.R)
├── data_utils.py                 # Data loading, cleaning, parameter fitting
├── pages/
│   ├── 1_About.py
│   ├── 2_How_To_Guide.py
│   ├── 3_Queuing_Theory.py
│   ├── 4_DES_Simulation.py
│   ├── 5_Optimizer.py
│   └── 6_Data_Analysis.py
├── data/
│   └── lft_records.csv           # Raw data file (already provided)
└── requirements.txt
```

---

## Part 1 — `data_utils.py`

### Raw Data Profile

The file `data/lft_records.csv` contains:
- **1,615 rows** (matching the published paper's stated sample size)
- **3 columns:** `sample_collected_date_time`, `dispatch_date_time`, `tat_minutes`
- **Date range:** 25 June 2025 – 11 August 2025
- **Date format:** `DD/MM/YYYY H:MM` — single-digit hours have no leading zero (e.g.
  `8:37` not `08:37`)

### Critical Data Quality Issue — Outliers

The dataset contains extreme TAT outliers representing administrative holds (specimens
not processed for days), not genuine workflow delays. These must be removed before the
simulation is parameterised. Examples:

| TAT (minutes) | Approx. duration |
|---|---|
| 89,270 | ~62 days |
| 33,332 | ~23 days |
| 20,304 | ~14 days |
| 10,410 | ~7 days |

### Functions to Implement

#### `load_raw_data(filepath="data/lft_records.csv") -> pd.DataFrame`
- Parse both datetime columns using `pd.to_datetime` with `dayfirst=True` and
  `format='mixed'`
- Recompute `tat_minutes` from parsed timestamps to validate the raw column
- Return the raw DataFrame

#### `clean_data(df, upper_percentile=0.95) -> tuple[pd.DataFrame, dict]`
- Remove rows where `tat_minutes` exceeds the given percentile threshold
- Return tuple of `(df_clean, summary)` where summary is a dict:
  ```python
  {
    "n_raw": int,
    "n_cleaned": int,
    "n_removed": int,
    "p95_threshold": float,
    "median_tat": float,
    "mean_tat": float
  }
  ```

#### `fit_parameters(df_clean) -> dict`
Derive simulation defaults from the cleaned real data:
- **arrival_rate_per_hour**: median inter-arrival time in minutes across the full
  observation window, converted to samples/hour
- **TAT statistics**: median, P95, P99
- **date_range**: `(min_date, max_date)` as strings
- **daily_volume**: mean samples per day
- Return as a dict used to pre-populate Streamlit sidebar defaults

---

## Part 2 — `simulation_engine.py`

This is the core of the project. Translate all 10 functions from `simulation_engine.R`
into Python using SimPy. Each function is described in full below.

### 2.1 `simulate_input_data(n, arrival_rate_per_hour=30, stat_share=0.15, seed=1) -> pd.DataFrame`

- Set `numpy.random.seed(seed)` at start
- Generate inter-arrival times: `np.random.exponential(1 / rate_per_min, n)` where
  `rate_per_min = arrival_rate_per_hour / 60`
- `arrival_time = np.cumsum(inter_arrival_times)`
- Assign `urgency` as `"STAT"` or `"ROUTINE"` based on `stat_share` probability
- Return `pd.DataFrame` with columns: `id`, `arrival_time`, `urgency`

### 2.2 `run_des(...) -> dict`

**Signature:**
```python
run_des(
    df,
    n_phleb=2,
    n_centrifuge=1,
    n_analyzer=1,
    n_tech=1,
    t_collect_mean=6,
    t_collect_sd=2,
    t_spin=12,
    t_analyze=12,
    t_validate_mean=4,
    t_validate_sd=1.5,
    batch_size=10,
    batch_max_wait=20,
    seed=1
) -> dict
```

This is the core SimPy translation. The workflow is a strict serial pipeline per sample:

```
SEIZE phlebotomist
  → timeout(max(0.1, normal(t_collect_mean, t_collect_sd)))
  → RELEASE phlebotomist
  → JOIN BATCH (wait until batch_size samples accumulated OR batch_max_wait minutes elapsed)
  → SEIZE centrifuge → timeout(t_spin) → RELEASE centrifuge
  → SEPARATE (each sample resumes independently)
  → SEIZE analyzer → timeout(t_analyze) → RELEASE analyzer
  → SEIZE technician
  → timeout(max(0.1, normal(t_validate_mean, t_validate_sd)))
  → RELEASE technician
  → record end_time, mark finished=True
```

**Implementation notes:**

- Use `simpy.Environment()`
- Resources: `simpy.Resource(env, capacity=n)` for each of phleb, centrifuge, analyzer,
  tech
- **Batching is the most critical and complex part.** Implement using a shared
  `simpy.Container` or a custom accumulator pattern:
  - Samples queue into a shared list after releasing the phlebotomist
  - A batch fires when either `batch_size` samples have accumulated OR `batch_max_wait`
    minutes have elapsed since the first sample in the current batch arrived
  - The entire batch then seizes the centrifuge together, waits `t_spin`, releases, then
    each sample continues independently to the analyzer
  - Test this logic explicitly — it is the most common point of failure
- Set `numpy.random.seed(seed)` at the start of the function
- Run simulation until `max(df.arrival_time) + 480`
- Track per-sample: `name`, `start_time`, `end_time`, `finished` (bool)
- Track resource state at each event: `resource`, `time`, `server` (busy count),
  `queue` (waiting count), `capacity`, `system` (server + queue)

**Return:**
```python
{
    "arrivals": pd.DataFrame,   # one row per sample
    "resources": pd.DataFrame   # one row per resource-event timestamp
}
```

### 2.3 `summarise_kpis(sim_results) -> dict`

- Filter `arrivals` to `finished == True`
- Compute `tat = end_time - start_time`
- Return:
```python
{
    "tat": pd.DataFrame,          # single-row summary
    "utilization": pd.DataFrame,  # one row per resource
    "arrivals": pd.DataFrame      # full arrivals with tat column
}
```
TAT summary columns: `n_completed`, `mean_tat`, `sd_tat`, `p50_tat`, `p90_tat`,
`p95_tat`, `p99_tat`

Utilization columns: `resource`, `utilization` (= `mean(server / capacity)` over all
timesteps), `avg_queue`, `max_queue`, `avg_system`

### 2.4 `get_wait_decomposition(sim_results) -> pd.DataFrame`

- From per-resource arrival data, compute time spent at each stage per sample
- Return DataFrame with columns: `name`, `wait_phleb`, `wait_centrifuge`,
  `wait_analyzer`, `wait_tech`, `total_wait`

### 2.5 `extract_resource_utilization(sim_results, n_phleb, n_analyzer, n_tech, replication=1) -> pd.DataFrame`

- Compute per-resource: `utilization`, `avg_queue`, `max_queue`, `avg_system`
- Add config columns: `n_phleb`, `n_analyzer`, `n_tech`, `replication`
- Return DataFrame

### 2.6 `run_des_replications(df, n_reps=500, config: dict) -> pd.DataFrame`

- Loop `seed` from `1` to `n_reps`
- Call `run_des` with config values unpacked
- Collect TAT summary per replication
- Return concatenated DataFrame with `replication` column

### 2.7 `run_single_factor_experiments(df, baseline_config: dict, n_reps=100) -> dict`

Define exactly 4 experiment configs (change ONE resource at a time from baseline):

| Experiment name | Change |
|---|---|
| `Baseline` | No change |
| `A1_Phleb_Plus1` | `n_phleb + 1` |
| `A2_Analyzer_Plus1` | `n_analyzer + 1` |
| `A3_Tech_Plus1` | `n_tech + 1` |

- Run `n_reps` replications per experiment
- Return:
```python
{
    "tat_data": pd.DataFrame,   # with "experiment" column
    "util_data": pd.DataFrame   # with "experiment" column
}
```

### 2.8 `run_robustness_tests(optimal_config, arrival_rates=[15,30,45,60], n_samples=500, n_reps=100) -> dict`

- For each arrival rate in the list, generate a new `df` via `simulate_input_data`
- Run `n_reps` replications using `optimal_config`
- Return:
```python
{
    "tat_data": pd.DataFrame,   # with "lambda" column
    "util_data": pd.DataFrame   # with "lambda" column
}
```

### 2.9 `run_sensitivity_analysis(df, optimal_config, n_reps=100) -> dict`

Define exactly 7 scenarios:

| Scenario name | `cost_mult` | `lambda_mult` | `service_mult` |
|---|---|---|---|
| `Baseline` | 1.0 | 1.0 | 1.0 |
| `Cost_Minus20` | 0.8 | 1.0 | 1.0 |
| `Cost_Plus20` | 1.2 | 1.0 | 1.0 |
| `Lambda_Minus20` | 1.0 | 0.8 | 1.0 |
| `Lambda_Plus20` | 1.0 | 1.2 | 1.0 |
| `Service_Minus15` | 1.0 | 1.0 | 0.85 |
| `Service_Plus15` | 1.0 | 1.0 | 1.15 |

- Apply `lambda_multiplier` by regenerating df with `arrival_rate_per_hour = 30 *
  lambda_mult`
- Apply `service_multiplier` to `t_collect_mean`, `t_analyze`, `t_validate_mean`
- Return:
```python
{
    "tat_data": pd.DataFrame,   # with scenario, lambda_mult, service_mult, cost_mult columns
    "util_data": pd.DataFrame   # same extra columns
}
```

### 2.10 `run_optimization_grid(...) -> pd.DataFrame`

**Signature:**
```python
run_optimization_grid(
    df,
    cost_tech=20,
    cost_an=50,
    target_tat=60,
    revenue_per_admission=2500,
    pw=0.15,
    n_reps=100
) -> pd.DataFrame
```

- Grid: `n_phleb` in `[1,2,3]`, `n_analyzer` in `[1,2]`, `n_tech` in `[1,2,3]` → 18
  configurations total
- For each config run `n_reps` replications, collect `p95_tat` per replication
- Cost formulas:
  ```python
  labor_cost = (n_phleb + n_tech) * cost_tech + n_analyzer * cost_an
  rev_loss_per_min = (revenue_per_admission * pw) / 1440
  delay_penalty = max(0, mean_p95_tat - target_tat) * rev_loss_per_min * len(df)
  total_cost = labor_cost + delay_penalty
  sla_compliance = (count of reps where p95_tat <= target_tat) / n_reps * 100
  ```
- Return DataFrame with columns: `Phleb`, `Analyzer`, `Tech`, `P95_TAT`, `Labor_Cost`,
  `Delay_Penalty`, `Total_Cost`, `SLA_Compliance`

---

## Part 3 — Streamlit Pages

### `pages/1_About.py`

Load `data/lft_records.csv` at startup using `data_utils.py`. Display:

- Title: **"Prescriptive Analytics for Laboratory Workflow Optimisation"**
- Subtitle: *"A Digital Twin of the LFT Workflow — St. Michael's Hospital, Pramso, Ghana"*
- `st.info` block — **Real-World Data Summary** — showing:
  - Total records loaded (raw and after cleaning)
  - Records removed as outliers (n and %)
  - Date range of observations
  - Median TAT, P95 TAT, P99 TAT (from cleaned data)
  - Estimated arrival rate (samples/hour)
- Short paragraph explaining the research context (DES, prescriptive analytics, district
  hospital setting)
- Link to preprint: https://www.researchsquare.com/article/rs-9423252/v1
- `st.caption`: "Built with Python SimPy + Streamlit. Original simulation engine in R
  simmer."

### `pages/2_How_To_Guide.py`

Static page. Mirror the R Shiny how-to guide content, adapted for the Streamlit
navigation structure. Use `st.expander` sections for each tab's instructions.

### `pages/3_Queuing_Theory.py`

**Inputs (sidebar or columns):**
- Arrival rate — samples/hr (numeric input, default from `fit_parameters`)
- Service rate — samples/hr/machine (numeric input, default 60)
- Number of analysers (slider 1–3)

**Logic:**
Implement the **Erlang-C** M/M/c formula from scratch in Python — do not use an
external queueing library. Standard formula:

```
rho = lambda / (c * mu)
Erlang-C numerator = ((c * rho)^c / c!) * (1 / (1 - rho))
Erlang-C denominator = sum_{k=0}^{c-1} (c*rho)^k / k! + numerator
C(c, rho) = numerator / denominator
Wq = C(c, rho) / (c * mu * (1 - rho))   # avg wait time in queue (minutes)
```

**Display:**
- `st.metric` for Utilisation % and Theoretical Average Wait (minutes)
- `st.warning` if system is unstable (λ ≥ μ × c)

### `pages/4_DES_Simulation.py`

**Sidebar inputs:**
- n_samples (default 300)
- arrival_rate (slider 5–120, default from `fit_parameters`)
- stat_share (slider 0–0.5, default 0.15)
- n_reps (numeric, default 100, max 500)
- n_phleb (numeric, default 1)
- n_analyzers (numeric, default 1)
- n_tech (numeric, default 2)
- batch_size (numeric, default 10)
- target_tat (numeric, default 60, used for SLA line and compliance calc)

**Button:** `"Run Descriptive Simulation"`

**On run:**
- Execute replications with `st.progress` bar
- Store results in `st.session_state`

**Display:**
- Three `st.metric` cards: P95 TAT (95th percentile across reps), Avg Completed Samples,
  SLA Compliance %
- **Plot 1** (Plotly): Histogram of P95 TAT across replications, vertical dashed red
  line at `target_tat`
- **Plot 2** (Plotly): Horizontal bar chart of resource utilisation % for phleb,
  centrifuge, analyzer, tech
- Download buttons: Baseline TAT CSV, Baseline Utilisation CSV
  (use `io.StringIO` for in-memory generation — no file writes)

### `pages/5_Optimizer.py`

**Inputs:**
- Ward beds (default 150)
- Ward occupancy % (slider 50–99, default 85)
- Revenue per admission in GHS (default 2500)
- SLA target in minutes (default 60)
- Analyser operating cost GHS/hr (default 50)
- Staff hourly rate GHS/hr (default 20)
- Replications per configuration (default 100)

**Fixed value:** Display Pw = 15% (blocked admission probability) as `st.info`

**Button:** `"Run Optimisation"`

**On run:**
- Call `run_optimization_grid` with a `st.spinner`
- Store results in `st.session_state`

**Display:**
- `st.success` banner showing best config: e.g. `"Optimal: 3 Ph | 2 An | 2 Te — Total
  Cost: GHS 142.50"`
- **Plot** (Plotly scatter): P95 TAT (x-axis) vs Total Cost (y-axis), points coloured
  by SLA Compliance % using a plasma colour scale
- Vertical dashed red line at `target_tat`
- `st.dataframe` showing all 18 configurations, sortable
- Download button: Full optimisation grid CSV (in-memory)

### `pages/6_Data_Analysis.py`

Three `st.expander` sections:

#### Section 1: Single-Factor Experiments
- Baseline config inputs: n_phleb, n_analyzer, n_tech (defaults: 1, 1, 2)
- Replications input (default 100)
- Button: `"Run Single-Factor Experiments"`
- On run: call `run_single_factor_experiments`, store in `st.session_state`
- Display summary table of P95 TAT by experiment
- Download buttons: TAT CSV, Utilisation CSV

#### Section 2: Robustness Testing
- Optimal config inputs: n_phleb, n_analyzer, n_tech (defaults: 3, 2, 2)
- Replications input (default 100)
- Button: `"Run Robustness Tests"`
- Tests arrival rates: [15, 30, 45, 60] samples/hr
- Display summary table of P95 TAT by lambda
- Download buttons: TAT CSV, Utilisation CSV

#### Section 3: Sensitivity Analysis
- Optimal config inputs: n_phleb, n_analyzer, n_tech (defaults: 3, 2, 2)
- Replications input (default 100)
- Button: `"Run Sensitivity Analysis"`
- Display summary table of P95 TAT by scenario
- Download buttons: TAT CSV, Utilisation CSV

---

## Part 4 — `requirements.txt`

```
streamlit
simpy
numpy
pandas
plotly
scipy
```

---

## Part 5 — Critical Implementation Instructions

### 1. Batching logic (most complex part)

The centrifuge batch is the hardest SimPy construct to implement correctly. Samples must
genuinely wait for a batch to fill OR a timeout to expire before the centrifuge seizes.
This is not a simple `simpy.Resource` call.

Recommended approach:
```python
# After releasing phlebotomist, each sample process does:
batch_store.put(sample_id)           # add self to batch accumulator
yield batch_ready_event              # wait until batch fires
# Then proceed to seize centrifuge
```
Use a separate `batch_manager` process that monitors `batch_store`, fires the batch
event when count reaches `batch_size` OR when `batch_max_wait` minutes have elapsed
since the first item was added. All samples in the batch then seize the centrifuge
resource together (using a count semaphore pattern), wait `t_spin`, release, then
continue individually to the analyzer.

**Test this explicitly** with a small n (e.g. 20 samples, batch_size=5) and verify
that batches fire correctly before running full replications.

### 2. Seed handling

Every call to `run_des` must call `numpy.random.seed(seed)` at the very start to ensure
full reproducibility across replications. This mirrors R's `set.seed()` behaviour.

### 3. Performance

Python SimPy is slower than R simmer for large replication counts. Wrap
multi-replication loops in `concurrent.futures.ProcessPoolExecutor` for parallelism
where Streamlit allows it. Always provide a fallback sequential path in case
multiprocessing fails (Streamlit Cloud may restrict it).

```python
from concurrent.futures import ProcessPoolExecutor, as_completed

def run_replications_parallel(df, config, n_reps, max_workers=4):
    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(run_des, df, **config, seed=i): i
                       for i in range(1, n_reps + 1)}
            results = [f.result() for f in as_completed(futures)]
        return results
    except Exception:
        # Fallback to sequential
        return [run_des(df, **config, seed=i) for i in range(1, n_reps + 1)]
```

### 4. Streamlit session state

Store all simulation results in `st.session_state` so results persist without re-running
when the user clicks download buttons or adjusts other widgets.

```python
if "des_results" not in st.session_state:
    st.session_state.des_results = None

if st.button("Run Descriptive Simulation"):
    st.session_state.des_results = run_replications(...)

if st.session_state.des_results is not None:
    # render results
```

### 5. Download handlers — no file writes

The app must be deployable to Streamlit Cloud. Never write files to disk inside the app.
Use in-memory buffers for all downloads:

```python
import io

@st.cache_data
def convert_df_to_csv(df):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")

st.download_button(
    label="Download CSV",
    data=convert_df_to_csv(results_df),
    file_name="results.csv",
    mime="text/csv"
)
```

### 6. Data loading on startup

In `app.py`, load and clean data once at startup and store in `st.session_state`:

```python
if "lft_data" not in st.session_state:
    raw = load_raw_data("data/lft_records.csv")
    df_clean, summary = clean_data(raw)
    params = fit_parameters(df_clean)
    st.session_state.lft_data = df_clean
    st.session_state.data_summary = summary
    st.session_state.fitted_params = params
```

If the CSV is absent, display a `st.warning` placeholder on the About page and use
hardcoded defaults for all parameter inputs.

### 7. Verified simulation parameters (from the published paper)

Use these as hardcoded defaults in the app, matching the published research exactly:

| Parameter | Value | Source |
|---|---|---|
| `t_collect_mean` | 6 min | Paper |
| `t_collect_sd` | 2 min | Paper |
| `t_spin` | 12 min | Paper |
| `t_analyze` | 12 min | Paper |
| `t_validate_mean` | 4 min | Paper |
| `t_validate_sd` | 1.5 min | Paper |
| `batch_size` | 10 | Paper |
| `batch_max_wait` | 20 min | Paper |
| Baseline: phleb | 1 | Paper |
| Baseline: analyzer | 1 | Paper |
| Baseline: tech | 2 | Paper |
| Optimal: phleb | 3 | Paper |
| Optimal: analyzer | 2 | Paper |
| Optimal: tech | 2 | Paper |
| Baseline P95 TAT | 847.03 min | Paper (for validation) |
| Optimal P95 TAT | ~699 min | Paper (for validation) |

The simulation should produce P95 TAT close to 847 minutes under baseline config (1
phleb, 1 analyzer, 2 tech) when run with 300 samples at 30/hr. Use this as a
**validation check** — add a note in the DES page if the simulated P95 deviates more
than 15% from the paper's reported value.

---

## Summary Checklist for Claude Code

- [ ] `data_utils.py` — load, clean, fit_parameters functions
- [ ] `simulation_engine.py` — all 10 functions translated from R simmer to Python SimPy
- [ ] Batch logic tested explicitly with small sample
- [ ] `app.py` — data loaded at startup, stored in session_state
- [ ] `pages/1_About.py` — data summary, preprint link
- [ ] `pages/2_How_To_Guide.py` — static guide
- [ ] `pages/3_Queuing_Theory.py` — Erlang-C implemented from scratch
- [ ] `pages/4_DES_Simulation.py` — interactive simulation with Plotly charts
- [ ] `pages/5_Optimizer.py` — grid search with cost-frontier scatter plot
- [ ] `pages/6_Data_Analysis.py` — three expander sections, all downloads
- [ ] All downloads use `io.StringIO` / in-memory buffers (no file writes)
- [ ] All results stored in `st.session_state`
- [ ] `requirements.txt` complete
- [ ] Deployable to Streamlit Cloud
