"""Louvain clustering + auto-labeling + color assignment."""

from __future__ import annotations

import logging
from collections.abc import Iterable

import networkx as nx

logger = logging.getLogger(__name__)

# Distinct OKLCH hues for clusters (will be cycled if more clusters than colors)
PALETTE = [
    "oklch(72% 0.16 250)",  # blue
    "oklch(75% 0.14 150)",  # green
    "oklch(75% 0.16 320)",  # purple
    "oklch(78% 0.14 60)",   # warm
    "oklch(70% 0.18 30)",   # red
    "oklch(78% 0.13 100)",  # yellow-green
    "oklch(72% 0.16 200)",  # teal
    "oklch(70% 0.16 290)",  # violet
    "oklch(75% 0.14 350)",  # pink
    "oklch(72% 0.13 120)",  # mint
    "oklch(70% 0.15 350)",  # rose
    "oklch(72% 0.13 220)",  # azure
]


def detect_clusters(
    edges: Iterable[tuple[int, int, float]],
    *,
    resolution: float = 1.0,
    seed: int = 42,
) -> dict[int, int]:
    """Run Louvain on the weighted graph; return {keyword_id: cluster_id}.

    cluster_id is 1-based and stable for the run (sorted by size, descending).
    """
    g = nx.Graph()
    for src, dst, weight in edges:
        g.add_edge(src, dst, weight=weight)

    if g.number_of_nodes() == 0:
        return {}

    communities = nx.community.louvain_communities(g, weight="weight", resolution=resolution, seed=seed)
    # Sort communities by size descending → stable, deterministic numbering
    communities_sorted = sorted(
        (set(c) for c in communities), key=lambda s: (-len(s), min(s))
    )
    out: dict[int, int] = {}
    for idx, members in enumerate(communities_sorted, start=1):
        for member in members:
            out[int(member)] = idx
    return out


def auto_label(
    cluster_members: dict[int, list[tuple[int, str, int]]],
    *,
    top_k: int = 3,
    user_overrides: dict[int, str] | None = None,
) -> dict[int, str]:
    """Pick a label for each cluster: top-K keywords by doc_freq, joined.

    cluster_members[cluster_id] = list of (kw_id, display, doc_freq).
    """
    out: dict[int, str] = {}
    overrides = user_overrides or {}
    for cid, members in cluster_members.items():
        if cid in overrides:
            out[cid] = overrides[cid]
            continue
        members_sorted = sorted(members, key=lambda m: -m[2])
        top = members_sorted[:top_k]
        out[cid] = " · ".join(d for _, d in [(m[1], m[1]) for m in top])
    return out


def palette_color(cluster_id: int) -> str:
    return PALETTE[(cluster_id - 1) % len(PALETTE)]
