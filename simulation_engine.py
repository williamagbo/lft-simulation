import simpy
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed


# ---------------------------------------------------------------------------
# 2.1  Input data generator
# ---------------------------------------------------------------------------

def simulate_input_data(n=300, arrival_rate_per_hour=30, stat_share=0.15, seed=1) -> pd.DataFrame:
    np.random.seed(seed)
    rate_per_min = arrival_rate_per_hour / 60
    iat = np.random.exponential(1 / rate_per_min, n)
    arrival_time = np.cumsum(iat)
    urgency = np.where(np.random.random(n) < stat_share, "STAT", "ROUTINE")
    return pd.DataFrame({"id": range(1, n + 1), "arrival_time": arrival_time, "urgency": urgency})


# ---------------------------------------------------------------------------
# 2.2  Core SimPy DES
# ---------------------------------------------------------------------------

def run_des(
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
    seed=1,
) -> dict:
    np.random.seed(seed)

    env = simpy.Environment()
    phleb_res = simpy.Resource(env, capacity=n_phleb)
    centrifuge_res = simpy.Resource(env, capacity=n_centrifuge)
    analyzer_res = simpy.Resource(env, capacity=n_analyzer)
    tech_res = simpy.Resource(env, capacity=n_tech)

    # Per-sample tracking
    arrivals_log = []
    resource_log = []

    # Batch accumulator
    batch_queue = []          # list of (sample_id, ready_event)
    batch_timer_active = [False]
    batch_first_arrival_time = [None]

    def log_resource(name, res, capacity):
        resource_log.append({
            "resource": name,
            "time": env.now,
            "server": res.count,
            "queue": len(res.queue),
            "capacity": capacity,
            "system": res.count + len(res.queue),
        })

    def batch_manager():
        while True:
            # Wait until at least one sample is in the batch queue
            yield env.timeout(0.01)
            if not batch_queue:
                continue

            now = env.now
            elapsed = now - batch_first_arrival_time[0] if batch_first_arrival_time[0] is not None else 0

            if len(batch_queue) >= batch_size or (elapsed >= batch_max_wait and batch_queue):
                # Fire the batch
                current_batch = batch_queue.copy()
                batch_queue.clear()
                batch_timer_active[0] = False
                batch_first_arrival_time[0] = None
                for _, ev in current_batch:
                    if not ev.triggered:
                        ev.succeed()

    def sample_process(row):
        sample_id = row["id"]
        start_time = env.now

        # --- Phlebotomy ---
        with phleb_res.request() as req:
            yield req
            log_resource("Phlebotomist", phleb_res, n_phleb)
            t = max(0.1, np.random.normal(t_collect_mean, t_collect_sd))
            yield env.timeout(t)
        log_resource("Phlebotomist", phleb_res, n_phleb)

        # --- Batch wait ---
        batch_ready = env.event()
        batch_queue.append((sample_id, batch_ready))
        if batch_first_arrival_time[0] is None:
            batch_first_arrival_time[0] = env.now

        yield batch_ready

        # --- Centrifuge (whole batch seizes together via process coordination) ---
        with centrifuge_res.request() as req:
            yield req
            log_resource("Centrifuge", centrifuge_res, n_centrifuge)
            yield env.timeout(t_spin)
        log_resource("Centrifuge", centrifuge_res, n_centrifuge)

        # --- Analyzer ---
        with analyzer_res.request() as req:
            yield req
            log_resource("Analyzer", analyzer_res, n_analyzer)
            yield env.timeout(t_analyze)
        log_resource("Analyzer", analyzer_res, n_analyzer)

        # --- Technician validation ---
        with tech_res.request() as req:
            yield req
            log_resource("Technician", tech_res, n_tech)
            t = max(0.1, np.random.normal(t_validate_mean, t_validate_sd))
            yield env.timeout(t)
        log_resource("Technician", tech_res, n_tech)

        arrivals_log.append({
            "name": sample_id,
            "start_time": start_time,
            "end_time": env.now,
            "finished": True,
        })

    def arrival_generator():
        for _, row in df.iterrows():
            yield env.timeout(max(0, row["arrival_time"] - env.now))
            env.process(sample_process(row))

    env.process(arrival_generator())
    env.process(batch_manager())
    sim_end = df["arrival_time"].max() + 480
    env.run(until=sim_end)

    arrivals_df = pd.DataFrame(arrivals_log)
    if arrivals_df.empty:
        arrivals_df = pd.DataFrame(columns=["name", "start_time", "end_time", "finished"])

    resources_df = pd.DataFrame(resource_log)
    if resources_df.empty:
        resources_df = pd.DataFrame(columns=["resource", "time", "server", "queue", "capacity", "system"])

    return {"arrivals": arrivals_df, "resources": resources_df}


# ---------------------------------------------------------------------------
# 2.3  KPI summary
# ---------------------------------------------------------------------------

def summarise_kpis(sim_results) -> dict:
    arrivals = sim_results["arrivals"]
    resources = sim_results["resources"]

    finished = arrivals[arrivals["finished"] == True].copy()
    finished["tat"] = finished["end_time"] - finished["start_time"]

    tat_summary = pd.DataFrame([{
        "n_completed": len(finished),
        "mean_tat": finished["tat"].mean(),
        "sd_tat": finished["tat"].std(),
        "p50_tat": finished["tat"].quantile(0.50),
        "p90_tat": finished["tat"].quantile(0.90),
        "p95_tat": finished["tat"].quantile(0.95),
        "p99_tat": finished["tat"].quantile(0.99),
    }])

    util_rows = []
    for res_name, grp in resources.groupby("resource"):
        cap = grp["capacity"].iloc[0]
        utilization = (grp["server"] / cap).mean()
        util_rows.append({
            "resource": res_name,
            "utilization": round(utilization, 4),
            "avg_queue": round(grp["queue"].mean(), 2),
            "max_queue": int(grp["queue"].max()),
            "avg_system": round(grp["system"].mean(), 2),
        })
    util_df = pd.DataFrame(util_rows)

    return {"tat": tat_summary, "utilization": util_df, "arrivals": finished}


# ---------------------------------------------------------------------------
# 2.4  Wait decomposition
# ---------------------------------------------------------------------------

def get_wait_decomposition(sim_results) -> pd.DataFrame:
    resources = sim_results["resources"]
    arrivals = sim_results["arrivals"]

    rows = []
    for _, row in arrivals.iterrows():
        name = row["name"]
        rows.append({
            "name": name,
            "wait_phleb": 0.0,
            "wait_centrifuge": 0.0,
            "wait_analyzer": 0.0,
            "wait_tech": 0.0,
            "total_wait": max(0, row["end_time"] - row["start_time"]),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2.5  Resource utilization extractor
# ---------------------------------------------------------------------------

def extract_resource_utilization(sim_results, n_phleb, n_analyzer, n_tech, replication=1) -> pd.DataFrame:
    kpis = summarise_kpis(sim_results)
    util = kpis["utilization"].copy()
    util["n_phleb"] = n_phleb
    util["n_analyzer"] = n_analyzer
    util["n_tech"] = n_tech
    util["replication"] = replication
    return util


# ---------------------------------------------------------------------------
# 2.6  Replications
# ---------------------------------------------------------------------------

def _run_single_rep(args):
    df, config, seed = args
    result = run_des(df, **config, seed=seed)
    kpis = summarise_kpis(result)
    tat_row = kpis["tat"].copy()
    tat_row["replication"] = seed
    util_row = kpis["utilization"].copy()
    util_row["replication"] = seed
    return tat_row, util_row


def run_des_replications(df, n_reps=500, config: dict = None) -> pd.DataFrame:
    if config is None:
        config = {}
    tat_frames = []
    for seed in range(1, n_reps + 1):
        result = run_des(df, **config, seed=seed)
        kpis = summarise_kpis(result)
        row = kpis["tat"].copy()
        row["replication"] = seed
        tat_frames.append(row)
    return pd.concat(tat_frames, ignore_index=True)


# ---------------------------------------------------------------------------
# 2.7  Single-factor experiments
# ---------------------------------------------------------------------------

def run_single_factor_experiments(df, baseline_config: dict, n_reps=100) -> dict:
    experiments = {
        "Baseline": baseline_config.copy(),
        "A1_Phleb_Plus1": {**baseline_config, "n_phleb": baseline_config.get("n_phleb", 1) + 1},
        "A2_Analyzer_Plus1": {**baseline_config, "n_analyzer": baseline_config.get("n_analyzer", 1) + 1},
        "A3_Tech_Plus1": {**baseline_config, "n_tech": baseline_config.get("n_tech", 2) + 1},
    }
    tat_all, util_all = [], []
    for exp_name, cfg in experiments.items():
        for seed in range(1, n_reps + 1):
            result = run_des(df, **cfg, seed=seed)
            kpis = summarise_kpis(result)
            tat_row = kpis["tat"].copy()
            tat_row["experiment"] = exp_name
            tat_row["replication"] = seed
            util_row = kpis["utilization"].copy()
            util_row["experiment"] = exp_name
            util_row["replication"] = seed
            tat_all.append(tat_row)
            util_all.append(util_row)
    return {
        "tat_data": pd.concat(tat_all, ignore_index=True),
        "util_data": pd.concat(util_all, ignore_index=True),
    }


# ---------------------------------------------------------------------------
# 2.8  Robustness tests
# ---------------------------------------------------------------------------

def run_robustness_tests(optimal_config, arrival_rates=None, n_samples=500, n_reps=100) -> dict:
    if arrival_rates is None:
        arrival_rates = [15, 30, 45, 60]
    tat_all, util_all = [], []
    for lam in arrival_rates:
        df = simulate_input_data(n=n_samples, arrival_rate_per_hour=lam)
        for seed in range(1, n_reps + 1):
            result = run_des(df, **optimal_config, seed=seed)
            kpis = summarise_kpis(result)
            tat_row = kpis["tat"].copy()
            tat_row["lambda"] = lam
            tat_row["replication"] = seed
            util_row = kpis["utilization"].copy()
            util_row["lambda"] = lam
            util_row["replication"] = seed
            tat_all.append(tat_row)
            util_all.append(util_row)
    return {
        "tat_data": pd.concat(tat_all, ignore_index=True),
        "util_data": pd.concat(util_all, ignore_index=True),
    }


# ---------------------------------------------------------------------------
# 2.9  Sensitivity analysis
# ---------------------------------------------------------------------------

def run_sensitivity_analysis(df, optimal_config, n_reps=100) -> dict:
    scenarios = [
        {"name": "Baseline",         "cost_mult": 1.0, "lambda_mult": 1.0, "service_mult": 1.00},
        {"name": "Cost_Minus20",      "cost_mult": 0.8, "lambda_mult": 1.0, "service_mult": 1.00},
        {"name": "Cost_Plus20",       "cost_mult": 1.2, "lambda_mult": 1.0, "service_mult": 1.00},
        {"name": "Lambda_Minus20",    "cost_mult": 1.0, "lambda_mult": 0.8, "service_mult": 1.00},
        {"name": "Lambda_Plus20",     "cost_mult": 1.0, "lambda_mult": 1.2, "service_mult": 1.00},
        {"name": "Service_Minus15",   "cost_mult": 1.0, "lambda_mult": 1.0, "service_mult": 0.85},
        {"name": "Service_Plus15",    "cost_mult": 1.0, "lambda_mult": 1.0, "service_mult": 1.15},
    ]
    tat_all, util_all = [], []
    base_lam = optimal_config.get("arrival_rate_per_hour", 30)
    base_n = len(df)

    for sc in scenarios:
        cfg = optimal_config.copy()
        # Apply service multiplier
        for key in ("t_collect_mean", "t_analyze", "t_validate_mean"):
            if key in cfg:
                cfg[key] = cfg[key] * sc["service_mult"]
        # Apply lambda multiplier — regenerate df
        sc_lam = base_lam * sc["lambda_mult"]
        sc_df = simulate_input_data(n=base_n, arrival_rate_per_hour=sc_lam)

        for seed in range(1, n_reps + 1):
            result = run_des(sc_df, **cfg, seed=seed)
            kpis = summarise_kpis(result)
            tat_row = kpis["tat"].copy()
            tat_row["scenario"] = sc["name"]
            tat_row["lambda_mult"] = sc["lambda_mult"]
            tat_row["service_mult"] = sc["service_mult"]
            tat_row["cost_mult"] = sc["cost_mult"]
            tat_row["replication"] = seed
            util_row = kpis["utilization"].copy()
            util_row["scenario"] = sc["name"]
            util_row["lambda_mult"] = sc["lambda_mult"]
            util_row["service_mult"] = sc["service_mult"]
            util_row["cost_mult"] = sc["cost_mult"]
            util_row["replication"] = seed
            tat_all.append(tat_row)
            util_all.append(util_row)
    return {
        "tat_data": pd.concat(tat_all, ignore_index=True),
        "util_data": pd.concat(util_all, ignore_index=True),
    }


# ---------------------------------------------------------------------------
# 2.10  Optimisation grid
# ---------------------------------------------------------------------------

def run_optimization_grid(
    df,
    cost_tech=20,
    cost_an=50,
    target_tat=60,
    revenue_per_admission=2500,
    pw=0.15,
    n_reps=100,
) -> pd.DataFrame:
    grid = [
        {"n_phleb": p, "n_analyzer": a, "n_tech": t}
        for p in [1, 2, 3]
        for a in [1, 2]
        for t in [1, 2, 3]
    ]
    rows = []
    rev_loss_per_min = (revenue_per_admission * pw) / 1440

    for cfg in grid:
        p95_vals = []
        for seed in range(1, n_reps + 1):
            result = run_des(df, n_phleb=cfg["n_phleb"], n_analyzer=cfg["n_analyzer"],
                             n_tech=cfg["n_tech"], seed=seed)
            kpis = summarise_kpis(result)
            p95_vals.append(float(kpis["tat"]["p95_tat"].iloc[0]))

        mean_p95 = np.mean(p95_vals)
        labor_cost = (cfg["n_phleb"] + cfg["n_tech"]) * cost_tech + cfg["n_analyzer"] * cost_an
        delay_penalty = max(0, mean_p95 - target_tat) * rev_loss_per_min * len(df)
        total_cost = labor_cost + delay_penalty
        sla_compliance = sum(1 for v in p95_vals if v <= target_tat) / n_reps * 100

        rows.append({
            "Phleb": cfg["n_phleb"],
            "Analyzer": cfg["n_analyzer"],
            "Tech": cfg["n_tech"],
            "P95_TAT": round(mean_p95, 2),
            "Labor_Cost": round(labor_cost, 2),
            "Delay_Penalty": round(delay_penalty, 2),
            "Total_Cost": round(total_cost, 2),
            "SLA_Compliance": round(sla_compliance, 2),
        })
    return pd.DataFrame(rows)
