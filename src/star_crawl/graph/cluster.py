"""Louvain clustering + auto-labeling + color assignment."""

from __future__ import annotations

import logging
from collections.abc import Iterable

import networkx as nx

logger = logging.getLogger(__name__)

# Distinct, vivid sRGB palette — perceptually anchored to OKLCH points so
# clusters stay visually balanced. Hex rather than oklch() because Cytoscape's
# canvas color parser doesn't recognise the oklch CSS function (only rgb / hsl
# / hex / named), which would otherwise fall back to gray.
PALETTE = [
    "#007ffc",  # cobalt blue
    "#00aa46",  # leaf green
    "#bb3ad6",  # magenta-purple
    "#f47600",  # amber
    "#df202e",  # crimson
    "#00c3c5",  # teal
    "#a49600",  # olive
    "#7e6cf7",  # violet
    "#e9609e",  # coral
    "#00af89",  # jade
    "#d040b9",  # fuchsia
    "#00b1ed",  # azure
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
    cluster_members: dict[int, list[tuple[int, str, int, int]]],
    *,
    top_k: int = 3,
    user_overrides: dict[int, str] | None = None,
) -> dict[int, str]:
    """Pick a label for each cluster: top-K most central keywords, joined.

    cluster_members[cluster_id] = list of (kw_id, display, doc_freq, intra_degree).
    Intra-cluster degree dominates so the label reflects the keywords that
    actually anchor the community; doc_freq breaks ties for terms tied on
    centrality.
    """
    out: dict[int, str] = {}
    overrides = user_overrides or {}
    for cid, members in cluster_members.items():
        if cid in overrides:
            out[cid] = overrides[cid]
            continue
        members_sorted = sorted(members, key=lambda m: (-m[3], -m[2]))
        top = members_sorted[:top_k]
        out[cid] = " · ".join(m[1] for m in top)
    return out


def palette_color(cluster_id: int) -> str:
    return PALETTE[(cluster_id - 1) % len(PALETTE)]
