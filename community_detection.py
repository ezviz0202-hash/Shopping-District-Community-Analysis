import pandas as pd
import networkx as nx

try:
    import community as community_louvain
except ImportError: 
    community_louvain = None


def detect_communities(G, seed=42):
    if community_louvain is not None:
        partition = community_louvain.best_partition(G, weight="weight", random_state=seed)
        modularity = community_louvain.modularity(partition, G, weight="weight")
    else:
        communities = nx.algorithms.community.louvain_communities(G, weight="weight", seed=seed)
        partition = {}
        for community_id, nodes in enumerate(communities):
            for node in nodes:
                partition[node] = community_id
        modularity = nx.algorithms.community.modularity(G, communities, weight="weight")

    result = pd.DataFrame([
        {"shop_id": node, "community": comm}
        for node, comm in partition.items()
    ])

    community_sizes = result["community"].value_counts().to_dict()
    result["community_size"] = result["community"].map(community_sizes)

    result = result.sort_values(["community", "shop_id"]).reset_index(drop=True)
    return result, modularity


def label_communities(community_df, shop_df):
    merged = community_df.merge(shop_df[["id", "category", "x", "y"]], left_on="shop_id", right_on="id")
    dominant = merged.groupby("community")["category"].agg(lambda x: x.value_counts().index[0]).to_dict()
    merged["community_label"] = merged["community"].map(lambda c: f"C{c}: {dominant[c]}")
    return merged


def compute_inter_community_flow(purchase_log, community_df):
    log = purchase_log.merge(community_df[["shop_id", "community"]], on="shop_id")
    customer_comm = log.groupby("customer_id")["community"].apply(set)
    cross_count = (customer_comm.apply(len) > 1).sum()
    total = len(customer_comm)
    cross_ratio = cross_count / total

    comm_flow = log.groupby(["customer_id", "community"]).size().reset_index(name="visits")
    flow_matrix = comm_flow.groupby("community")["visits"].sum()

    return {
        "cross_community_customers": int(cross_count),
        "total_customers": int(total),
        "cross_community_ratio": round(float(cross_ratio), 3),
        "community_visit_volume": flow_matrix.to_dict(),
    }
