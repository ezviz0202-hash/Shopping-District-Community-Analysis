import os
import json
import pandas as pd

from simulator import generate_purchase_log, generate_iot_data, SHOP_DF
from network_analysis import build_covisit_matrix, build_shop_network, compute_network_motifs
from community_detection import detect_communities, label_communities, compute_inter_community_flow
from excitement_analysis import aggregate_excitement_by_community, compute_excitement_trend, detect_excitement_anomalies
from social_capital_proxy_analysis import run_social_capital_proxy_analysis
from visualize import (
    plot_community_network,
    plot_covisit_heatmap,
    plot_excitement_curves,
    plot_spatial_map,
    plot_intervention_dashboard,
)

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def main():
    print("[1/8] Generating synthetic purchase log and IoT data...")
    purchase_log = generate_purchase_log(n_customers=400, n_days=60)
    iot_data = generate_iot_data(purchase_log)

    purchase_log.to_csv(os.path.join(OUTPUT_DIR, "purchase_log.csv"), index=False)
    iot_data.to_csv(os.path.join(OUTPUT_DIR, "iot_data.csv"), index=False)
    SHOP_DF.to_csv(os.path.join(OUTPUT_DIR, "shops.csv"), index=False)
    print(f"    Purchase records: {len(purchase_log)}")
    print(f"    IoT records: {len(iot_data)}")

    print("[2/8] Building cross-visit network...")
    covisit_matrix = build_covisit_matrix(purchase_log)
    G = build_shop_network(covisit_matrix, min_weight=3)
    motif_stats = compute_network_motifs(G)
    motif_stats.to_csv(os.path.join(OUTPUT_DIR, "network_stats.csv"), index=False)
    print(f"    Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")

    print("[3/8] Detecting communities via Louvain...")
    community_df, modularity = detect_communities(G)
    labeled_df = label_communities(community_df, SHOP_DF)
    labeled_df.to_csv(os.path.join(OUTPUT_DIR, "community_assignments.csv"), index=False)
    print(f"    Communities found: {community_df['community'].nunique()}")
    print(f"    Modularity: {modularity:.4f}")

    print("[4/8] Analyzing excitement curves...")
    daily_excitement = aggregate_excitement_by_community(iot_data, labeled_df)
    trends = compute_excitement_trend(daily_excitement)
    anomalies = detect_excitement_anomalies(daily_excitement)
    anomalies.to_csv(os.path.join(OUTPUT_DIR, "excitement_anomalies.csv"), index=False)

    print("[5/8] Computing inter-community flow statistics...")
    flow_stats = compute_inter_community_flow(purchase_log, labeled_df)
    with open(os.path.join(OUTPUT_DIR, "flow_stats.json"), "w") as f:
        json.dump(flow_stats, f, indent=2)
    print(f"    Cross-community purchasing ratio: {flow_stats['cross_community_ratio']:.1%}")

    print("[6/8] Running social capital proxy analysis...")
    bridge_df, pair_flow, temporal_network, social_capital_summary = run_social_capital_proxy_analysis(
        G,
        purchase_log,
        labeled_df,
        output_dir=OUTPUT_DIR,
        global_modularity=modularity,
        temporal_freq="W",
        min_weight=3,
    )
    print(f"    Top bridge store: {bridge_df.iloc[0]['shop_id']} "
          f"(score={bridge_df.iloc[0]['community_bridge_score']:.3f})")

    print("[7/8] Generating visualizations...")
    plot_community_network(G, labeled_df, os.path.join(OUTPUT_DIR, "fig1_community_network.png"))
    plot_covisit_heatmap(covisit_matrix, labeled_df, os.path.join(OUTPUT_DIR, "fig2_covisit_heatmap.png"))
    plot_excitement_curves(trends[:4], os.path.join(OUTPUT_DIR, "fig3_excitement_curves.png"))
    plot_spatial_map(SHOP_DF, labeled_df, os.path.join(OUTPUT_DIR, "fig4_spatial_map.png"))
    plot_intervention_dashboard(labeled_df, trends[:4], flow_stats, os.path.join(OUTPUT_DIR, "fig5_dashboard.png"))

    print("[8/8] Summary report:")
    print(f"    Total shops: {len(SHOP_DF)}")
    print(f"    Total customers: {purchase_log['customer_id'].nunique()}")
    print(f"    Detected communities: {community_df['community'].nunique()}")
    print(f"    Network modularity: {modularity:.4f}")
    print(f"    Cross-community ratio: {flow_stats['cross_community_ratio']:.1%}")
    print(f"    Excitement anomalies detected: {len(anomalies)}")
    print(f"    Top bridge store: {bridge_df.iloc[0]['shop_id']}")
    print(f"\nAll outputs saved to ./{OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
