"""Persist named Codex connections in the managed runtime data directory.

The Codex plugin has no native settings page. Its MCP tools configure the
server over stdio, and this module stores the result so the next MCP process
can load it without asking the user to run an installer or edit config.toml.

The file contains passwords in plain text. It is therefore written atomically
with mode 0600 on POSIX, and reads reject symlinks, non-regular files, and
group/world-readable files.
"""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from nebula_mcp.config import Settings
from nebula_mcp.errors import NebulaMCPError

SCHEMA_VERSION = 1
MAX_BYTES = 1_048_576
NAME_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")

_RECORD_FIELDS = frozenset(
    {
        "NEBULA_ADDRESSES",
        "NEBULA_USERNAME",
        "NEBULA_PASSWORD",
        "NEBULA_DEFAULT_SCHEMA",
        "NEBULA_DEFAULT_GRAPH",
        "NEBULA_CONNECT_TIMEOUT_MS",
        "NEBULA_REQUEST_TIMEOUT_MS",
        "NEBULA_POOL_WAIT_TIMEOUT_MS",
        "NEBULA_POOL_MIN_SIZE",
        "NEBULA_POOL_MAX_SIZE",
        "NEBULA_TLS_ENABLED",
        "NEBULA_TIMEZONE",
        "NEBULA_ALLOW_MUTATIONS",
        "NEBULA_MAX_ROWS",
        "NEBULA_MAX_NODES",
        "NEBULA_MAX_EDGES",
        "NEBULA_MAX_BYTES",
        "NEBULA_LOG_LEVEL",
    }
)


def _failure(
    code: str,
    message: str,
    suggestion: str | None = None,
) -> NebulaMCPError:
    return NebulaMCPError(
        category="configuration_error",
        code=code,
        message=message,
        suggestion=suggestion,
    )


def validate_name(name: str) -> str:
    if not isinstance(name, str) or NAME_PATTERN.fullmatch(name) is None:
        raise _failure(
            "INVALID_CONNECTION_NAME",
            "连接名称只能包含字母、数字、下划线或短横线，长度 1–64。",
            "Use a short name such as dev, test, or prod.",
        )
    return name


def _settings_record(settings: Settings) -> dict[str, str]:
    record = {
        "NEBULA_ADDRESSES": settings.addresses,
        "NEBULA_USERNAME": settings.username,
        "NEBULA_PASSWORD": settings.password.get_secret_value(),
        "NEBULA_CONNECT_TIMEOUT_MS": str(settings.connect_timeout_ms),
        "NEBULA_REQUEST_TIMEOUT_MS": str(settings.request_timeout_ms),
        "NEBULA_POOL_WAIT_TIMEOUT_MS": str(settings.pool_wait_timeout_ms),
        "NEBULA_POOL_MIN_SIZE": str(settings.pool_min_size),
        "NEBULA_POOL_MAX_SIZE": str(settings.pool_max_size),
        "NEBULA_TLS_ENABLED": "true" if settings.tls_enabled else "false",
        "NEBULA_ALLOW_MUTATIONS": "true" if settings.allow_mutations else "false",
        "NEBULA_MAX_ROWS": str(settings.max_rows),
        "NEBULA_MAX_NODES": str(settings.max_nodes),
        "NEBULA_MAX_EDGES": str(settings.max_edges),
        "NEBULA_MAX_BYTES": str(settings.max_bytes),
        "NEBULA_LOG_LEVEL": settings.log_level,
    }
    if settings.default_schema is not None:
        record["NEBULA_DEFAULT_SCHEMA"] = settings.default_schema
    if settings.default_graph is not None:
        record["NEBULA_DEFAULT_GRAPH"] = settings.default_graph
    if settings.timezone is not None:
        record["NEBULA_TIMEZONE"] = settings.timezone
    return record


def _parse_record(value: object) -> Settings:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        raise _failure(
            "INVALID_CONNECTIONS_FILE",
            "连接配置文件格式无效；每个连接都必须是字符串键值对象。",
            "Configure the connection again with nebula_configure_connection.",
        )
    if any(key not in _RECORD_FIELDS for key in value):
        raise _failure(
            "INVALID_CONNECTIONS_FILE",
            "连接配置包含未知字段。",
            "Configure the connection again with nebula_configure_connection.",
        )
    try:
        return Settings.from_env(value)
    except (ValidationError, ValueError):
        raise _failure(
            "INVALID_CONNECTIONS_FILE",
            "连接配置中的地址、用户名、密码或超时无效。",
            "Configure the connection again with nebula_configure_connection.",
        ) from None


def _validate_path(path: Path) -> None:
    if not path.is_absolute():
        raise _failure(
            "INVALID_CONNECTIONS_FILE",
            "NEBULA_CONNECTIONS_FILE 必须是绝对路径。",
        )


def load(path: Path) -> tuple[dict[str, Settings], str | None]:
    """Read named connections, returning no connections when the file is absent."""

    _validate_path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {}, None
    except OSError:
        raise _failure(
            "INVALID_CONNECTIONS_FILE",
            "无法读取连接配置文件。",
        ) from None

    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise _failure(
            "INVALID_CONNECTIONS_FILE",
            "连接配置文件必须是有权限的普通文件，不能是符号链接。",
        )
    if info.st_size > MAX_BYTES:
        raise _failure(
            "INVALID_CONNECTIONS_FILE",
            "连接配置文件过大。",
        )
    if os.name != "nt" and info.st_mode & 0o077:
        raise _failure(
            "CONNECTION_FILE_PERMISSIONS",
            "连接配置文件对其他用户可读；其中包含数据库密码。",
            f"Run chmod 600 {path} and retry.",
        )

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise _failure(
            "INVALID_CONNECTIONS_FILE",
            "连接配置文件不是有效的 UTF-8 JSON。",
        ) from None

    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
        raise _failure(
            "INVALID_CONNECTIONS_FILE",
            "连接配置文件版本无效。",
        )
    raw_connections = document.get("connections")
    if not isinstance(raw_connections, dict):
        raise _failure(
            "INVALID_CONNECTIONS_FILE",
            "连接配置文件缺少 connections 对象。",
        )
    active = document.get("active")
    if active is not None and not isinstance(active, str):
        raise _failure(
            "INVALID_CONNECTIONS_FILE",
            "连接配置文件的 active 必须是字符串或 null。",
        )

    connections: dict[str, Settings] = {}
    for name, record in raw_connections.items():
        if not isinstance(name, str) or NAME_PATTERN.fullmatch(name) is None:
            raise _failure(
                "INVALID_CONNECTIONS_FILE",
                "连接配置文件包含无效的连接名称。",
            )
        connections[name] = _parse_record(record)

    if active is not None:
        validate_name(active)
        if active not in connections:
            raise _failure(
                "INVALID_CONNECTIONS_FILE",
                "连接配置文件的 active 指向不存在的连接。",
            )
    elif len(connections) == 1:
        active = next(iter(connections))
    return connections, active


def save(path: Path, connections: Mapping[str, Settings], active: str | None) -> None:
    """Atomically write named connections with 0600 permissions."""

    _validate_path(path)
    for name in connections:
        validate_name(name)
    if active is not None:
        validate_name(active)
        if active not in connections:
            raise _failure(
                "INVALID_CONNECTIONS_FILE",
                "active 必须指向已保存的连接。",
            )
    if path.is_symlink():
        raise _failure(
            "INVALID_CONNECTIONS_FILE",
            "拒绝写入符号链接形式的连接配置文件。",
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "active": active,
        "connections": {name: _settings_record(settings) for name, settings in connections.items()},
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        raise _failure(
            "CONNECTION_SAVE_FAILED",
            "无法创建连接配置文件目录。",
        ) from None

    temporary: str | None = None
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=".connections-",
            suffix=".tmp",
            dir=path.parent,
        )
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        if os.name != "nt":
            try:
                directory = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except OSError:
                # The file is already in place; directory fsync is best effort.
                pass
    except OSError:
        raise _failure(
            "CONNECTION_SAVE_FAILED",
            "无法保存连接配置；磁盘权限或空间不足。",
            "Check that the runtime data directory is writable and retry.",
        ) from None
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass
