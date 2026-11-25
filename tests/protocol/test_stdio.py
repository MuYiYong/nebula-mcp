from __future__ import annotations

import os
import sys
from pathlib import Path

import anyio
import pytest
from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.anyio
async def test_stdio_subprocess_initializes_lists_and_calls_tools() -> None:
    wheel_python = os.getenv("NEBULA_WHEEL_PYTHON")
    params = StdioServerParameters(
        command=wheel_python or sys.executable,
        args=[str(ROOT / "tests/fixtures/fake_stdio_server.py")],
        cwd=ROOT,
        env={} if wheel_python else {"PYTHONPATH": str(ROOT / "src")},
    )

    async with Client(params) as client:
        tools = await client.list_tools()
        result = await client.call_tool("nebula_test_connection", {})

    assert len(tools.tools) == 12
    assert result.is_error is False
    assert result.structured_content["version"] == "5.3.0"


@pytest.mark.anyio
async def test_production_stdio_subprocess_initializes_without_configuration() -> None:
    wheel_python = os.getenv("NEBULA_WHEEL_PYTHON")
    params = StdioServerParameters(
        command=wheel_python or sys.executable,
        args=["-m", "nebula_mcp"],
        cwd=ROOT,
        env={} if wheel_python else {"PYTHONPATH": str(ROOT / "src")},
    )

    async with Client(params) as client:
        tools = await client.list_tools()
        result = await client.call_tool("nebula_test_connection", {})

    assert len(tools.tools) == 12
    assert result.is_error is True
    assert result.structured_content["error"]["code"] == "CONFIGURATION_REQUIRED"


@pytest.mark.anyio
async def test_marketplace_stdio_exposes_browser_setup_and_packages_assets(tmp_path: Path) -> None:
    wheel_python = os.getenv("NEBULA_WHEEL_PYTHON")
    env = {"NEBULA_CONNECTIONS_FILE": str(tmp_path / "connections.json")}
    if not wheel_python:
        env["PYTHONPATH"] = str(ROOT / "src")
    python = wheel_python or sys.executable
    flags = ["-I"] if wheel_python else []
    with anyio.fail_after(30):
        await anyio.run_process(
            [python, *flags, "-c", "from nebula_mcp.browser_setup import _load_assets; _load_assets()"],
            env={**os.environ, **env}, cwd=tmp_path, check=True,
        )
    params = StdioServerParameters(
        command=python, args=[*flags, "-m", "nebula_mcp", "--codex-marketplace"],
        cwd=tmp_path, env=env,
    )
    async with Client(params) as client:
        names = {tool.name for tool in (await client.list_tools()).tools}
        assert "nebula_open_connection_settings" in names
        assert "nebula_configure_connection" not in names


@pytest.mark.anyio
async def test_dsh_stdio_exposes_only_restricted_tools_and_ignores_named_environment(
    tmp_path: Path,
) -> None:
    wheel_python = os.getenv("NEBULA_WHEEL_PYTHON")
    home = tmp_path / "home"
    codex_home = tmp_path / "codex"
    home.mkdir()
    codex_home.mkdir()
    env = {
        "HOME": str(home),
        "CODEX_HOME": str(codex_home),
        # An unrestricted server would report INVALID_ENVIRONMENTS. This is deliberately
        # not a usable profile and no endpoint or credentials are supplied.
        "NEBULA_ENVIRONMENTS": "not valid JSON",
        "NEBULA_ENVIRONMENT": "ignored_profile",
        "NEBULA_ALLOW_MUTATIONS": "true",
    }
    if not wheel_python:
        env["PYTHONPATH"] = str(ROOT / "src")
    params = StdioServerParameters(
        command=wheel_python or sys.executable,
        args=["-I", "-m", "nebula_mcp.dsh_stdio"] if wheel_python else ["-m", "nebula_mcp.dsh_stdio"],
        cwd=tmp_path,
        env=env,
    )

    async with Client(params) as client:
        tools = await client.list_tools()
        result = await client.call_tool("nebula_test_connection", {})

    # The four tools omitted here are configuration, list/switch environment, and mutation.
    assert {tool.name for tool in tools.tools} == {
        "nebula_execute_query",
        "nebula_get_graph_schema",
        "nebula_list_graphs",
        "nebula_render_graph",
        "nebula_render_result",
        "nebula_select_graph",
        "nebula_test_connection",
        "nebula_validate_gql",
    }
    assert result.is_error is True
    error = result.structured_content["error"]
    assert error["code"] == "CONFIGURATION_REQUIRED"
    assert set(error["variables"]) == {"NEBULA_ADDRESSES", "NEBULA_PASSWORD", "NEBULA_USERNAME"}
    assert "Settings" in error["suggestion"]
    assert "nebula_configure_connection" not in error["suggestion"]
