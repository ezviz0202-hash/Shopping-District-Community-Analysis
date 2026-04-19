import numpy as np
import pandas as pd
import networkx as nx
from collections import defaultdict


def build_covisit_matrix(purchase_log):
    customer_shops = purchase_log.groupby("customer_id")["shop_id"].apply(set)
    shop_ids = sorted(purchase_log["shop_id"].unique())
    covisit = defaultdict(int)

    for shops in customer_shops:
        shops = list(shops)
        for i in range(len(shops)):
            for j in range(i + 1, len(shops)):
                key = tuple(sorted([shops[i], shops[j]]))
                covisit[key] += 1

    matrix = pd.DataFrame(0, index=shop_ids, columns=shop_ids)
    for (a, b), count in covisit.items():
        matrix.loc[a, b] = count
        matrix.loc[b, a] = count

    return matrix


def build_shop_network(covisit_matrix, min_weight=5):
    G = nx.Graph()
    shops = covisit_matrix.index.tolist()
    G.add_nodes_from(shops)

    for i, a in enumerate(shops):
        for b in shops[i + 1:]:
            w = covisit_matrix.loc[a, b]
            if w >= min_weight:
                G.add_edge(a, b, weight=int(w))

    return G


def compute_network_motifs(G):
    triangles = {}
    for node in G.nodes():
        t = sum(1 for n1, n2 in nx.triangles(G, node) for _ in [1]) if False else nx.triangles(G, node)
        triangles[node] = t

    clustering = nx.clustering(G, weight="weight")
    betweenness = nx.betweenness_centrality(G, weight="weight")
    degree = dict(G.degree(weight="weight"))

    stats = pd.DataFrame({
        "shop_id": list(G.nodes()),
        "weighted_degree": [degree[n] for n in G.nodes()],
        "clustering_coeff": [clustering[n] for n in G.nodes()],
        "betweenness": [betweenness[n] for n in G.nodes()],
        "triangles": [triangles[n] for n in G.nodes()],
    })
    return stats