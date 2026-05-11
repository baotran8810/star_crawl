"""Louvain clustering + auto-labeling + color assignment."""

from __future__ import annotations

import logging
from collections.abc import Iterable

import networkx as nx

logger = logging.getLogger(__name__)

# Distinct, vivid OKLCH palette. Higher chroma + irregular hue spacing
# maximises perceived separation between adjacent clusters (vs naive 30°
# steps that all collapse into "pastel blues" perceptually).
PALETTE = [
    "oklch(60% 0.22 250)",  # cobalt blue
    "oklch(64% 0.19 150)",  # leaf green
    "oklch(60% 0.24 320)",  # magenta-purple
    "oklch(70% 0.19 55)",   # amber
    "oklch(58% 0.22 25)",   # crimson
    "oklch(72% 0.17 195)",  # teal
    "oklch(66% 0.18 105)",  # olive
    "oklch(62% 0.20 285)",  # violet
    "oklch(68% 0.18 355)",  # coral
    "oklch(65% 0.17 175)",  # jade
    "oklch(62% 0.22 335)",  # fuchsia
    "oklch(70% 0.17 225)",  # azure
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
