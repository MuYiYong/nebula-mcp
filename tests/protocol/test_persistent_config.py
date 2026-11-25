from __future__ import annotations

import json
import os
import stat
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlsplit

import anyio
import pytest
from mcp import Client

from nebula_mcp import browser_setup, connection_store
from nebula_mcp import server as server_module
from nebula_mcp.config import Settings
from nebula_mcp.errors import NebulaMCPError
from nebula_mcp.server import create_server
from tests.unit.test_service import FakeGateway, FakeResult


@pytest.fixture
def connections_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for name in (
        "NEBULA_ADDRESSES",
        "NEBULA_USERNAME",
        "NEBULA_PASSWORD",
        "NEBULA_ENVIRONMENTS",
        "NEBULA_ENVIRONMENT",
    ):
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / "codex-connections.json"
    monkeypatch.setenv("NEBULA_CONNECTIONS_FILE", str(path))
    return path


@pytest.fixture
def gateways(monkeypatch: pytest.MonkeyPatch) -> list[FakeGateway]:
    created: list[FakeGateway] = []

    class ConfigGateway(FakeGateway):
        def __init__(self, settings):  # type: ignore[no-untyped-def]
            super().__init__()
            self.settings = settings
            self.closed = False
            created.append(self)

        def open(self) -> None:
            if self.settings.addresses.startswith("bad"):
                raise NebulaMCPError(category="connection_error", message="Cannot connect")

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(server_module, "DatabaseGateway", ConfigGateway)
    return created


def connection_payload(name: str | None = None, address: str = "db:9669") -> dict[str, object]:
    payload: dict[str, object] = {
        "addresses": address,
        "username": "reader",
        "password": "config-secret",
    }
    if name is not None:
        payload["name"] = name
    return payload


@pytest.mark.anyio
async def test_configure_persists_and_reloads_in_a_new_server(
    connections_file: Path, gateways: list[FakeGateway]
) -> None:
    async with Client(create_server()) as client:
        configured = await client.call_tool(
            "nebula_configure_connection", connection_payload("dev")
        )
        assert not configured.is_error
        listed = await client.call_tool("nebula_list_environments", {})
        assert listed.structured_content == {"active": "dev", "environments": ["dev"]}

    document = json.loads(connections_file.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    assert document["active"] == "dev"
    assert document["connections"]["dev"]["NEBULA_ADDRESSES"] == "db:9669"
    assert document["connections"]["dev"]["NEBULA_PASSWORD"] == "config-secret"
    assert stat.S_IMODE(connections_file.stat().st_mode) == 0o600

    async with Client(create_server()) as client:
        listed = await client.call_tool("nebula_list_environments", {})
        assert listed.structured_content == {"active": "dev", "environments": ["dev"]}
        tested = await client.call_tool("nebula_test_connection", {})
        assert not tested.is_error
        assert "config-secret" not in tested.model_dump_json()


@pytest.mark.anyio
async def test_multiple_connections_and_switch_survive_restart(
    connections_file: Path, gateways: list[FakeGateway]
) -> None:
    async with Client(create_server()) as client:
        assert not (await client.call_tool(
            "nebula_configure_connection", connection_payload("dev")
        )).is_error
        assert not (await client.call_tool(
            "nebula_configure_connection", connection_payload("prod", "prod:9669")
        )).is_error
        switched = await client.call_tool("nebula_switch_environment", {"name": "dev"})
        assert not switched.is_error

    document = json.loads(connections_file.read_text(encoding="utf-8"))
    assert set(document["connections"]) == {"dev", "prod"}
    assert document["active"] == "dev"

    async with Client(create_server()) as client:
        listed = await client.call_tool("nebula_list_environments", {})
        assert listed.structured_content == {"active": "dev", "environments": ["dev", "prod"]}


@pytest.mark.anyio
async def test_failed_configure_keeps_the_saved_file(
    connections_file: Path, gateways: list[FakeGateway]
) -> None:
    async with Client(create_server()) as client:
        assert not (await client.call_tool(
            "nebula_configure_connection", connection_payload("dev")
        )).is_error
        before = connections_file.read_bytes()
        failed = await client.call_tool(
            "nebula_configure_connection", connection_payload("dev", "bad:9669")
        )
        assert failed.is_error
        assert "config-secret" not in failed.model_dump_json()

    assert connections_file.read_bytes() == before


@pytest.mark.anyio
async def test_explicit_environments_win_over_the_connections_file(
    connections_file: Path, gateways: list[FakeGateway], monkeypatch: pytest.MonkeyPatch
) -> None:
    connections_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "active": "file",
                "connections": {
                    "file": {
                        "NEBULA_ADDRESSES": "file:9669",
                        "NEBULA_USERNAME": "reader",
                        "NEBULA_PASSWORD": "file-secret",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    os.chmod(connections_file, 0o600)
    monkeypatch.setenv(
        "NEBULA_ENVIRONMENTS",
        json.dumps(
            {
                "env": {
                    "NEBULA_ADDRESSES": "env:9669",
                    "NEBULA_USERNAME": "reader",
                    "NEBULA_PASSWORD": "env-secret",
                }
            }
        ),
    )
    monkeypatch.setenv("NEBULA_ENVIRONMENT", "env")

    async with Client(create_server()) as client:
        listed = await client.call_tool("nebula_list_environments", {})
        assert listed.structured_content == {"active": "env", "environments": ["env"]}

    assert "file-secret" in connections_file.read_text(encoding="utf-8")


@pytest.mark.anyio
async def test_invalid_file_can_be_repaired_by_configure(
    connections_file: Path, gateways: list[FakeGateway]
) -> None:
    connections_file.write_text("{broken", encoding="utf-8")
    os.chmod(connections_file, 0o600)

    async with Client(create_server()) as client:
        failed = await client.call_tool(
            "nebula_execute_query", {"statement": "RETURN 1"}
        )
        assert failed.is_error
        assert failed.structured_content["error"]["code"] == "INVALID_CONNECTIONS_FILE"
        repaired = await client.call_tool(
            "nebula_configure_connection", connection_payload("dev")
        )
        assert not repaired.is_error
        listed = await client.call_tool("nebula_list_environments", {})
        assert listed.structured_content == {"active": "dev", "environments": ["dev"]}

    document = json.loads(connections_file.read_text(encoding="utf-8"))
    assert document["active"] == "dev"


@pytest.mark.anyio
async def test_tool_schema_exposes_optional_connection_name(
    connections_file: Path, gateways: list[FakeGateway]
) -> None:
    async with Client(create_server()) as client:
        tools = (await client.list_tools()).tools
    configure = next(tool for tool in tools if tool.name == "nebula_configure_connection")
    assert "name" in configure.input_schema["properties"]
    assert "name" not in configure.input_schema.get("required", [])
    assert not any(tool.name == "nebula_open_connection_settings" for tool in tools)


async def setup_request(
    page: str, route: str, payload: dict[str, object] | None = None
) -> tuple[int, dict[str, object]]:
    url = urlsplit(page)

    def request() -> tuple[int, dict[str, object]]:
        conn = HTTPConnection("127.0.0.1", url.port, timeout=5)
        try:
            if payload is None:
                conn.request("GET", url.path + route)
            else:
                conn.request("POST", url.path + route, json.dumps(payload), {
                    "Origin": f"{url.scheme}://{url.netloc}",
                    "Content-Type": "application/json",
                })
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    return await anyio.to_thread.run_sync(request)


def browser_payload(**overrides: object) -> dict[str, object]:
    return {**connection_payload(), "connect_timeout_ms": 30_000, "tls_enabled": False, **overrides}


@pytest.mark.anyio
async def test_marketplace_setup_browser_saves_queries_and_reloads(
    connections_file: Path, gateways: list[FakeGateway], monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls: list[str] = []
    monkeypatch.setattr(browser_setup, "_open_browser", urls.append)
    async with Client(create_server(codex_marketplace=True)) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        assert "nebula_configure_connection" not in tools
        opener = tools["nebula_open_connection_settings"]
        assert opener.title == "配置悦数连接"
        assert opener.input_schema.get("properties", {}) == {}
        missing = await client.call_tool("nebula_test_connection", {})
        assert "nebula_open_connection_settings" in missing.structured_content["error"]["suggestion"]
        opened = await client.call_tool(opener.name, {})
        assert opened.structured_content["status"] == "browser_opened"
        assert "http://" not in opened.model_dump_json()
        assert await setup_request(urls[-1], "state") == (200, {
            "addresses": "", "username": "", "has_password": False,
            "tls_enabled": False, "connect_timeout_ms": 30_000,
        })
        status, missing_password = await setup_request(urls[-1], "save", browser_payload(password=""))
        assert status == 400 and missing_password["field"] == "password"
        assert not connections_file.exists() and not gateways
        assert await setup_request(urls[-1], "save", browser_payload()) == (200, {"ok": True})
        gateways[-1].results.append(FakeResult([{"value": 1}]))
        result = await client.call_tool("nebula_execute_query", {
            "statement": "RETURN 1 AS value", "graph": "demo",
        })
        assert not result.is_error
        assert result.structured_content["table"]["rows"] == [{"value": 1}]

    assert connection_store.load(connections_file)[1] == "default"
    if os.name != "nt":
        assert stat.S_IMODE(connections_file.stat().st_mode) == 0o600
    async with Client(create_server(codex_marketplace=True)) as client:
        tested = await client.call_tool("nebula_test_connection", {})
        assert not tested.is_error
        assert "config-secret" not in tested.model_dump_json()


@pytest.mark.anyio
async def test_marketplace_failed_edits_keep_session_and_disk_and_blank_retains_credentials(
    connections_file: Path, gateways: list[FakeGateway], monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls: list[str] = []
    monkeypatch.setattr(browser_setup, "_open_browser", urls.append)
    original = Settings.from_env({
        "NEBULA_ADDRESSES": "old:9669", "NEBULA_USERNAME": "reader",
        "NEBULA_PASSWORD": "previous-secret", "NEBULA_REQUEST_TIMEOUT_MS": "42000",
        "NEBULA_DEFAULT_GRAPH": "demo",
    })
    connection_store.save(connections_file, {"old": original}, "old")
    before = connections_file.read_bytes()
    async with Client(create_server(codex_marketplace=True)) as client:
        await client.call_tool("nebula_open_connection_settings", {})
        status, state = await setup_request(urls[-1], "state")
        assert status == 200 and state["has_password"] and "password" not in state
        assert state["addresses"] == "old:9669" and state["username"] == "reader"
        status, error = await setup_request(urls[-1], "save", browser_payload(addresses="bad:9669"))
        assert status == 422 and error["code"] == "CONNECTION_TEST_FAILED"
        assert connections_file.read_bytes() == before
        assert gateways[1].closed and not gateways[0].closed
        assert not (await client.call_tool("nebula_test_connection", {})).is_error
        assert await setup_request(urls[-1], "save", browser_payload(password="")) == (200, {"ok": True})
        assert gateways[0].closed
    updated, selected = connection_store.load(connections_file)
    assert selected == "old"
    assert updated["old"].password == original.password
    assert updated["old"].default_graph == original.default_graph
    assert updated["old"].request_timeout_ms == original.request_timeout_ms


@pytest.mark.anyio
async def test_marketplace_stale_browser_cannot_overwrite_newer_settings(
    connections_file: Path, gateways: list[FakeGateway], monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls: list[str] = []
    monkeypatch.setattr(browser_setup, "_open_browser", urls.append)
    async with Client(create_server(codex_marketplace=True)) as first:
        await first.call_tool("nebula_open_connection_settings", {})
        async with Client(create_server(codex_marketplace=True)) as second:
            await second.call_tool("nebula_open_connection_settings", {})
            assert await setup_request(urls[1], "save", browser_payload()) == (200, {"ok": True})
        status, error = await setup_request(urls[0], "save", browser_payload(addresses="other:9669"))
        assert status == 409 and error["code"] == "CONNECTION_SETTINGS_CHANGED"
        assert connection_store.load(connections_file)[0]["default"].addresses == "db:9669"
