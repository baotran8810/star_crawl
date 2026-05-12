"""Read-side queries for the graph view."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class GraphFilters:
    sources: list[str] | None = None
    since: str | None = None
    until: str | None = None
    min_freq: int = 3
    min_npmi: float = 0.15
    cluster: int | None = None
    focus: int | None = None


def stale_status(conn: sqlite3.Connection) -> dict:
    """Compare current articles count vs the most recent build.

    Returns dict with `current_articles`, `last_build_articles`, `built_at`,
    and `is_stale` (bool, True when delta > 5%).
    """
    current = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    row = conn.execute(
        """SELECT n_articles, built_at FROM graph_meta
            ORDER BY built_at DESC LIMIT 1"""
    ).fetchone()
    if row is None:
        return {
            "current_articles": current,
            "last_build_articles": 0,
            "built_at": None,
            "is_stale": False,  # 'not built' is a separate state
            "is_built": False,
        }
    last = int(row["n_articles"]) if isinstance(row, sqlite3.Row) else int(row[0])
    built_at = row["built_at"] if isinstance(row, sqlite3.Row) else row[1]
    delta = current - last
    is_stale = current > 0 and (delta / max(current, 1)) > 0.05
    return {
        "current_articles": current,
        "last_build_articles": last,
        "built_at": built_at,
        "is_stale": is_stale,
        "is_built": True,
    }


def keyword_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM keywords").fetchone()[0])


def read_graph(conn: sqlite3.Connection, filters: GraphFilters) -> dict:
    """Return a Cytoscape elements payload {nodes, edges, meta}."""
    # If source or time filters are set, restrict to keywords that appear in
    # articles matching those filters.
    article_filter_active = bool(filters.sources or filters.since or filters.until)
    if article_filter_active:
        a_where: list[str] = []
        a_params: list[object] = []
        if filters.sources:
            placeholders = ",".join(["?"] * len(filters.sources))
            a_where.append(f"source_name IN ({placeholders})")
            a_params.extend(filters.sources)
        if filters.since:
            a_where.append("(published_at >= ? OR (published_at IS NULL AND crawled_at >= ?))")
            a_params.extend([filters.since, filters.since])
        if filters.until:
            a_where.append("(published_at <= ? OR (published_at IS NULL AND crawled_at <= ?))")
            a_params.extend([filters.until, filters.until])
        a_clause = "WHERE " + " AND ".join(a_where)
        allowed_kw_rows = conn.execute(
            f"""SELECT DISTINCT ak.keyword_id
                  FROM article_keywords ak
                  JOIN articles a ON a.id = ak.article_id
                  {a_clause}""",
            a_params,
        ).fetchall()
        allowed_kw_ids = {int(r["keyword_id"]) for r in allowed_kw_rows}
        if not allowed_kw_ids:
            allowed_kw_ids = {-1}  # sentinel: nothing will match
    else:
        allowed_kw_ids = None

    nodes_sql = """
        SELECT k.id, k.term, k.display, k.doc_freq, k.cluster_id,
               c.label  AS cluster_label,
               c.color  AS cluster_color
          FROM keywords k
     LEFT JOIN clusters c ON c.id = k.cluster_id
         WHERE k.doc_freq >= ?
    """
    params: list[object] = [filters.min_freq]
    if filters.cluster is not None:
        nodes_sql += " AND k.cluster_id = ?"
        params.append(filters.cluster)
    if allowed_kw_ids is not None:
        placeholders = ",".join(["?"] * len(allowed_kw_ids))
        nodes_sql += f" AND k.id IN ({placeholders})"
        params.extend(allowed_kw_ids)

    node_rows = conn.execute(nodes_sql, params).fetchall()
    node_ids = {int(r["id"]) for r in node_rows}

    edge_sql = """
        SELECT src_id, dst_id, co_count, npmi
          FROM keyword_edges
         WHERE npmi >= ?
    """
    edge_params: list[object] = [filters.min_npmi]
    edge_rows = conn.execute(edge_sql, edge_params).fetchall()
    edges_filtered = [
        e for e in edge_rows
        if int(e["src_id"]) in node_ids and int(e["dst_id"]) in node_ids
    ]

    if filters.focus is not None:
        focus_id = int(filters.focus)
        # Keep focus + its first-degree neighbors only
        neighbors = {focus_id}
        for e in edges_filtered:
            if int(e["src_id"]) == focus_id:
                neighbors.add(int(e["dst_id"]))
            elif int(e["dst_id"]) == focus_id:
                neighbors.add(int(e["src_id"]))
        node_rows = [r for r in node_rows if int(r["id"]) in neighbors]
        node_ids = neighbors
        edges_filtered = [
            e for e in edges_filtered
            if int(e["src_id"]) in node_ids and int(e["dst_id"]) in node_ids
        ]

    nodes = [
        {
            "data": {
                "id": f"k_{r['id']}",
                "kw_id": int(r["id"]),
                "term": r["term"],
                "display": r["display"],
                "doc_freq": int(r["doc_freq"]),
                "cluster_id": int(r["cluster_id"]) if r["cluster_id"] else 0,
                "cluster_label": r["cluster_label"] or "—",
                "color": r["cluster_color"] or "oklch(70% 0.01 80)",
            }
        }
        for r in node_rows
    ]
    edges = [
        {
            "data": {
                "id": f"e_{e['src_id']}_{e['dst_id']}",
                "source": f"k_{e['src_id']}",
                "target": f"k_{e['dst_id']}",
                "co_count": int(e["co_count"]),
                "npmi": float(e["npmi"]),
            }
        }
        for e in edges_filtered
    ]

    meta = stale_status(conn)
    meta["filters_applied"] = {
        "min_freq": filters.min_freq,
        "min_npmi": filters.min_npmi,
        "cluster": filters.cluster,
        "focus": filters.focus,
        "sources": list(filters.sources) if filters.sources else None,
        "since": filters.since,
        "until": filters.until,
    }
    return {"nodes": nodes, "edges": edges, "meta": meta}


def read_keyword_panel(conn: sqlite3.Connection, kw_id: int) -> dict | None:
    row = conn.execute(
        """SELECT k.*, c.label AS cluster_label
             FROM keywords k LEFT JOIN clusters c ON c.id = k.cluster_id
            WHERE k.id = ?""",
        (kw_id,),
    ).fetchone()
    if row is None:
        return None

    neighbors = conn.execute(
        """SELECT k2.id, k2.display, e.npmi
             FROM keyword_edges e
             JOIN keywords k2 ON k2.id = CASE WHEN e.src_id = ? THEN e.dst_id ELSE e.src_id END
            WHERE e.src_id = ? OR e.dst_id = ?
            ORDER BY e.npmi DESC LIMIT 8""",
        (kw_id, kw_id, kw_id),
    ).fetchall()

    articles = conn.execute(
        """SELECT a.id, a.source_name, a.title, a.published_at
             FROM article_keywords ak
             JOIN articles a ON a.id = ak.article_id
            WHERE ak.keyword_id = ?
            ORDER BY a.published_at DESC LIMIT 8""",
        (kw_id,),
    ).fetchall()

    return {
        "keyword": row,
        "neighbors": neighbors,
        "articles": articles,
    }


def search_keywords(conn: sqlite3.Connection, q: str, limit: int = 10) -> list:
    if not q.strip():
        return []
    rows = conn.execute(
        """SELECT id, term, display, doc_freq FROM keywords
            WHERE term LIKE ? OR display LIKE ?
            ORDER BY doc_freq DESC LIMIT ?""",
        (f"%{q.lower()}%", f"%{q}%", limit),
    ).fetchall()
    return rows


def read_article_keywords(conn: sqlite3.Connection, article_id: int) -> list:
    """Keywords linked to one article, ordered by score then doc_freq."""
    return conn.execute(
        """SELECT k.id, k.term, k.display, k.doc_freq, k.cluster_id,
                  ak.score, ak.is_glossary,
                  c.label AS cluster_label,
                  c.color AS cluster_color
             FROM article_keywords ak
             JOIN keywords k ON k.id = ak.keyword_id
        LEFT JOIN clusters c ON c.id = k.cluster_id
            WHERE ak.article_id = ?
            ORDER BY ak.score DESC, k.doc_freq DESC""",
        (article_id,),
    ).fetchall()


def read_related_articles(
    conn: sqlite3.Connection, article_id: int, *, limit: int = 8
) -> list:
    """Other articles ranked by overlap of keywords with this one.

    Returns rows with id, title, source_name, source_display, published_at,
    overlap (# shared keywords), word_count. 0 results when this article
    has no keyword links yet or no other article shares any keyword.
    """
    return conn.execute(
        """WITH this_kw AS (
              SELECT keyword_id FROM article_keywords WHERE article_id = ?
           )
           SELECT a.id, a.title, a.source_name, a.published_at, a.word_count,
                  s.display_name AS source_display,
                  COUNT(*) AS overlap
             FROM article_keywords ak
             JOIN this_kw t ON t.keyword_id = ak.keyword_id
             JOIN articles a ON a.id = ak.article_id
             JOIN sources s ON s.name = a.source_name
            WHERE ak.article_id != ?
            GROUP BY ak.article_id
            HAVING overlap > 0
            ORDER BY overlap DESC, a.published_at DESC
            LIMIT ?""",
        (article_id, article_id, limit),
    ).fetchall()


def has_extracted_keywords(conn: sqlite3.Connection, article_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM article_keywords WHERE article_id = ? LIMIT 1",
        (article_id,),
    ).fetchone()
    return row is not None
