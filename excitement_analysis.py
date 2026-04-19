import pandas as pd
import numpy as np


def aggregate_excitement_by_community(iot_data, community_df):
    merged = iot_data.merge(community_df[["shop_id", "community", "community_label"]], on="shop_id")
    daily = merged.groupby(["date", "community", "community_label"]).agg(
        mean_excitement=("excitement_score", "mean"),
        total_foot_traffic=("foot_traffic", "sum"),
        mean_dwell_time=("dwell_time_min", "mean"),
    ).reset_index()
    return daily


def compute_excitement_trend(daily_excitement):
    results = []
    for comm, group in daily_excitement.groupby("community"):
        group = group.sort_values("date").reset_index(drop=True)
        group["rolling_excitement"] = group["mean_excitement"].rolling(7, min_periods=1).mean()
        group["z_score"] = (group["mean_excitement"] - group["mean_excitement"].mean()) / (
            group["mean_excitement"].std() + 1e-9
        )
        peak_day = group.loc[group["mean_excitement"].idxmax(), "date"]
        results.append({
            "community": comm,
            "label": group["community_label"].iloc[0],
            "mean_excitement_overall": round(group["mean_excitement"].mean(), 4),
            "peak_date": peak_day,
            "trend_data": group,
        })
    return results


def detect_excitement_anomalies(daily_excitement, z_threshold=1.5):
    anomalies = []
    for comm, group in daily_excitement.groupby("community"):
        group = group.copy()
        group["z_score"] = (group["mean_excitement"] - group["mean_excitement"].mean()) / (
            group["mean_excitement"].std() + 1e-9
        )
        flagged = group[group["z_score"].abs() > z_threshold]
        for _, row in flagged.iterrows():
            anomalies.append({
                "community": comm,
                "date": row["date"],
                "excitement_score": round(row["mean_excitement"], 4),
                "z_score": round(row["z_score"], 3),
                "type": "high" if row["z_score"] > 0 else "low",
            })
    return pd.DataFrame(anomalies)
