from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from mcp import Client

from nebula_mcp import server as server_module
from nebula_mcp.errors import NebulaMCPError
from nebula_mcp.server import create_server
from tests.unit.test_service import FakeGateway


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
