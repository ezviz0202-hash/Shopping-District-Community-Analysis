from __future__ import annotations

import json
import os
from typing import Dict, Optional, Tuple

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from network_analysis import build_covisit_matrix, build_shop_network
from community_detection import detect_communities


PALETTE = ["#2E86AB", "#E84855", "#3BB273", "#F4A261", "#9B5DE5", "#00B4D8"]


def _min_max_normalize(series: pd.Series) -> pd.Series:
   
    values = pd.to_numeric(series, errors="coerce").fillna(0.0)
    min_v = float(values.min())
    max_v = float(values.max())
    if np.isclose(max_v, min_v):
        return pd.Series(0.0, index=series.index)
    return (values - min_v) / (max_v - min_v)


def _add_inverse_distance(G: nx.Graph) -> nx.Graph:
 
    H = G.copy()
    for u, v, data in H.edges(data=True):
        weight = float(data.get("weight", 1.0))
        data["distance"] = 1.0 / max(weight, 1e-9)
    return H


def compute_community_pair_flow(
    purchase_log: pd.DataFrame,
    community_df: pd.DataFrame,
) -> pd.DataFrame:
   
    required = {"customer_id", "shop_id"}
    if not required.issubset(purchase_log.columns):
        raise ValueError(f"purchase_log must contain columns: {sorted(required)}")
    if not {"shop_id", "community"}.issubset(community_df.columns):
        raise ValueError("community_df must contain columns: shop_id, community")

    log = purchase_log.merge(
        community_df[["shop_id", "community"]].drop_duplicates(),
        on="shop_id",
        how="left",
    )
    communities = sorted(log["community"].dropna().unique())
    matrix = pd.DataFrame(0, index=communities, columns=communities, dtype=int)

    for _, group in log.groupby("customer_id"):
        visited = sorted(group["community"].dropna().unique())
        for i, c1 in enumerate(visited):
            matrix.loc[c1, c1] += 1
            for c2 in visited[i + 1:]:
                matrix.loc[c1, c2] += 1
                matrix.loc[c2, c1] += 1

    matrix.index.name = "community_from"
    matrix.columns.name = "community_to"
    return matrix


def compute_shop_bridge_indicators(
    G: nx.Graph,
    purchase_log: pd.DataFrame,
    community_df: pd.DataFrame,
) -> pd.DataFrame:
   
    comm_lookup = community_df.set_index("shop_id")["community"].to_dict()
    label_lookup = community_df.set_index("shop_id").get("community_label", pd.Series(dtype=str)).to_dict()

    H = _add_inverse_distance(G)
    betweenness = nx.betweenness_centrality(H, weight="distance", normalized=True)
    degree_centrality = nx.degree_centrality(G)
    weighted_degree = dict(G.degree(weight="weight"))

    visit_volume = purchase_log.groupby("shop_id").size().to_dict()
    total_sales = purchase_log.groupby("shop_id")["amount"].sum().to_dict() if "amount" in purchase_log.columns else {}

    rows = []
    for node in G.nodes():
        own_comm = comm_lookup.get(node)
        cross_edge_count = 0
        cross_edge_weight = 0.0
        internal_edge_weight = 0.0

        for neighbor in G.neighbors(node):
            edge_weight = float(G[node][neighbor].get("weight", 1.0))
            if comm_lookup.get(neighbor) != own_comm:
                cross_edge_count += 1
                cross_edge_weight += edge_weight
            else:
                internal_edge_weight += edge_weight

        total_edge_weight = cross_edge_weight + internal_edge_weight
        cross_share = cross_edge_weight / total_edge_weight if total_edge_weight > 0 else 0.0

        rows.append({
            "shop_id": node,
            "community": own_comm,
            "community_label": label_lookup.get(node, f"C{own_comm}"),
            "visit_volume": int(visit_volume.get(node, 0)),
            "total_sales": float(total_sales.get(node, 0.0)),
            "degree_centrality": float(degree_centrality.get(node, 0.0)),
            "betweenness_centrality": float(betweenness.get(node, 0.0)),
            "weighted_degree": float(weighted_degree.get(node, 0.0)),
            "cross_community_edge_count": int(cross_edge_count),
            "cross_community_edge_weight": float(cross_edge_weight),
            "cross_community_share": float(cross_share),
        })

    df = pd.DataFrame(rows)
    df["norm_betweenness"] = _min_max_normalize(df["betweenness_centrality"])
    df["norm_cross_weight"] = _min_max_normalize(df["cross_community_edge_weight"])
    df["norm_cross_count"] = _min_max_normalize(df["cross_community_edge_count"])
    df["community_bridge_score"] = (
        df["norm_betweenness"] + df["norm_cross_weight"] + df["norm_cross_count"]
    ) / 3.0

    # Consensus rank is kept alongside the score for interpretability.
    df["rank_betweenness"] = df["betweenness_centrality"].rank(ascending=False, method="min").astype(int)
    df["rank_cross_weight"] = df["cross_community_edge_weight"].rank(ascending=False, method="min").astype(int)
    df["rank_cross_count"] = df["cross_community_edge_count"].rank(ascending=False, method="min").astype(int)
    df["rank_bridge_score"] = df["community_bridge_score"].rank(ascending=False, method="min").astype(int)

    return df.sort_values(
        ["community_bridge_score", "betweenness_centrality", "cross_community_edge_weight"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def compute_temporal_network_evolution(
    purchase_log: pd.DataFrame,
    freq: str = "W",
    min_weight: int = 3,
) -> pd.DataFrame:
 
    if "timestamp" not in purchase_log.columns:
        raise ValueError("purchase_log must contain a timestamp column for temporal analysis")

    log = purchase_log.copy()
    log["timestamp"] = pd.to_datetime(log["timestamp"])
    log["period"] = log["timestamp"].dt.to_period(freq).dt.start_time

    rows = []
    for period, period_log in log.groupby("period"):
        if period_log["customer_id"].nunique() < 2 or period_log["shop_id"].nunique() < 2:
            continue

        covisit_matrix = build_covisit_matrix(period_log)
        G_period = build_shop_network(covisit_matrix, min_weight=min_weight)
        density = nx.density(G_period) if G_period.number_of_nodes() > 1 else 0.0
        avg_clustering = nx.average_clustering(G_period, weight="weight") if G_period.number_of_edges() > 0 else 0.0

        modularity = np.nan
        n_communities = 0
        if G_period.number_of_edges() > 0:
            try:
                community_df, modularity = detect_communities(G_period)
                n_communities = int(community_df["community"].nunique())
            except Exception:
                modularity = np.nan
                n_communities = 0

        rows.append({
            "period_start": period,
            "purchase_records": int(len(period_log)),
            "active_customers": int(period_log["customer_id"].nunique()),
            "active_shops": int(period_log["shop_id"].nunique()),
            "nodes": int(G_period.number_of_nodes()),
            "edges": int(G_period.number_of_edges()),
            "network_density": float(density),
            "avg_clustering": float(avg_clustering),
            "modularity": None if pd.isna(modularity) else float(modularity),
            "detected_communities": int(n_communities),
        })

    return pd.DataFrame(rows)


def summarize_social_capital_proxies(
    bridge_df: pd.DataFrame,
    pair_flow: pd.DataFrame,
    temporal_df: pd.DataFrame,
    global_modularity: Optional[float] = None,
) -> Dict[str, object]:
  
    top_bridge_stores = bridge_df.head(5)[[
        "shop_id",
        "community",
        "betweenness_centrality",
        "cross_community_edge_count",
        "cross_community_edge_weight",
        "community_bridge_score",
    ]].to_dict(orient="records")

    off_diag = pair_flow.copy()
    if len(off_diag) > 0:
        for c in off_diag.index:
            off_diag.loc[c, c] = 0
        strongest_pair = off_diag.stack().sort_values(ascending=False).head(1)
        strongest_pair_info = None
        if not strongest_pair.empty:
            (c_from, c_to), value = strongest_pair.index[0], int(strongest_pair.iloc[0])
            strongest_pair_info = {
                "community_from": int(c_from),
                "community_to": int(c_to),
                "shared_customers": value,
            }
    else:
        strongest_pair_info = None

    temporal_summary = {}
    if not temporal_df.empty:
        temporal_summary = {
            "periods": int(len(temporal_df)),
            "mean_network_density": float(temporal_df["network_density"].mean()),
            "mean_modularity": None if temporal_df["modularity"].dropna().empty else float(temporal_df["modularity"].dropna().mean()),
        }

    return {
        "interpretation_note": (
            "These metrics are proxy indicators for potential social capital connectors; "
            "they do not directly measure social capital."
        ),
        "global_modularity": None if global_modularity is None else float(global_modularity),
        "top_bridge_stores": top_bridge_stores,
        "strongest_community_pair": strongest_pair_info,
        "temporal_network_evolution": temporal_summary,
    }


def plot_bridge_store_ranking(
    bridge_df: pd.DataFrame,
    output_path: str,
    top_n: int = 8,
) -> None:
  
    top = bridge_df.head(top_n).iloc[::-1]
    colors = [PALETTE[int(c) % len(PALETTE)] for c in top["community"]]

    fig, ax = plt.subplots(figsize=(10, 6), facecolor="#F8F9FA")
    ax.set_facecolor("#F8F9FA")
    ax.barh(top["shop_id"], top["community_bridge_score"], color=colors, edgecolor="white")
    ax.set_xlabel("Community Bridge Score (equal-weight normalized proxy)")
    ax.set_ylabel("Shop")
    ax.set_title("Potential Bridge Stores Connecting Purchasing Communities", fontsize=13, pad=12)
    ax.grid(axis="x", alpha=0.25)

    for _, row in top.iterrows():
        ax.text(
            row["community_bridge_score"] + 0.01,
            row["shop_id"],
            f"C{int(row['community'])} | btw={row['betweenness_centrality']:.2f} | xflow={row['cross_community_edge_weight']:.0f}",
            va="center",
            fontsize=8,
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_social_capital_proxy_dashboard(
    bridge_df: pd.DataFrame,
    pair_flow: pd.DataFrame,
    temporal_df: pd.DataFrame,
    output_path: str,
) -> None:
  
    fig, axes = plt.subplots(1, 3, figsize=(17, 5), facecolor="#F8F9FA")
    fig.suptitle("Social Capital Proxy Dashboard — Bridge Stores and Network Evolution", fontsize=13, y=1.04)

   
    ax1 = axes[0]
    ax1.set_facecolor("#F8F9FA")
    top = bridge_df.head(6).iloc[::-1]
    colors = [PALETTE[int(c) % len(PALETTE)] for c in top["community"]]
    ax1.barh(top["shop_id"], top["community_bridge_score"], color=colors, edgecolor="white")
    ax1.set_title("Top Potential Bridge Stores", fontsize=10)
    ax1.set_xlabel("Bridge score")
    ax1.grid(axis="x", alpha=0.25)

  
    ax2 = axes[1]
    ax2.set_facecolor("#F8F9FA")
    im = ax2.imshow(pair_flow.values, cmap="Blues")
    ax2.set_xticks(range(len(pair_flow.columns)))
    ax2.set_xticklabels([f"C{c}" for c in pair_flow.columns])
    ax2.set_yticks(range(len(pair_flow.index)))
    ax2.set_yticklabels([f"C{c}" for c in pair_flow.index])
    ax2.set_title("Community-pair Customer Flow", fontsize=10)
    for i in range(pair_flow.shape[0]):
        for j in range(pair_flow.shape[1]):
            ax2.text(j, i, int(pair_flow.iloc[i, j]), ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)

   
    ax3 = axes[2]
    ax3.set_facecolor("#F8F9FA")
    if temporal_df.empty:
        ax3.text(0.5, 0.5, "No temporal data", ha="center", va="center")
        ax3.set_axis_off()
    else:
        tdf = temporal_df.copy()
        tdf["period_start"] = pd.to_datetime(tdf["period_start"])
        ax3.plot(tdf["period_start"], tdf["network_density"], marker="o", label="Density")
        if "modularity" in tdf.columns and tdf["modularity"].notna().any():
            ax3.plot(tdf["period_start"], tdf["modularity"], marker="s", label="Modularity")
        ax3.set_title("Temporal Network Evolution", fontsize=10)
        ax3.set_ylabel("Value")
        ax3.tick_params(axis="x", rotation=30, labelsize=8)
        ax3.grid(alpha=0.25)
        ax3.legend(fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def run_social_capital_proxy_analysis(
    G: nx.Graph,
    purchase_log: pd.DataFrame,
    community_df: pd.DataFrame,
    output_dir: str = "outputs",
    global_modularity: Optional[float] = None,
    temporal_freq: str = "W",
    min_weight: int = 3,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, object]]:
 
    os.makedirs(output_dir, exist_ok=True)

    bridge_df = compute_shop_bridge_indicators(G, purchase_log, community_df)
    pair_flow = compute_community_pair_flow(purchase_log, community_df)
    temporal_df = compute_temporal_network_evolution(purchase_log, freq=temporal_freq, min_weight=min_weight)
    summary = summarize_social_capital_proxies(bridge_df, pair_flow, temporal_df, global_modularity)

    bridge_df.to_csv(os.path.join(output_dir, "social_capital_bridge_store_ranking.csv"), index=False)
    pair_flow.to_csv(os.path.join(output_dir, "social_capital_community_pair_flow.csv"))
    temporal_df.to_csv(os.path.join(output_dir, "social_capital_temporal_network_evolution.csv"), index=False)
    with open(os.path.join(output_dir, "social_capital_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    plot_bridge_store_ranking(bridge_df, os.path.join(output_dir, "fig6_bridge_store_ranking.png"))
    plot_social_capital_proxy_dashboard(
        bridge_df,
        pair_flow,
        temporal_df,
        os.path.join(output_dir, "fig7_social_capital_proxy_dashboard.png"),
    )

    return bridge_df, pair_flow, temporal_df, summary
