from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree

import pytest
from mcp import Client

from nebula_mcp.errors import NebulaMCPError
from nebula_mcp.models import (
    GraphListOutput,
    GraphSchemaInput,
    GraphSummary,
    ListGraphsInput,
    MutationInput,
    QueryInput,
    QueryOutput,
)
from nebula_mcp.server import create_server
from nebula_mcp.service import NebulaService

pytestmark = pytest.mark.skipif(
    os.getenv("NEBULA_RUN_REMOTE_TESTS") != "1",
    reason="set NEBULA_RUN_REMOTE_TESTS=1 for YueShu integration",
)

SCHEMA = "default_schema"
EVALUATION_GRAPH = "cypher_compat_381_graph"
EVALUATION_GRAPH_TYPE = "cypher_compat_381_type"
EVALUATIONS = Path(__file__).resolve().parents[2] / "evaluations/remote_readonly.xml"


async def _discover_graph_with_edge(
    remote_service: NebulaService,
) -> tuple[GraphSummary, str, QueryOutput]:
    listed = await remote_service.list_graphs(ListGraphsInput(limit=100, offset=0))
    for item in listed.graphs:
        schema = item.schema_name or SCHEMA
        reference = item.name if schema == SCHEMA else f"/{schema}/{item.name}"
        seed = await remote_service.execute_query(
            QueryInput(
                statement=(
                    f"USE {reference}\n"
                    "MATCH (source)-[seed_edge]-(seed_neighbor) "
                    "RETURN source, seed_edge, seed_neighbor LIMIT 1"
                ),
                include_analysis=False,
                include_charts=False,
            )
        )
        if seed.status.ok and seed.graph is not None and seed.graph.elements.edges:
            return item, reference, seed
    pytest.fail("no discovered graph contains an incident edge")


@pytest.mark.anyio
async def test_remote_version_graphs_and_schema(remote_service: NebulaService) -> None:
    connection = await remote_service.test_connection()
    graphs = await remote_service.list_graphs(ListGraphsInput(limit=100, offset=0))
    graph, _, _ = await _discover_graph_with_edge(remote_service)
    assert graph.graph_type is not None
    schema = await remote_service.get_graph_schema(
        GraphSchemaInput(
            schema=graph.schema_name or SCHEMA,
            graph_type=graph.graph_type,
        )
    )

    assert connection.connected is True
    assert connection.version.startswith("5.3.0")
    assert graphs.returned_count > 0
    assert graph in graphs.graphs
    assert {entity.entity_type for entity in schema.entities} >= {"Node", "Edge"}


@pytest.mark.anyio
async def test_remote_scalar_node_edge_and_path_shapes(remote_service: NebulaService) -> None:
    _, reference, _ = await _discover_graph_with_edge(remote_service)
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
            statement=f"USE {reference}\nMATCH (n) RETURN n LIMIT 1",
            include_analysis=False,
            include_charts=False,
        )
    )
    edge = await remote_service.execute_query(
        QueryInput(
            statement=f"USE {reference}\nMATCH (a)-[e]-(b) RETURN e LIMIT 1",
            include_analysis=False,
            include_charts=False,
        )
    )
    path = await remote_service.execute_query(
        QueryInput(
            statement=f"USE {reference}\nMATCH p = (a)-[e]-(b) RETURN p LIMIT 1",
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
    graphs: GraphListOutput = await remote_service.list_graphs(
        ListGraphsInput(limit=100, offset=0)
    )
    if not any(
        item.schema_name == SCHEMA
        and item.name == EVALUATION_GRAPH
        and item.graph_type == EVALUATION_GRAPH_TYPE
        for item in graphs.graphs
    ):
        pytest.skip("the mutable XML evaluation fixture graph is not present")
    server = create_server(service=remote_service)

    async with Client(server) as client:
        for qa_pair in qa_pairs:
            result = await client.call_tool(
                "nebula_get_graph_schema",
                {"schema": SCHEMA, "graph_type": EVALUATION_GRAPH_TYPE},
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
