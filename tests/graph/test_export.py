"""Export module tests (US5)."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pytest

from star_crawl.graph import export as gexport


def _sample_payload() -> dict:
    return {
        "nodes": [
            {"data": {
                "id": "k_1", "kw_id": 1, "term": "kafka", "display": "Kafka",
                "doc_freq": 12, "cluster_id": 1, "cluster_label": "streaming",
                "color": "oklch(72% 0.16 250)",
            }},
            {"data": {
                "id": "k_2", "kw_id": 2, "term": "stream", "display": "Stream",
                "doc_freq": 9, "cluster_id": 1, "cluster_label": "streaming",
                "color": "oklch(72% 0.16 250)",
            }},
            {"data": {
                "id": "k_3", "kw_id": 3, "term": "postgres", "display": "Postgres",
                "doc_freq": 11, "cluster_id": 2, "cluster_label": "storage",
                "color": "oklch(75% 0.14 150)",
            }},
        ],
        "edges": [
            {"data": {"id": "e_1_2", "source": "k_1", "target": "k_2",
                      "co_count": 7, "npmi": 0.62}},
        ],
        "meta": {"built_at": "2026-05-10T00:00:00Z", "is_stale": False},
    }


@pytest.mark.integration
def test_export_json(tmp_path: Path):
    payload = _sample_payload()
    out = tmp_path / "graph.json"
    size = gexport.to_cytoscape_json(payload, out)
    assert size > 0
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert len(loaded["nodes"]) == 3
    assert len(loaded["edges"]) == 1
    assert loaded["nodes"][0]["data"]["display"] == "Kafka"


@pytest.mark.integration
def test_export_graphml(tmp_path: Path):
    payload = _sample_payload()
    out = tmp_path / "graph.graphml"
    size = gexport.to_graphml(payload, out)
    assert size > 0
    g = nx.read_graphml(out)
    assert g.number_of_nodes() == 3
    assert g.number_of_edges() == 1
    # Node attributes preserved
    node_data = g.nodes["k_1"]
    assert node_data["display"] == "Kafka"
    assert int(node_data["doc_freq"]) == 12
    # Edge attributes preserved
    edge_data = g.edges["k_1", "k_2"]
    assert float(edge_data["npmi"]) == pytest.approx(0.62)
    assert int(edge_data["co_count"]) == 7


@pytest.mark.integration
def test_export_empty_payload(tmp_path: Path):
    payload = {"nodes": [], "edges": [], "meta": {}}
    out_json = tmp_path / "empty.json"
    out_gml = tmp_path / "empty.graphml"
    assert gexport.to_cytoscape_json(payload, out_json) > 0
    assert gexport.to_graphml(payload, out_gml) > 0
    g = nx.read_graphml(out_gml)
    assert g.number_of_nodes() == 0
