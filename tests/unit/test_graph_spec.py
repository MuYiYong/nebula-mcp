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
    assert [item.data["element_id"] for item in spec.elements.nodes] == ["1", "2"]
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


def test_graph_json_preserves_int64_ids_and_properties_for_javascript() -> None:
    large = 288456991511150593
    node = {**NODE_A, 'id': large, 'properties': {'name': 'A', 'large': large, 'nested': [-large], 'small': 34}}
    parsed = parse_result(OneShotResult([{'node': node}]), graph='demo', limits=ResultLimits(rows=10, nodes=10, edges=10, bytes=100_000))
    data = build_cytoscape_graph(parsed).elements.nodes[0].data
    assert data['raw_id'] == str(large)
    assert data['properties']['large'] == str(large)
    assert data['properties']['nested'] == [str(-large)]
    assert data['properties']['small'] == 34


def test_schema_keys_are_distinct_from_internal_ids() -> None:
    parsed = parse_result(
        OneShotResult([{"value": [NODE_A, EDGE_AB, NODE_B]}]), graph="demo",
        limits=ResultLimits(rows=10, nodes=10, edges=10, bytes=100_000),
    )
    node_type = parsed.graph.nodes[0].type_name
    edge_type = parsed.graph.edges[0].edge_type
    spec = build_cytoscape_graph(parsed, key_fields={
        ("node", node_type): ["name"], ("edge", edge_type): ["missing"],
    })
    assert spec.elements.nodes[0].data["primary_key"] == {"name": NODE_A["properties"]["name"]}
    assert spec.elements.edges[0].data["multiedge_key"] == {"missing": None}
    assert build_cytoscape_graph(parsed).elements.nodes[0].data["primary_key"] is None


def test_composite_multiedge_key_comes_from_properties_not_rank() -> None:
    edge = {**EDGE_AB, 'rank': 9223372036854775807,
            'properties': {'start_year': 2000, 'end_year': 2003}}
    parsed = parse_result(OneShotResult([{'e': edge}]), graph='demo',
                          limits=ResultLimits(rows=10, nodes=10, edges=10, bytes=100_000))
    data = build_cytoscape_graph(parsed, {('edge', edge['type']): ['start_year', 'end_year']}).elements.edges[0].data
    assert data['multiedge_key'] == {'start_year': 2000, 'end_year': 2003}
    assert data['rank'] == '9223372036854775807'
    assert build_cytoscape_graph(parsed).elements.edges[0].data['multiedge_key'] is None
