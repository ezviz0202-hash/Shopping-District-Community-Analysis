import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import seaborn as sns
import networkx as nx
import numpy as np
import pandas as pd

PALETTE = ["#2E86AB", "#E84855", "#3BB273", "#F4A261", "#9B5DE5", "#00B4D8"]


def plot_community_network(G, community_df, output_path):
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_facecolor("#F8F9FA")
    fig.patch.set_facecolor("#F8F9FA")

    communities = sorted(community_df["community"].unique())
    color_map = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(communities)}
    node_colors = [color_map[community_df.set_index("shop_id").loc[n, "community"]] for n in G.nodes()]

    pos = nx.spring_layout(G, weight="weight", seed=42, k=2.0)
    weights = [G[u][v]["weight"] for u, v in G.edges()]
    max_w = max(weights) if weights else 1

    nx.draw_networkx_edges(
        G, pos, ax=ax,
        width=[0.5 + 3.0 * w / max_w for w in weights],
        alpha=0.35,
        edge_color="#AAAAAA",
    )
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=node_colors,
        node_size=500,
        edgecolors="white",
        linewidths=1.5,
    )
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=7, font_color="white", font_weight="bold")

    legend_patches = [
        mpatches.Patch(color=color_map[c], label=f"Community {c}")
        for c in communities
    ]
    ax.legend(handles=legend_patches, loc="upper left", fontsize=9, framealpha=0.9)
    ax.set_title("Cross-Cutting Purchase Behavior Network\n(edge weight = co-visit frequency)", fontsize=13, pad=12)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_covisit_heatmap(covisit_matrix, community_df, output_path):
    ordered_shops = community_df.sort_values("community")["shop_id"].tolist()
    matrix = covisit_matrix.loc[ordered_shops, ordered_shops]

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        matrix,
        ax=ax,
        cmap="Blues",
        linewidths=0.3,
        linecolor="#DDDDDD",
        cbar_kws={"label": "Co-visit count"},
        xticklabels=True,
        yticklabels=True,
    )

    communities = community_df.set_index("shop_id")["community"]
    boundaries = []
    prev = None
    for i, shop in enumerate(ordered_shops):
        c = communities[shop]
        if c != prev:
            boundaries.append(i)
            prev = c

    for b in boundaries[1:]:
        ax.axhline(b, color="red", linewidth=1.5, alpha=0.7)
        ax.axvline(b, color="red", linewidth=1.5, alpha=0.7)

    ax.set_title("Cross-Visit Frequency Heatmap\n(red lines = community boundaries)", fontsize=13, pad=10)
    ax.tick_params(labelsize=7)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_excitement_curves(excitement_trends, output_path):
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), facecolor="#F8F9FA")
    fig.suptitle("Community Excitement Level Curves (7-day Rolling Average)", fontsize=14, y=1.01)

    for idx, trend in enumerate(excitement_trends):
        ax = axes[idx // 2][idx % 2]
        ax.set_facecolor("#F8F9FA")
        data = trend["trend_data"]
        color = PALETTE[idx % len(PALETTE)]

        ax.fill_between(data["date"], data["rolling_excitement"], alpha=0.15, color=color)
        ax.plot(data["date"], data["rolling_excitement"], color=color, linewidth=2, label="7-day avg")
        ax.plot(data["date"], data["mean_excitement"], color=color, linewidth=0.8, alpha=0.4)

        ax.set_title(trend["label"], fontsize=10, fontweight="bold")
        ax.set_ylabel("Excitement Score", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.xaxis.set_major_locator(plt.MaxNLocator(5))
        ax.tick_params(axis="x", rotation=30)
        ax.grid(axis="y", alpha=0.3)

        peak = trend["peak_date"]
        ax.axvline(peak, color="red", linewidth=1, linestyle="--", alpha=0.7)
        ax.text(peak, ax.get_ylim()[1] * 0.95, "peak", fontsize=7, color="red", ha="center")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_spatial_map(shop_df, community_df, output_path):
    merged = shop_df.merge(community_df[["shop_id", "community"]], left_on="id", right_on="shop_id")
    communities = sorted(merged["community"].unique())
    color_map = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(communities)}

    fig, ax = plt.subplots(figsize=(9, 8))
    ax.set_facecolor("#EEF2F7")
    fig.patch.set_facecolor("#F8F9FA")

    for _, row in merged.iterrows():
        c = color_map[row["community"]]
        ax.scatter(row["x"], row["y"], s=280, color=c, edgecolors="white", linewidths=1.5, zorder=3)
        ax.text(row["x"] + 1.0, row["y"] + 1.0, row["id"], fontsize=7, zorder=4)

    legend_patches = [
        mpatches.Patch(color=color_map[c], label=f"Community {c}")
        for c in communities
    ]
    ax.legend(handles=legend_patches, loc="upper right", fontsize=9, framealpha=0.9)
    ax.set_xlim(-5, 110)
    ax.set_ylim(-5, 110)
    ax.set_xlabel("X coordinate (m)", fontsize=10)
    ax.set_ylabel("Y coordinate (m)", fontsize=10)
    ax.set_title("Spatial Distribution of Shop Communities\n(Detected via Cross-cutting Behavior Analysis)", fontsize=13, pad=10)
    ax.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_intervention_dashboard(community_df, excitement_trends, flow_stats, output_path):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), facecolor="#F8F9FA")
    fig.suptitle("Community Management Dashboard — Intervention Priority Analysis", fontsize=13, y=1.02)

    communities = [t["community"] for t in excitement_trends]
    labels = [t["label"] for t in excitement_trends]
    scores = [t["mean_excitement_overall"] for t in excitement_trends]
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(communities))]

    ax1 = axes[0]
    ax1.set_facecolor("#F8F9FA")
    bars = ax1.bar(labels, scores, color=colors, edgecolor="white", linewidth=1.5)
    ax1.set_title("Avg Excitement Score\nby Community", fontsize=10)
    ax1.set_ylabel("Score")
    ax1.tick_params(axis="x", rotation=30, labelsize=8)
    ax1.grid(axis="y", alpha=0.3)
    for bar, score in zip(bars, scores):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.003,
                 f"{score:.3f}", ha="center", fontsize=8)

    ax2 = axes[1]
    ax2.set_facecolor("#F8F9FA")
    visit_data = flow_stats["community_visit_volume"]
    visit_labels = [f"C{k}" for k in sorted(visit_data.keys())]
    visit_vals = [visit_data[k] for k in sorted(visit_data.keys())]
    ax2.bar(visit_labels, visit_vals, color=colors[:len(visit_labels)], edgecolor="white")
    ax2.set_title("Total Visit Volume\nby Community", fontsize=10)
    ax2.set_ylabel("Visits")
    ax2.tick_params(axis="x", labelsize=9)
    ax2.grid(axis="y", alpha=0.3)

    ax3 = axes[2]
    ax3.set_facecolor("#F8F9FA")
    cross_ratio = flow_stats["cross_community_ratio"]
    internal_ratio = 1 - cross_ratio
    wedge_sizes = [cross_ratio, internal_ratio]
    wedge_labels = [f"Cross-community\n{cross_ratio:.1%}", f"Single-community\n{internal_ratio:.1%}"]
    ax3.pie(wedge_sizes, labels=wedge_labels, colors=[PALETTE[0], PALETTE[2]],
            autopct="%1.1f%%", startangle=90, textprops={"fontsize": 9})
    ax3.set_title("Cross-community\nPurchasing Ratio", fontsize=10)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
