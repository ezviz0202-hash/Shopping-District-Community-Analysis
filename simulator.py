import numpy as np
import pandas as pd

np.random.seed(42)


COMMUNITY_CENTERS = {
    "food":     (20, 75),
    "clothing": (75, 75),
    "daily":    (20, 25),
    "leisure":  (75, 25),
}

SHOPS_RAW = []
for i, (group, (cx, cy)) in enumerate(COMMUNITY_CENTERS.items()):
    for j in range(5):
        idx = i * 5 + j + 1
        SHOPS_RAW.append({
            "id": f"S{idx:02d}",
            "name": f"Shop_{idx:02d}",
            "x": round(cx + np.random.uniform(-15, 15), 2),
            "y": round(cy + np.random.uniform(-15, 15), 2),
            "category": group,
        })

SHOP_DF = pd.DataFrame(SHOPS_RAW)

COMMUNITY_PRIORS = {
    "food":     [f"S{i:02d}" for i in range(1, 6)],
    "clothing": [f"S{i:02d}" for i in range(6, 11)],
    "daily":    [f"S{i:02d}" for i in range(11, 16)],
    "leisure":  [f"S{i:02d}" for i in range(16, 21)],
}


COMMUNITY_IOT_PROFILE = {
    "food":     {"traffic_scale": 8,  "dwell_mean": 6,  "spend_mean": 1200},
    "clothing": {"traffic_scale": 5,  "dwell_mean": 14, "spend_mean": 3500},
    "daily":    {"traffic_scale": 12, "dwell_mean": 5,  "spend_mean": 800},
    "leisure":  {"traffic_scale": 4,  "dwell_mean": 20, "spend_mean": 2500},
}


def generate_purchase_log(n_customers=400, n_days=60, seed=42):
    np.random.seed(seed)
    records = []
    shop_ids = SHOP_DF["id"].tolist()
    groups = list(COMMUNITY_PRIORS.keys())

    for cid in range(1, n_customers + 1):
        preference_group = np.random.choice(groups)
        preferred = COMMUNITY_PRIORS[preference_group]
        other = [s for s in shop_ids if s not in preferred]

       
        n_visits = np.random.poisson(6)
        for _ in range(max(n_visits, 1)):
            if np.random.rand() < 0.92:
                shop = np.random.choice(preferred)
            else:
                
                adjacent_group = np.random.choice([g for g in groups if g != preference_group])
                shop = np.random.choice(COMMUNITY_PRIORS[adjacent_group])

            day = np.random.randint(0, n_days)
            hour = int(np.random.normal(13, 3))
            hour = max(9, min(20, hour))
            profile = COMMUNITY_IOT_PROFILE[
                SHOP_DF.set_index("id").loc[shop, "category"]
            ]
            amount = round(abs(np.random.normal(profile["spend_mean"], profile["spend_mean"] * 0.4)), 0)
            records.append({
                "customer_id": f"C{cid:04d}",
                "shop_id": shop,
                "day": day,
                "hour": hour,
                "amount": amount,
            })

    df = pd.DataFrame(records)
    df["timestamp"] = (
        pd.to_datetime("2024-01-01")
        + pd.to_timedelta(df["day"], unit="D")
        + pd.to_timedelta(df["hour"], unit="h")
    )
    df = df.drop(columns=["day", "hour"])
    return df.sort_values("timestamp").reset_index(drop=True)


def generate_iot_data(purchase_log, seed=42):
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    records = []

    shop_category = SHOP_DF.set_index("id")["category"].to_dict()

    for _, shop_row in SHOP_DF.iterrows():
        shop_id = shop_row["id"]
        category = shop_row["category"]
        profile = COMMUNITY_IOT_PROFILE[category]
        shop_purchases = purchase_log[purchase_log["shop_id"] == shop_id]

        for date in dates:
            day_purchases = shop_purchases[shop_purchases["timestamp"].dt.date == date.date()]
            base_count = len(day_purchases)

            # Community-specific traffic scale + random event spikes
            spike = np.random.choice([1.0, 1.8, 2.5], p=[0.85, 0.10, 0.05])
            foot_traffic = max(
                1,
                int((base_count * profile["traffic_scale"] + np.random.poisson(3)) * spike),
            )
            dwell_time = round(abs(np.random.normal(profile["dwell_mean"], profile["dwell_mean"] * 0.3)), 1)
            avg_amount = day_purchases["amount"].mean() if len(day_purchases) > 0 else profile["spend_mean"] * 0.5

            excitement = round(
                0.4 * min(foot_traffic / (profile["traffic_scale"] * 5), 1.0)
                + 0.3 * min(dwell_time / (profile["dwell_mean"] * 2), 1.0)
                + 0.3 * min(avg_amount / (profile["spend_mean"] * 1.5), 1.0),
                3,
            )
            records.append({
                "shop_id": shop_id,
                "date": date,
                "foot_traffic": foot_traffic,
                "dwell_time_min": dwell_time,
                "excitement_score": excitement,
            })

    return pd.DataFrame(records)
