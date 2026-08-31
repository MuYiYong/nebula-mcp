from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree

import pytest
from mcp import Client

from nebula_mcp.errors import NebulaMCPError
from nebula_mcp.models import GraphSchemaInput, ListGraphsInput, MutationInput, QueryInput
from nebula_mcp.server import create_server
from nebula_mcp.service import NebulaService

pytestmark = pytest.mark.skipif(
    os.getenv("NEBULA_RUN_REMOTE_TESTS") != "1",
    reason="set NEBULA_RUN_REMOTE_TESTS=1 for YueShu integration",
)

SCHEMA = "default_schema"
GRAPH = "cypher_compat_381_graph"
GRAPH_TYPE = "cypher_compat_381_type"
EVALUATIONS = Path(__file__).resolve().parents[2] / "evaluations/remote_readonly.xml"


@pytest.mark.anyio
async def test_remote_version_graphs_and_schema(remote_service: NebulaService) -> None:
    connection = await remote_service.test_connection()
    graphs = await remote_service.list_graphs(ListGraphsInput(limit=100, offset=0))
    schema = await remote_service.get_graph_schema(
        GraphSchemaInput(schema=SCHEMA, graph_type=GRAPH_TYPE)
    )

    assert connection.connected is True
    assert connection.version.startswith("5.3.0")
    assert any(item.schema_name == SCHEMA and item.name == GRAPH for item in graphs.graphs)
    assert {entity.entity_type for entity in schema.entities} >= {"Node", "Edge"}
    assert sum(entity.entity_type == "Edge" for entity in schema.entities) == 3


@pytest.mark.anyio
async def test_remote_scalar_node_edge_and_path_shapes(remote_service: NebulaService) -> None:
    scalar = await remote_service.execute_query(
        QueryInput(
            statement="RETURN 1 AS probe",
            include_graph=False,
            include_analysis=False,
            include_charts=False,
        )
    )
    node = await remote_service.execute_query(
        QueryInput(
            statement="MATCH (n) RETURN n LIMIT 1",
            graph=GRAPH,
            include_analysis=False,
            include_charts=False,
        )
    )
    edge = await remote_service.execute_query(
        QueryInput(
            statement="MATCH (a)-[e]->(b) RETURN e LIMIT 1",
            graph=GRAPH,
            include_analysis=False,
            include_charts=False,
        )
    )
    path = await remote_service.execute_query(
        QueryInput(
            statement="MATCH p = (a)-[e]->(b) RETURN p LIMIT 1",
            graph=GRAPH,
            include_analysis=False,
            include_charts=False,
        )
    )

    assert scalar.status.ok is True
    assert scalar.table.rows == [{"probe": 1}]
    assert node.status.ok is True
    assert node.graph is not None and len(node.graph.elements.nodes) == 1
    assert edge.status.ok is True
    assert edge.graph is not None and len(edge.graph.elements.edges) == 1
    edge_node_ids = {item.data["id"] for item in edge.graph.elements.nodes}
    assert edge.graph.elements.edges[0].data["source"] in edge_node_ids
    assert edge.graph.elements.edges[0].data["target"] in edge_node_ids
    assert path.status.ok is True
    assert path.graph is not None and len(path.graph.paths) == 1
    assert path.graph.paths[0]["hop_count"] == 1
    assert path.graph.paths[0]["sdk_length"] == 2


@pytest.mark.anyio
async def test_remote_configuration_still_denies_mutation(remote_service: NebulaService) -> None:
    with pytest.raises(NebulaMCPError) as caught:
        await remote_service.execute_mutation(
            MutationInput(statement="INSERT (:NeverExecuted)", confirm_mutation=True)
        )

    assert caught.value.category == "policy_denied"
    assert "disabled" in caught.value.message


@pytest.mark.anyio
async def test_remote_mcp_evaluation_answers(remote_service: NebulaService) -> None:
    qa_pairs = ElementTree.parse(EVALUATIONS).getroot().findall("qa_pair")
    server = create_server(service=remote_service)

    async with Client(server) as client:
        for qa_pair in qa_pairs:
            result = await client.call_tool(
                "nebula_get_graph_schema",
                {"schema": SCHEMA, "graph_type": GRAPH_TYPE},
            )
            assert result.is_error is False
            facts = _schema_facts(result.structured_content)
            expected = qa_pair.findtext("expected_answer")
            assert facts[qa_pair.attrib["fact_key"]] == expected


def _schema_facts(output: dict[str, object]) -> dict[str, str]:
    entities = output["entities"]
    assert isinstance(entities, list)
    nodes = [item for item in entities if item["entity_type"] == "Node"]
    edges = [item for item in entities if item["entity_type"] == "Edge"]
    node = nodes[0]
    edges_by_type = {item["type_name"]: item for item in edges}
    return {
        "graph_type": str(output["graph_type"]),
        "node_type_count": str(len(nodes)),
        "node_type": str(node["type_name"]),
        "node_label": str(node["labels"][0]),
        "node_primary_key": str(node["primary_key_or_multiedge_key"][0]),
        "node_property_count": str(len(node["properties"])),
        "edge_type_count": str(len(edges)),
        "invest_label": str(edges_by_type["Invest"]["labels"][0]),
        "cooperate_label": str(edges_by_type["Cooperate"]["labels"][0]),
        "supply_key_mode": str(edges_by_type["Supply"]["primary_key_or_multiedge_key"]),
    }
