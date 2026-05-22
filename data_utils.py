import pandas as pd
import numpy as np


def load_raw_data(filepath="data/lft_records.csv") -> pd.DataFrame:
    df = pd.read_csv(filepath)
    df["sample_collected_date_time"] = pd.to_datetime(
        df["sample_collected_date_time"], dayfirst=True, format="mixed"
    )
    df["dispatch_date_time"] = pd.to_datetime(
        df["dispatch_date_time"], dayfirst=True, format="mixed"
    )
    df["tat_minutes"] = (
        df["dispatch_date_time"] - df["sample_collected_date_time"]
    ).dt.total_seconds() / 60
    return df


def clean_data(df, upper_percentile=0.95):
    n_raw = len(df)
    threshold = df["tat_minutes"].quantile(upper_percentile)
    df_clean = df[df["tat_minutes"] <= threshold].copy().reset_index(drop=True)
    n_cleaned = len(df_clean)
    summary = {
        "n_raw": n_raw,
        "n_cleaned": n_cleaned,
        "n_removed": n_raw - n_cleaned,
        "p95_threshold": round(threshold, 2),
        "median_tat": round(df_clean["tat_minutes"].median(), 2),
        "mean_tat": round(df_clean["tat_minutes"].mean(), 2),
    }
    return df_clean, summary


def fit_parameters(df_clean) -> dict:
    df_sorted = df_clean.sort_values("sample_collected_date_time").reset_index(drop=True)
    inter_arrival = df_sorted["sample_collected_date_time"].diff().dt.total_seconds().dropna() / 60
    median_iat_min = inter_arrival.median()
    arrival_rate_per_hour = 60 / median_iat_min if median_iat_min > 0 else 30.0

    date_range = (
        str(df_clean["sample_collected_date_time"].min().date()),
        str(df_clean["sample_collected_date_time"].max().date()),
    )
    n_days = max(
        (df_clean["sample_collected_date_time"].max() - df_clean["sample_collected_date_time"].min()).days,
        1,
    )
    daily_volume = len(df_clean) / n_days

    return {
        "arrival_rate_per_hour": round(arrival_rate_per_hour, 2),
        "median_tat": round(df_clean["tat_minutes"].median(), 2),
        "p95_tat": round(df_clean["tat_minutes"].quantile(0.95), 2),
        "p99_tat": round(df_clean["tat_minutes"].quantile(0.99), 2),
        "date_range": date_range,
        "daily_volume": round(daily_volume, 1),
    }
