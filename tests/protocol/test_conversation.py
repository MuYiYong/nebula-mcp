from __future__ import annotations

import pytest
from mcp import Client

from nebula_mcp import server as server_module
from nebula_mcp.server import create_server
from nebula_mcp.service import NebulaService
from tests.unit.test_conversation import missing_graph
from tests.unit.test_service import FakeGateway, FakeResult


@pytest.mark.anyio
async def test_mcp_graph_choice_resumes_and_scalar_result_can_render(settings):
    gateway = FakeGateway([missing_graph(), FakeResult([]), FakeResult([{"n": 1}])])
    async with Client(create_server(service=NebulaService(settings, gateway))) as client:
        blocked = await client.call_tool("nebula_execute_query", {"statement": "MATCH (n) RETURN n"})
        assert blocked.structured_content["error"]["code"] == "GRAPH_SELECTION_REQUIRED"
        selected = await client.call_tool("nebula_select_graph", {"graph": "demo"})
        assert not selected.is_error
        result = selected.structured_content["result"]
        rendered = await client.call_tool("nebula_render_result", {"result": result, "explanation": "返回一行。"})
        assert not rendered.is_error
        assert rendered.structured_content["result"]["table"]["rows"] == [{"n": 1}]


@pytest.mark.anyio
async def test_mcp_configuration_without_restart_and_failed_update_keeps_connection(monkeypatch):
    for key in ("NEBULA_ADDRESSES", "NEBULA_USERNAME", "NEBULA_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    gateways = []

    class ConfigGateway(FakeGateway):
        def __init__(self, settings):
            super().__init__([FakeResult([{"n": 1}])])
            self.settings = settings
            self.closed = False
            gateways.append(self)

        def open(self):
            if self.settings.addresses.startswith("bad"):
                from nebula_mcp.errors import NebulaMCPError
                raise NebulaMCPError(category="connection_error", message="Cannot connect")

        def close(self):
            self.closed = True

    monkeypatch.setattr(server_module, "DatabaseGateway", ConfigGateway)
    async with Client(create_server()) as client:
        output = await client.call_tool("nebula_configure_connection", {"addresses": "db:9669", "username": "reader", "password": "test-secret"})
        assert not output.is_error
        assert output.structured_content["connected"]
        assert "test-secret" not in str(output)
        failed = await client.call_tool("nebula_configure_connection", {"addresses": "bad:9669", "username": "reader", "password": "test-secret"})
        assert failed.is_error
        assert not gateways[0].closed
        assert gateways[1].closed
        query = await client.call_tool("nebula_execute_query", {"statement": "RETURN 1 AS n"})
        assert not query.is_error
    assert gateways[0].closed


@pytest.mark.anyio
async def test_selection_and_query_do_not_interleave(settings):
    import anyio

    entered = anyio.Event()
    release = anyio.Event()

    class DelayedGateway(FakeGateway):
        async def execute(self, statement):
            self.statements.append(statement)
            if statement == "SESSION SET GRAPH demo":
                entered.set()
                await release.wait()
            return FakeResult([])

    gateway = DelayedGateway()
    async with Client(create_server(service=NebulaService(settings, gateway))) as client:
        async def choose():
            await client.call_tool("nebula_select_graph", {"graph": "demo"})

        async def query():
            await entered.wait()
            await client.call_tool("nebula_execute_query", {"statement": "MATCH (n) RETURN n"})

        async def resource():
            await entered.wait()
            await client.read_resource("nebula://schema/default_schema/demo_type")

        async with anyio.create_task_group() as group:
            group.start_soon(choose)
            group.start_soon(query)
            group.start_soon(resource)
            await entered.wait()
            await anyio.sleep(0.02)
            assert gateway.statements == ["SESSION SET GRAPH demo"]
            release.set()
    assert gateway.statements[0] == "SESSION SET GRAPH demo"
    assert set(gateway.statements[1:]) == {"PROFILE MATCH (n) RETURN n", "DESCRIBE GRAPH TYPE /default_schema/demo_type"}
