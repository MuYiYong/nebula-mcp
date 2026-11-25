from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from nebula_mcp import connection_store
from nebula_mcp.config import Settings
from nebula_mcp.errors import NebulaMCPError

BASE_ENV = {
    "NEBULA_ADDRESSES": "db-a:9669,db-b:9669",
    "NEBULA_USERNAME": "reader",
    "NEBULA_PASSWORD": "test-secret-value",
}


def settings(**overrides: str) -> Settings:
    return Settings.from_env({**BASE_ENV, **overrides})


def test_missing_file_means_no_connections(tmp_path: Path) -> None:
    assert connection_store.load(tmp_path / "missing.json") == ({}, None)


def test_save_and_load_roundtrip_keeps_active_connection(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "codex-connections.json"
    first = settings(NEBULA_TLS_ENABLED="true", NEBULA_DEFAULT_SCHEMA="demo")
    second = settings(NEBULA_ADDRESSES="db-c:9669", NEBULA_USERNAME="writer")

    connection_store.save(path, {"dev": first, "prod": second}, "prod")
    loaded, active = connection_store.load(path)

    assert active == "prod"
    assert set(loaded) == {"dev", "prod"}
    assert loaded["dev"].addresses == first.addresses
    assert loaded["dev"].password.get_secret_value() == "test-secret-value"
    assert loaded["dev"].tls_enabled is True
    assert loaded["dev"].default_schema == "demo"
    assert loaded["prod"].username == "writer"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert b"test-secret-value" in path.read_bytes()


def test_single_connection_becomes_active_when_active_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "connections.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "active": None,
                "connections": {
                    "only": {
                        "NEBULA_ADDRESSES": "db:9669",
                        "NEBULA_USERNAME": "reader",
                        "NEBULA_PASSWORD": "secret",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    os.chmod(path, 0o600)

    loaded, active = connection_store.load(path)

    assert active == "only"
    assert set(loaded) == {"only"}


def test_save_is_atomic_and_leaves_no_temporary_files(tmp_path: Path) -> None:
    path = tmp_path / "connections.json"
    connection_store.save(path, {"dev": settings()}, "dev")

    assert [entry.name for entry in tmp_path.iterdir()] == ["connections.json"]


def test_save_replaces_existing_file_with_restricted_mode(tmp_path: Path) -> None:
    path = tmp_path / "connections.json"
    path.write_text("old", encoding="utf-8")
    os.chmod(path, 0o644)

    connection_store.save(path, {"dev": settings()}, "dev")

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    loaded, active = connection_store.load(path)
    assert active == "dev"
    assert set(loaded) == {"dev"}


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission check")
def test_load_rejects_group_or_world_readable_file(tmp_path: Path) -> None:
    path = tmp_path / "connections.json"
    connection_store.save(path, {"dev": settings()}, "dev")
    os.chmod(path, 0o644)

    with pytest.raises(NebulaMCPError) as caught:
        connection_store.load(path)

    assert caught.value.code == "CONNECTION_FILE_PERMISSIONS"
    assert "test-secret-value" not in str(caught.value)


def test_load_rejects_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    connection_store.save(real, {"dev": settings()}, "dev")
    link = tmp_path / "link.json"
    link.symlink_to(real)

    with pytest.raises(NebulaMCPError) as caught:
        connection_store.load(link)

    assert caught.value.code == "INVALID_CONNECTIONS_FILE"


def test_save_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(target)

    with pytest.raises(NebulaMCPError) as caught:
        connection_store.save(link, {"dev": settings()}, "dev")

    assert caught.value.code == "INVALID_CONNECTIONS_FILE"
    assert target.read_text(encoding="utf-8") == "{}"


@pytest.mark.parametrize(
    ("document", "code"),
    [
        ({"schema_version": 2, "connections": {}}, "INVALID_CONNECTIONS_FILE"),
        ({"schema_version": 1}, "INVALID_CONNECTIONS_FILE"),
        ({"schema_version": 1, "connections": {"bad name": {}}}, "INVALID_CONNECTIONS_FILE"),
        (
            {"schema_version": 1, "active": "missing", "connections": {"dev": {}}},
            "INVALID_CONNECTIONS_FILE",
        ),
        (
            {
                "schema_version": 1,
                "active": "dev",
                "connections": {"dev": {"NEBULA_ADDRESSES": "db:9669", "UNKNOWN": "x"}},
            },
            "INVALID_CONNECTIONS_FILE",
        ),
    ],
)
def test_load_rejects_invalid_documents(
    tmp_path: Path, document: dict[str, object], code: str
) -> None:
    path = tmp_path / "connections.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    os.chmod(path, 0o600)

    with pytest.raises(NebulaMCPError) as caught:
        connection_store.load(path)

    assert caught.value.code == code
    assert "test-secret-value" not in str(caught.value)


def test_load_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "connections.json"
    path.write_text("{not-json", encoding="utf-8")
    os.chmod(path, 0o600)

    with pytest.raises(NebulaMCPError) as caught:
        connection_store.load(path)

    assert caught.value.code == "INVALID_CONNECTIONS_FILE"


def test_save_rejects_active_connection_outside_map(tmp_path: Path) -> None:
    with pytest.raises(NebulaMCPError) as caught:
        connection_store.save(tmp_path / "connections.json", {"dev": settings()}, "prod")

    assert caught.value.code == "INVALID_CONNECTIONS_FILE"


@pytest.mark.parametrize("name", ["", "two words", "x" * 65])
def test_connection_names_are_validated(name: str) -> None:
    with pytest.raises(NebulaMCPError) as caught:
        connection_store.validate_name(name)

    assert caught.value.code == "INVALID_CONNECTION_NAME"


def test_relative_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(NebulaMCPError):
        connection_store.load(Path("relative.json"))
