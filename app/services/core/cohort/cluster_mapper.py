CLUSTER_LABELS = {
    0: "Budget Master – Disciplined and Predictable",
    1: "Weekend Spender – Spikes in Entertainment & Food",
    2: "Risk Group – Unstable Income & Missed Payments",
    3: "Balanced – Stable, Average Usage",
    4: "High Earner – Low Spending",
    5: "Impulse Buyer – Spikes, No Planning",
}


def map_cluster_label(cluster_id: int) -> str:
    return CLUSTER_LABELS.get(cluster_id, "Unknown Cluster")


def all_cluster_labels() -> dict:
    return CLUSTER_LABELS
