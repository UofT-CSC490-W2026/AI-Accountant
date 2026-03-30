"""Steps 3-6: Cluster entries by amount using Ckmeans, assign new transaction."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from ckwrap import ckmeans

from services.precedent_v2.candidates import N_MIN
from services.precedent_v2.models import PrecedentEntry


@dataclass(frozen=True)
class AmountCluster:
    """A group of precedent entries with similar amounts."""
    entries: list[PrecedentEntry]
    center: float
    lower: float  # min amount in cluster
    upper: float  # max amount in cluster


def cluster_amounts(
    entries: list[PrecedentEntry],
    n_min: int = N_MIN,
) -> list[AmountCluster]:
    """Cluster entries by amount using Ckmeans.1d.dp with BIC-selected k.

    Args:
        entries: All entries for this vendor (already filtered by n_min).
        n_min: Minimum entries per cluster.

    Returns:
        List of AmountClusters.
    """
    amounts = np.array([float(e.amount) for e in entries])

    max_k = len(entries) // n_min
    if max_k < 1:
        max_k = 1

    result = ckmeans(amounts, max_k)
    labels = result.labels

    clusters: dict[int, list[PrecedentEntry]] = {}
    for entry, label in zip(entries, labels):
        clusters.setdefault(label, []).append(entry)

    return [
        AmountCluster(
            entries=group,
            center=float(np.mean([float(e.amount) for e in group])),
            lower=float(min(float(e.amount) for e in group)),
            upper=float(max(float(e.amount) for e in group)),
        )
        for group in clusters.values()
    ]


def assign_to_cluster(
    amount: float,
    clusters: list[AmountCluster],
    n_min: int = N_MIN,
) -> AmountCluster | None:
    """Assign a new transaction amount to the nearest cluster.

    Returns:
        The cluster if the amount falls within its range and the cluster
        has >= n_min entries. None (abstain) otherwise.
    """
    best: AmountCluster | None = None
    best_distance = float("inf")

    for cluster in clusters:
        if cluster.lower <= amount <= cluster.upper and len(cluster.entries) >= n_min:
            distance = abs(amount - cluster.center)
            if distance < best_distance:
                best = cluster
                best_distance = distance

    return best
