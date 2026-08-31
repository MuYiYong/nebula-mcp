from __future__ import annotations

from typing import Any

import pytest

from nebula_mcp.config import Settings
from nebula_mcp.database import DatabaseGateway
from nebula_mcp.errors import NebulaMCPError


class FakeResult:
    status_code = "00000"


class FakeClient:
    def __init__(self, *, result: object | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.statements: list[str] = []

    def execute(self, statement: str) -> object:
        self.statements.append(statement)
        if self.error is not None:
            raise self.error
        return self.result

    def get_version(self) -> str:
        if self.error is not None:
            raise self.error
        return "5.3.0"


class FakePool:
    def __init__(self, client: FakeClient) -> None:
        self.client = client
        self.borrowed = 0
        self.returned = 0
        self.closed = False

    def get_client(self) -> FakeClient:
        self.borrowed += 1
        return self.client

    def return_client(self, client: FakeClient) -> None:
        assert client is self.client
        self.returned += 1

    def close(self) -> None:
        self.closed = True


class PoolFactory:
    def __init__(self, pool: FakePool) -> None:
        self.pool = pool
        self.config: Any = None

    def __call__(self, config: object) -> FakePool:
        self.config = config
        return self.pool


@pytest.mark.anyio
async def test_execute_borrows_and_returns_client(settings: Settings) -> None:
    result = FakeResult()
    client = FakeClient(result=result)
    pool = FakePool(client)
    gateway = DatabaseGateway(settings, pool_factory=PoolFactory(pool))
    gateway.open()

    actual = await gateway.execute("RETURN 1")

    assert actual is result
    assert client.statements == ["RETURN 1"]
    assert (pool.borrowed, pool.returned) == (1, 1)


@pytest.mark.anyio
async def test_execute_returns_client_after_database_error(settings: Settings) -> None:
    pool = FakePool(FakeClient(error=RuntimeError("runtime-secret must not escape")))
    gateway = DatabaseGateway(settings, pool_factory=PoolFactory(pool))
    gateway.open()

    with pytest.raises(NebulaMCPError) as caught:
        await gateway.execute("RETURN 1")

    assert caught.value.category == "database_error"
    assert str(caught.value) == "Database query failed"
    assert "runtime-secret" not in str(caught.value)
    assert (pool.borrowed, pool.returned) == (1, 1)


@pytest.mark.anyio
async def test_version_uses_borrowed_client(settings: Settings) -> None:
    pool = FakePool(FakeClient())
    gateway = DatabaseGateway(settings, pool_factory=PoolFactory(pool))
    gateway.open()

    assert await gateway.version() == "5.3.0"
    assert (pool.borrowed, pool.returned) == (1, 1)


def test_open_maps_settings_to_exact_v53_pool_config(settings: Settings) -> None:
    factory = PoolFactory(FakePool(FakeClient()))
    gateway = DatabaseGateway(settings, pool_factory=factory)

    gateway.open()

    assert factory.config.addresses == "db-a:9669,db-b:9669"
    assert factory.config.user_name == "reader"
    assert factory.config.password == "runtime-secret"
    assert factory.config.min_client_size == 1
    assert factory.config.max_client_size == 3
    assert factory.config.max_wait_ms == 2_000
    assert factory.config.connect_timeout_ms == 4_000
    assert factory.config.request_timeout_ms == 8_000
    assert factory.config.schema == "default_schema"
    assert factory.config.graph == "demo_graph"
    assert factory.config.timezone == "Asia/Shanghai"


def test_close_is_idempotent(settings: Settings) -> None:
    pool = FakePool(FakeClient())
    gateway = DatabaseGateway(settings, pool_factory=PoolFactory(pool))
    gateway.open()

    gateway.close()
    gateway.close()

    assert pool.closed is True


@pytest.mark.anyio
async def test_execute_before_open_is_actionable(settings: Settings) -> None:
    gateway = DatabaseGateway(settings, pool_factory=PoolFactory(FakePool(FakeClient())))

    with pytest.raises(NebulaMCPError) as caught:
        await gateway.execute("RETURN 1")

    assert caught.value.category == "configuration_error"
    assert caught.value.suggestion == "Open the database gateway before executing tools"
