from __future__ import annotations

from collections.abc import Iterable
from typing import Any, ClassVar

import pytest

from nebula_mcp.config import Settings
from nebula_mcp.errors import NebulaMCPError
from nebula_mcp.models import (
    ExpandNodeInput,
    GraphSchemaInput,
    ListGraphsInput,
    MutationInput,
    QueryInput,
    ValidateGQLInput,
)
from nebula_mcp.service import NebulaService


class FakeResult:
    status_code = "00000"
    status_message = ""
    latency_us = 11
    column_names: ClassVar[list[str]] = []

    def __init__(self, rows: list[dict[str, Any]], *, extra_info: dict[str, Any] | None = None) -> None:
        self.rows = rows
        self.size = len(rows)
        self.extra_info = extra_info or {}
        self.column_names = list(rows[0]) if rows else []

    def as_primitive_by_row(self) -> Iterable[dict[str, Any]]:
        yield from self.rows


class FakeGateway:
    def __init__(self, results: list[FakeResult] | None = None) -> None:
        self.results = list(results or [])
        self.statements: list[str] = []

    async def execute(self, statement: str) -> FakeResult:
        if statement.startswith("DESCRIBE GRAPH ") and not statement.startswith("DESCRIBE GRAPH TYPE "):
            return FakeResult([])
        self.statements.append(statement)
        return self.results.pop(0)

    async def version(self) -> str:
        return "5.3.0"


def mutation_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"allow_mutations": True})


@pytest.mark.anyio
async def test_connection_output_is_redacted(settings: Settings) -> None:
    gateway = FakeGateway()
    service = NebulaService(settings, gateway)

    output = await service.test_connection()

    assert output.connected is True
    assert output.version == "5.3.0"
    assert output.config["username"] == "r***r"
    assert "runtime-secret" not in output.model_dump_json()


@pytest.mark.anyio
async def test_query_requires_read_only_policy_before_gateway_call(settings: Settings) -> None:
    gateway = FakeGateway()
    service = NebulaService(settings, gateway)

    with pytest.raises(NebulaMCPError) as caught:
        await service.execute_query(QueryInput(statement="DROP GRAPH demo"))

    assert caught.value.category == "policy_denied"
    assert gateway.statements == []


@pytest.mark.anyio
async def test_query_rejects_unconverted_cypher_before_gateway_call(settings: Settings) -> None:
    gateway = FakeGateway()
    service = NebulaService(settings, gateway)

    with pytest.raises(NebulaMCPError) as caught:
        await service.execute_query(QueryInput(statement="MATCH (n) WITH n RETURN n LIMIT 1"))

    assert caught.value.category == "validation_error"
    assert gateway.statements == []


@pytest.mark.anyio
async def test_query_builds_requested_specs_and_factual_context(settings: Settings) -> None:
    rows = [{"sector": "A", "score": 1.0}, {"sector": "B", "score": 2.0}]
    gateway = FakeGateway([FakeResult(rows)])
    service = NebulaService(settings, gateway)

    output = await service.execute_query(
        QueryInput(statement="RETURN 'A' AS sector, 1.0 AS score", graph="demo")
    )

    assert gateway.statements == ["PROFILE USE demo\nRETURN 'A' AS sector, 1.0 AS score"]
    assert output.query.statement == "RETURN 'A' AS sector, 1.0 AS score"
    assert output.query.display_statement == (
        "USE demo\nRETURN 'A' AS sector, 1.0 AS score"
    )
    assert output.table.returned_row_count == 2
    assert output.graph is not None
    assert output.graph.format == "cytoscape-elements-v1"
    assert output.analysis is not None
    assert output.charts[0].format == "vega-lite-v5"
    assert output.explanation_context.empty_result is False
    assert output.explanation_context.validation_evidence.executed is True


@pytest.mark.anyio
async def test_query_result_components_remain_individually_configurable(
    settings: Settings,
) -> None:
    rows = [{"sector": "A", "score": 1.0}, {"sector": "B", "score": 2.0}]
    gateway = FakeGateway([FakeResult(rows)])
    service = NebulaService(settings, gateway)

    output = await service.execute_query(
        QueryInput(
            statement="RETURN 'A' AS sector, 1.0 AS score",
            include_graph=False,
            include_analysis=False,
            include_charts=False,
        )
    )

    assert output.graph is None
    assert output.analysis is None
    assert output.charts == []
    assert output.explanation_context.validation_evidence.executed is True


@pytest.mark.anyio
async def test_graph_input_conflicts_with_explicit_use(settings: Settings) -> None:
    gateway = FakeGateway()
    service = NebulaService(settings, gateway)

    with pytest.raises(NebulaMCPError, match="USE"):
        await service.execute_query(QueryInput(statement="USE other RETURN 1", graph="demo"))

    assert gateway.statements == []


@pytest.mark.anyio
async def test_explicit_use_supplies_the_result_graph_context(settings: Settings) -> None:
    gateway = FakeGateway([FakeResult([{"value": 1}])])
    service = NebulaService(settings, gateway)

    output = await service.execute_query(QueryInput(statement="USE other RETURN 1"))

    assert output.query.statement == "USE other RETURN 1"
    assert output.query.display_statement == "USE other RETURN 1"
    assert output.query.graph == "other"
    assert output.graph is not None
    assert output.graph.graph == "other"


@pytest.mark.anyio
async def test_expand_node_executes_fixed_read_only_query(settings: Settings) -> None:
    source = {
        "id": 289166301065117700,
        "type": "Corp",
        "labels": ["Corporation"],
        "properties": {"name": "A"},
    }
    neighbor = {
        "id": 289166301065117701,
        "type": "Corp",
        "labels": ["Corporation"],
        "properties": {"name": "B"},
    }
    edge = {
        "src_id": source["id"],
        "dst_id": neighbor["id"],
        "rank": 0,
        "type": "Invest",
        "labels": ["INVEST"],
        "properties": {"weight": 0.8},
        "direction": "OUTGOING",
    }
    gateway = FakeGateway(
        [FakeResult([{"source": source, "edge": edge, "neighbor": neighbor}])]
    )
    service = NebulaService(settings, gateway)

    output = await service.expand_node(
        ExpandNodeInput(graph="demo", element_id=str(source["id"]), max_rows=25)
    )

    expected = (
        "USE demo\n"
        "MATCH (source WHERE element_id(source) = 289166301065117700)-[edge]-(neighbor)\n"
        "RETURN source, edge, neighbor\n"
        "LIMIT 25"
    )
    assert gateway.statements == [f"PROFILE {expected}"]
    assert output.query.statement == expected
    assert output.query.display_statement == expected
    assert output.query.read_only is True
    assert output.graph.format == "cytoscape-elements-v1"
    assert len(output.graph.elements.nodes) == 2
    assert len(output.graph.elements.edges) == 1


@pytest.mark.anyio
async def test_expand_node_caps_rows_to_server_limit(settings: Settings) -> None:
    gateway = FakeGateway([FakeResult([])])
    service = NebulaService(settings, gateway)

    output = await service.expand_node(
        ExpandNodeInput(graph="#scratch", element_id="1", max_rows=10_000)
    )

    assert gateway.statements[0].endswith(f"LIMIT {settings.max_rows}")
    assert output.graph.elements.nodes == []
    assert output.graph.elements.edges == []


@pytest.mark.anyio
async def test_mutation_needs_switch_and_confirmation(settings: Settings) -> None:
    gateway = FakeGateway()
    service = NebulaService(settings, gateway)

    with pytest.raises(NebulaMCPError, match="disabled"):
        await service.execute_mutation(
            MutationInput(statement="INSERT (:N)", confirm_mutation=True)
        )
    assert gateway.statements == []

    enabled_service = NebulaService(mutation_settings(settings), gateway)
    with pytest.raises(NebulaMCPError, match="confirmation"):
        await enabled_service.execute_mutation(
            MutationInput(statement="INSERT (:N)", confirm_mutation=False)
        )
    assert gateway.statements == []


@pytest.mark.anyio
async def test_enabled_confirmed_mutation_returns_affected_counts(settings: Settings) -> None:
    gateway = FakeGateway(
        [FakeResult([], extra_info={"affected_nodes": 2, "affected_edges": 1})]
    )
    service = NebulaService(mutation_settings(settings), gateway)

    output = await service.execute_mutation(
        MutationInput(statement="INSERT (:N)", confirm_mutation=True)
    )

    assert output.affected_nodes == 2
    assert output.affected_edges == 1


@pytest.mark.anyio
async def test_schema_uses_persistent_schema_reference_and_bounds_ddl(settings: Settings) -> None:
    gateway = FakeGateway(
        [
            FakeResult(
                [
                    {
                        "entity_type": "Node",
                        "type_name": "Corp",
                        "type_pattern": "(Corp)",
                        "labels": ["Corporation"],
                        "primary_key": "id",
                        "multiedge_key": None,
                        "properties": {"id": "INT64"},
                    }
                ]
            ),
            FakeResult(
                [
                    {
                        "graph_type_name": "demo_type",
                        "create_graph_type_statement": "CREATE GRAPH TYPE demo_type " + "x" * 100,
                    }
                ]
            ),
        ]
    )
    service = NebulaService(settings, gateway)

    output = await service.get_graph_schema(
        GraphSchemaInput(
            schema="default_schema",
            graph_type="demo_type",
            include_ddl=True,
            max_ddl_bytes=32,
        )
    )

    assert gateway.statements == [
        "DESCRIBE GRAPH TYPE /default_schema/demo_type",
        "SHOW CREATE GRAPH TYPE /default_schema/demo_type",
    ]
    assert output.entities[0].entity_type == "Node"
    assert output.ddl_truncated is True
    assert len(output.ddl.encode("utf-8")) <= 32


@pytest.mark.anyio
async def test_list_graphs_returns_typed_page(settings: Settings) -> None:
    gateway = FakeGateway(
        [
            FakeResult(
                [
                    {
                        "schema": "/default_schema",
                        "name": "demo",
                        "graph_type": "demo_type",
                        "owner": "root",
                        "extra": None,
                    }
                ]
            )
        ]
    )
    service = NebulaService(settings, gateway)

    output = await service.list_graphs(ListGraphsInput(limit=10, offset=5))

    assert gateway.statements == ["CALL show_graphs() RETURN * OFFSET 5 LIMIT 10"]
    assert output.graphs[0].name == "demo"
    assert output.graphs[0].schema_name == "default_schema"
    assert output.returned_count == 1


@pytest.mark.anyio
async def test_validate_explain_never_executes_the_original_statement(settings: Settings) -> None:
    gateway = FakeGateway([FakeResult([{"plan": "NodesScan"}])])
    service = NebulaService(settings, gateway)

    output = await service.validate_gql(
        ValidateGQLInput(statement="MATCH (n) RETURN n LIMIT 1", run_explain=True)
    )

    assert gateway.statements == ["EXPLAIN MATCH (n) RETURN n LIMIT 1"]
    assert output.evidence.explain_checked is True
    assert output.evidence.executed is False
    assert output.explain is not None


@pytest.mark.anyio
async def test_query_resolves_schema_keys_and_preserves_wire_statement(settings: Settings) -> None:
    from tests.unit.test_result_parser import NODE_A

    class KeyGateway(FakeGateway):
        async def execute(self, statement):
            self.statements.append(statement)
            if statement.startswith("DESCRIBE GRAPH TYPE"):
                return FakeResult([{"entity_type": "Node", "type_name": NODE_A["type"],
                                    "primary_key/multiedge_key": ["name"]}])
            if statement.startswith("DESCRIBE GRAPH"):
                return FakeResult([{"graph_type_name": "demo_type"}])
            return FakeResult([{"n": NODE_A}])

    gateway = KeyGateway()
    output = await NebulaService(settings, gateway).execute_query(
        QueryInput(statement="USE /other/demo MATCH (n) RETURN n LIMIT 1")
    )
    assert gateway.statements[-1] == "DESCRIBE GRAPH TYPE /other/`demo_type`"
    assert output.graph.elements.nodes[0].data["primary_key"] == {"name": NODE_A["properties"]["name"]}
    assert output.query.display_statement == "USE /other/demo MATCH (n) RETURN n LIMIT 1"
    assert len(output.explanation_context.suggested_focus) >= 4


@pytest.mark.anyio
async def test_schema_denied_keeps_query_result_with_unknown_key(settings: Settings) -> None:
    from tests.unit.test_result_parser import NODE_A

    class DeniedGateway(FakeGateway):
        async def execute(self, statement):
            if statement.startswith('DESCRIBE'):
                raise NebulaMCPError(category='database_error', message='Not permitted')
            return FakeResult([{'n': NODE_A}])

    output = await NebulaService(settings, DeniedGateway()).execute_query(
        QueryInput(statement='USE demo MATCH (n) RETURN n LIMIT 1')
    )
    assert output.status.ok
    assert output.graph.elements.nodes[0].data['primary_key'] is None
    assert output.table.returned_row_count == 1
