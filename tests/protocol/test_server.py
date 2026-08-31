from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, ClassVar

import pytest
from mcp import Client

from nebula_mcp import server as server_module
from nebula_mcp.config import Settings
from nebula_mcp.errors import NebulaMCPError
from nebula_mcp.server import create_server
from nebula_mcp.service import NebulaService


class FakeResult:
    status_code = "00000"
    status_message = ""
    latency_us = 7
    extra_info: ClassVar[dict[str, Any]] = {}

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.size = len(rows)
        self.column_names = list(rows[0]) if rows else []

    def as_primitive_by_row(self) -> Iterable[dict[str, Any]]:
        yield from self.rows


class RoutingGateway:
    def __init__(self) -> None:
        self.statements: list[str] = []

    async def version(self) -> str:
        return "5.3.0"

    async def execute(self, statement: str) -> FakeResult:
        self.statements.append(statement)
        if statement.startswith("DESCRIBE GRAPH TYPE"):
            return FakeResult(
                [
                    {
                        "entity_type": "Node",
                        "type_name": "Corp",
                        "type_pattern": "(Corp)",
                        "labels": ["Corporation"],
                        "primary_key/multiedge_key": "id",
                        "properties": {"id": "INT64"},
                    }
                ]
            )
        if statement.startswith("CALL show_graphs"):
            return FakeResult(
                [
                    {
                        "schema": "default_schema",
                        "name": "demo_graph",
                        "graph_type": "demo_type",
                        "owner": "root",
                    }
                ]
            )
        return FakeResult([{"sector": "A", "score": 1.0}])


@pytest.fixture
def service(settings: Settings) -> NebulaService:
    return NebulaService(settings, RoutingGateway())


@pytest.mark.anyio
async def test_server_exposes_complete_prefixed_tool_set(service: NebulaService) -> None:
    server = create_server(service=service)

    async with Client(server) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert set(tools) == {
        "nebula_test_connection",
        "nebula_list_graphs",
        "nebula_get_graph_schema",
        "nebula_validate_gql",
        "nebula_execute_query",
        "nebula_execute_mutation",
    }
    assert tools["nebula_execute_query"].annotations.read_only_hint is True
    assert tools["nebula_execute_query"].annotations.destructive_hint is False
    assert tools["nebula_execute_mutation"].annotations.destructive_hint is True
    assert all(tool.output_schema is not None for tool in tools.values())


@pytest.mark.anyio
async def test_query_presentation_contract_is_delivered_to_mcp_clients(
    service: NebulaService,
) -> None:
    server = create_server(service=service)

    async with Client(server) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        instructions = client.instructions or ""

    query_tool = tools["nebula_execute_query"]
    normalized_instructions = " ".join(instructions.split())
    assert "present every enabled result component together" in normalized_instructions
    assert "render every non-empty vega-lite-v5 chart" in normalized_instructions
    assert "write a human-readable explanation" in normalized_instructions

    description = query_tool.description or ""
    assert "A table does not replace charts or the explanation" in description

    input_properties = query_tool.input_schema["properties"]
    for name in ("include_graph", "include_analysis", "include_charts"):
        assert input_properties[name]["default"] is True
        assert input_properties[name]["type"] == "boolean"

    output_properties = query_tool.output_schema["properties"]
    assert "render" in output_properties["charts"]["description"].lower()
    assert "human-readable explanation" in output_properties["explanation_context"]["description"]


@pytest.mark.anyio
async def test_successful_tool_returns_valid_structured_content(service: NebulaService) -> None:
    server = create_server(service=service)

    async with Client(server) as client:
        result = await client.call_tool("nebula_execute_query", {"statement": "RETURN 1"})

    assert result.is_error is False
    assert result.structured_content["status"]["ok"] is True
    assert result.structured_content["graph"]["format"] == "cytoscape-elements-v1"
    assert result.structured_content["graph"]["elements"]["nodes"] == []
    assert result.structured_content["charts"][0]["format"] == "vega-lite-v5"
    assert result.structured_content["explanation_context"]["facts"] == [
        "Returned 1 row(s).",
        "Extracted 0 node(s) and 0 edge(s).",
    ]


@pytest.mark.anyio
async def test_expected_service_error_is_safe_and_structured(service: NebulaService) -> None:
    server = create_server(service=service)

    async with Client(server) as client:
        result = await client.call_tool("nebula_execute_query", {"statement": "DROP GRAPH demo"})

    assert result.is_error is True
    assert result.structured_content["error"]["category"] == "policy_denied"
    assert "runtime-secret" not in json.dumps(result.structured_content)


@pytest.mark.anyio
async def test_unconfigured_server_initializes_and_returns_variable_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("NEBULA_ADDRESSES", "NEBULA_USERNAME", "NEBULA_PASSWORD"):
        monkeypatch.delenv(name, raising=False)

    async with Client(create_server()) as client:
        tools = await client.list_tools()
        result = await client.call_tool("nebula_test_connection", {})
        resource = await client.read_resource("nebula://connection")

    assert len(tools.tools) == 6
    assert result.is_error is True
    error = result.structured_content["error"]
    assert error["code"] == "CONFIGURATION_REQUIRED"
    assert error["variables"] == [
        "NEBULA_ADDRESSES",
        "NEBULA_PASSWORD",
        "NEBULA_USERNAME",
    ]
    assert json.loads(resource.contents[0].text)["code"] == "CONFIGURATION_REQUIRED"


@pytest.mark.anyio
async def test_partially_configured_server_initializes_and_returns_missing_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEBULA_ADDRESSES", "localhost:9669")
    monkeypatch.setenv("NEBULA_USERNAME", "root")
    monkeypatch.delenv("NEBULA_PASSWORD", raising=False)

    async with Client(create_server()) as client:
        result = await client.call_tool("nebula_test_connection", {})

    assert result.is_error is True
    assert result.structured_content["error"]["variables"] == ["NEBULA_PASSWORD"]


@pytest.mark.anyio
async def test_invalid_configuration_server_initializes_and_returns_variable_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEBULA_ADDRESSES", "not-an-address")
    monkeypatch.setenv("NEBULA_USERNAME", "root")
    monkeypatch.setenv("NEBULA_PASSWORD", "secret")

    async with Client(create_server()) as client:
        result = await client.call_tool("nebula_test_connection", {})

    assert result.is_error is True
    error = result.structured_content["error"]
    assert error["code"] == "CONFIGURATION_REQUIRED"
    assert error["variables"] == ["NEBULA_ADDRESSES"]


@pytest.mark.anyio
async def test_connection_failure_does_not_abort_initialization(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingGateway:
        def __init__(self, resolved: Settings) -> None:
            assert resolved == settings

        def open(self) -> None:
            raise NebulaMCPError(
                category="connection_error",
                message="Database connection failed",
                retryable=True,
            )

        def close(self) -> None:
            raise AssertionError("failed gateway must not be closed as ready")

    monkeypatch.setattr(server_module, "DatabaseGateway", FailingGateway)
    async with Client(create_server(settings=settings)) as client:
        result = await client.call_tool("nebula_list_graphs", {})
        resource = await client.read_resource("nebula://connection")

    assert result.is_error is True
    assert result.structured_content["error"]["category"] == "connection_error"
    assert json.loads(resource.contents[0].text)["category"] == "connection_error"


@pytest.mark.anyio
async def test_connection_and_schema_resources_are_readable(service: NebulaService) -> None:
    server = create_server(service=service)

    async with Client(server) as client:
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        connection = await client.read_resource("nebula://connection")
        graph_schema = await client.read_resource(
            "nebula://schema/default_schema/demo_type"
        )

    assert [str(item.uri) for item in resources.resources] == ["nebula://connection"]
    assert [item.uri_template for item in templates.resource_templates] == [
        "nebula://schema/{schema}/{graph_type}"
    ]
    assert json.loads(connection.contents[0].text)["version"] == "5.3.0"
    assert json.loads(graph_schema.contents[0].text)["entities"][0]["entity_type"] == "Node"
