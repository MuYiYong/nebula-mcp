from __future__ import annotations

from nebula_mcp.models import ResultLimits
from nebula_mcp.result_parser import parse_result
from nebula_mcp.specs import build_cytoscape_graph
from tests.unit.test_result_parser import EDGE_AB, NODE_A, NODE_B, OneShotResult


def test_cytoscape_spec_uses_stable_cross_graph_ids() -> None:
    parsed = parse_result(
        OneShotResult([{"value": [NODE_A, EDGE_AB, NODE_B]}]),
        graph="demo",
        limits=ResultLimits(rows=10, nodes=10, edges=10, bytes=100_000),
    )

    spec = build_cytoscape_graph(parsed)

    assert spec.format == "cytoscape-elements-v1"
    assert [item.data["id"] for item in spec.elements.nodes] == ["demo:1", "demo:2"]
    edge = spec.elements.edges[0].data
    assert edge["id"] == "demo:1:Invest:0:2"
    assert edge["source"] == "demo:1"
    assert edge["target"] == "demo:2"


def test_every_edge_endpoint_references_an_existing_node() -> None:
    parsed = parse_result(
        OneShotResult([{"value": EDGE_AB}]),
        graph="demo",
        limits=ResultLimits(rows=10, nodes=10, edges=10, bytes=100_000),
    )

    spec = build_cytoscape_graph(parsed)
    node_ids = {item.data["id"] for item in spec.elements.nodes}

    for edge in spec.elements.edges:
        assert edge.data["source"] in node_ids
        assert edge.data["target"] in node_ids


def test_structured_endpoint_ids_use_the_same_encoding_as_nodes() -> None:
    source_id = {"tenant": "a", "id": 1}
    target_id = {"tenant": "a", "id": 2}
    edge = {**EDGE_AB, "src_id": source_id, "dst_id": target_id}
    parsed = parse_result(
        OneShotResult([{"value": edge}]),
        graph="demo",
        limits=ResultLimits(rows=10, nodes=10, edges=10, bytes=100_000),
    )

    spec = build_cytoscape_graph(parsed)
    node_ids = {item.data["id"] for item in spec.elements.nodes}

    assert spec.elements.edges[0].data["source"] in node_ids
    assert spec.elements.edges[0].data["target"] in node_ids
