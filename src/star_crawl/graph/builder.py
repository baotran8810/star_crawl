"""Build the keyword co-occurrence graph from article_keywords.

Pipeline:
  1. Load all (article_id, keyword_id) pairs into per-article keyword sets.
  2. Compute pairwise co-occurrence counts.
  3. Apply NPMI weighting + filter thresholds.
  4. Cap edges per node by NPMI (top-N).
  5. Run Louvain to assign cluster_id.
  6. Auto-label clusters (top-3 keywords by doc_freq).
  7. Persist into keyword_edges + clusters + graph_meta.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from star_crawl.db.connection import connect
from star_crawl.graph.cluster import auto_label, detect_clusters, palette_color
from star_crawl.graph.ppmi import npmi

logger = logging.getLogger(__name__)


@dataclass
class GraphBuildResult:
    n_keywords: int = 0
    n_edges: int = 0
    n_clusters: int = 0
    cluster_labels: dict[int, str] = field(default_factory=dict)


def build_graph(
    *,
    data_dir: Path | None = None,
    min_doc_freq: int = 3,
    min_co_count: int = 2,
    min_npmi: float = 0.15,
    max_edges_per_node: int = 30,
    cluster_resolution: float = 1.0,
    cluster_seed: int = 42,
) -> GraphBuildResult:
    config = {
        "min_doc_freq": min_doc_freq,
        "min_co_count": min_co_count,
        "min_npmi": min_npmi,
        "max_edges_per_node": max_edges_per_node,
        "cluster_resolution": cluster_resolution,
        "cluster_seed": cluster_seed,
    }
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]

    conn = connect(data_dir)
    try:
        # 1. doc_freq filter
        kept = conn.execute(
            "SELECT id, display, doc_freq FROM keywords WHERE doc_freq >= ?",
            (min_doc_freq,),
        ).fetchall()
        kept_ids = {int(r["id"]) for r in kept}
        df_by_id = {int(r["id"]): int(r["doc_freq"]) for r in kept}
        display_by_id = {int(r["id"]): str(r["display"]) for r in kept}

        # 2. Per-article keyword sets (only kept keywords)
        rows = conn.execute(
            "SELECT article_id, keyword_id FROM article_keywords"
        ).fetchall()
        per_article: dict[int, set[int]] = defaultdict(set)
        for r in rows:
            kw = int(r["keyword_id"])
            if kw in kept_ids:
                per_article[int(r["article_id"])].add(kw)

        n_total_articles = (
            conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        )

        # 3. Pairwise co-occurrence
        co: Counter[tuple[int, int]] = Counter()
        for kws in per_article.values():
            sorted_kws = sorted(kws)
            for i, a in enumerate(sorted_kws):
                for b in sorted_kws[i + 1:]:
                    co[(a, b)] += 1

        # 4. NPMI + filter
        edges: list[tuple[int, int, int, float]] = []
        for (a, b), c in co.items():
            if c < min_co_count:
                continue
            w = npmi(c, df_by_id[a], df_by_id[b], n_total_articles)
            if w < min_npmi:
                continue
            edges.append((a, b, c, w))

        # 5. Per-node degree cap (top-N by NPMI)
        if max_edges_per_node and edges:
            per_node: dict[int, list[tuple[int, int, int, float]]] = defaultdict(list)
            for e in edges:
                per_node[e[0]].append(e)
                per_node[e[1]].append(e)
            keep: set[tuple[int, int]] = set()
            for node, node_edges in per_node.items():
                node_edges_sorted = sorted(node_edges, key=lambda x: -x[3])[:max_edges_per_node]
                for e in node_edges_sorted:
                    key = (min(e[0], e[1]), max(e[0], e[1]))
                    keep.add(key)
            edges = [e for e in edges if (min(e[0], e[1]), max(e[0], e[1])) in keep]

        # 6. Cluster (preserve user-labeled clusters by re-applying overrides)
        existing_overrides = _load_user_overrides(conn)
        edge_tuples = [(a, b, w) for a, b, _, w in edges]
        cluster_by_kw = detect_clusters(
            edge_tuples,
            resolution=cluster_resolution,
            seed=cluster_seed,
        )
        # Singleton keywords (no edges) — assign their own cluster
        for kw_id in kept_ids:
            if kw_id not in cluster_by_kw:
                cluster_by_kw[kw_id] = 0  # 0 = no-cluster sentinel; cleaned up below

        # Re-number clusters consecutively starting at 1, leaving 0 for singletons
        unique_cids = {c for c in cluster_by_kw.values() if c > 0}
        cluster_renum = {old: i for i, old in enumerate(sorted(unique_cids), start=1)}
        cluster_by_kw = {
            kw_id: cluster_renum.get(c, 0) for kw_id, c in cluster_by_kw.items()
        }

        # 7. Auto-label
        members_by_cluster: dict[int, list[tuple[int, str, int]]] = defaultdict(list)
        for kw_id, cid in cluster_by_kw.items():
            if cid == 0:
                continue
            members_by_cluster[cid].append(
                (kw_id, display_by_id[kw_id], df_by_id[kw_id])
            )
        labels = auto_label(members_by_cluster, user_overrides=existing_overrides)

        # 8. Persist
        # Wipe previous build
        conn.execute("DELETE FROM keyword_edges")
        conn.execute(
            """UPDATE keywords SET cluster_id = NULL"""
        )
        conn.execute("DELETE FROM clusters")
        conn.commit()

        # Insert clusters (skip 0)
        for cid, members in members_by_cluster.items():
            conn.execute(
                """INSERT INTO clusters (id, label, n_keywords, color, is_user_labeled)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    cid,
                    labels.get(cid, f"cluster {cid}"),
                    len(members),
                    palette_color(cid),
                    int(cid in existing_overrides),
                ),
            )

        for kw_id, cid in cluster_by_kw.items():
            if cid > 0:
                conn.execute(
                    "UPDATE keywords SET cluster_id = ? WHERE id = ?",
                    (cid, kw_id),
                )

        # Insert edges (canonical order: src < dst)
        for a, b, c, w in edges:
            src, dst = (a, b) if a < b else (b, a)
            conn.execute(
                """INSERT INTO keyword_edges (src_id, dst_id, co_count, npmi)
                   VALUES (?, ?, ?, ?)""",
                (src, dst, c, w),
            )

        # Audit row
        conn.execute(
            """INSERT INTO graph_meta
                  (n_articles, n_keywords, n_edges, n_clusters, config_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (n_total_articles, len(kept_ids), len(edges), len(members_by_cluster), config_hash),
        )
        conn.commit()
    finally:
        conn.close()

    return GraphBuildResult(
        n_keywords=len(kept_ids),
        n_edges=len(edges),
        n_clusters=len(members_by_cluster),
        cluster_labels=labels,
    )


def _load_user_overrides(conn) -> dict[int, str]:
    """Preserve labels of clusters previously marked is_user_labeled=1."""
    try:
        rows = conn.execute(
            "SELECT id, label FROM clusters WHERE is_user_labeled = 1"
        ).fetchall()
        return {int(r["id"]): str(r["label"]) for r in rows}
    except Exception:
        return {}
