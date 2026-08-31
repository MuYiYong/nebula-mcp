from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def markdown_section(text: str, heading: str) -> str:
    start = text.index(heading)
    level = len(heading) - len(heading.lstrip("#"))
    next_heading = re.compile(rf"^#{{1,{level}}} ", re.MULTILINE).search(
        text, start + len(heading)
    )
    end = len(text) if next_heading is None else next_heading.start()
    return text[start:end]


def test_readme_documents_required_workflow_and_safety() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    installation = markdown_section(text, "## 安装")
    workflow = markdown_section(text, "## 推荐工作流")
    mutation = markdown_section(text, "## 只读与 mutation 边界")
    results = markdown_section(text, "## 查询结果")
    developer = markdown_section(text, "## 开发与本地验证")

    assert "codex mcp add" in installation
    assert "NEBULA_ALLOW_MUTATIONS=false" in installation
    for required in ("gql-query-generator", "EXPLAIN", "静态校验", "执行验证"):
        assert required in workflow
    assert "nebula_execute_mutation" in mutation
    assert "只读账号" in developer
    for required in ("cytoscape-elements-v1", "vega-lite-v5"):
        assert required in results


def test_readme_documents_release_install_desktop_journey_and_security() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    installation = markdown_section(text, "## 安装")
    desktop = markdown_section(text, "### 配置 Codex Desktop")

    assert "GitHub Release" in installation
    assert "`install.py`" in installation
    assert "python3 install.py" in installation
    assert [
        installation.index(fragment)
        for fragment in ("GitHub Release", "`install.py`", "python3 install.py")
    ] == sorted(
        installation.index(fragment)
        for fragment in ("GitHub Release", "`install.py`", "python3 install.py")
    )
    assert "-e '.[dev]'" not in installation
    assert ".venv/bin/python -m build" not in installation
    assert "CONFIGURATION_REQUIRED" in installation
    assert text.index("python3 install.py") < text.index("### 配置 Codex Desktop")

    journey_steps = (
        "Settings > MCP servers > nebula",
        "NEBULA_ADDRESSES",
        "NEBULA_USERNAME",
        "NEBULA_PASSWORD",
        "NEBULA_CONNECT_TIMEOUT_MS=30000",
        "NEBULA_ALLOW_MUTATIONS=false",
        "保存设置并重启 MCP",
        "nebula_test_connection",
    )
    positions = [desktop.index(step) for step in journey_steps]
    assert positions == sorted(positions)
    for disclosure in (
        "config.toml",
        "明文",
        "不使用 Keychain",
    ):
        assert disclosure in desktop
    assert "不要共享该文件" in desktop
    assert "不是加密" in desktop


def test_readme_documents_release_lifecycle_and_developer_boundary() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    lifecycle = markdown_section(text, "### 升级、冲突与卸载")
    developer = markdown_section(text, "## 开发与本地验证")

    assert "python3 install.py" in lifecycle
    assert "不会 remove/add" in lifecycle
    assert "保留现有环境变量" in lifecycle
    assert "--replace-registration" in lifecycle
    assert "会删除该旧注册的环境变量" in lifecycle
    assert "不会合并或恢复" in lifecycle
    assert "python3 install.py --uninstall" in lifecycle

    editable_install = ".venv/bin/python -m pip install -e '.[dev]'"
    wheel_build = ".venv/bin/python -m build"
    assert editable_install in developer
    assert wheel_build in developer
    assert text.count(editable_install) == 1
    assert text.count(wheel_build) == 1


def test_readme_documents_windows_powershell_lifecycle_and_acl_boundary() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    installation = markdown_section(text, "## 安装")

    for required in (
        "PowerShell",
        "Invoke-WebRequest",
        "py -3 install.py",
        "py -3 install.py --uninstall",
        "LOCALAPPDATA",
        "继承 ACL",
        "junction/reparse point",
        "不使用 POSIX chmod",
    ):
        assert required in installation
    assert "bash/zsh" in installation


def test_readme_intro_describes_portable_local_codex_use() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    intro = text[: text.index("## 安装")]

    assert "本地 Codex" in intro
    assert "macOS/Codex" not in intro


def test_env_example_documents_desktop_only_configuration() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    for required in (
        "不会被 Server 自动读取",
        "Release 安装后",
        "Codex 桌面",
        "真实值不得提交",
        "NEBULA_ALLOW_MUTATIONS=false",
        "NEBULA_MAX_ROWS=100",
    ):
        assert required in text


def test_readme_documents_all_six_tools() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    tools = markdown_section(text, "## 工具")
    for tool_name in (
        "nebula_test_connection",
        "nebula_list_graphs",
        "nebula_get_graph_schema",
        "nebula_validate_gql",
        "nebula_execute_query",
        "nebula_execute_mutation",
    ):
        assert tool_name in tools


def test_cli_help_does_not_require_database_configuration() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "nebula_mcp", "--help"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "stdio" in completed.stdout


def test_repository_contains_no_runtime_password() -> None:
    runtime_password = os.getenv("NEBULA_PASSWORD")
    if not runtime_password:
        pytest.skip("runtime password is not present in this process")
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    for raw_path in tracked:
        if raw_path:
            path = ROOT / os.fsdecode(raw_path)
            assert runtime_password not in path.read_text(errors="ignore")
