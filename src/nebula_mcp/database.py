"""Pooled YueShu 5.3 database access."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from threading import RLock
from typing import Any, Protocol, cast

import anyio
from nebulagraph_python.client.nebula_pool import (  # type: ignore[import-untyped]
    NebulaPool,
    NebulaPoolConfig,
)

from nebula_mcp.config import Settings
from nebula_mcp.errors import NebulaMCPError


class ResultLike(Protocol):
    """The public ResultSet surface consumed by the result parser."""

    status_code: str
    status_message: str
    latency_us: int
    extra_info: Mapping[str, Any]
    column_names: list[str]
    size: int

    def as_primitive_by_row(self) -> Iterable[dict[str, Any]]: ...


class ClientLike(Protocol):
    def execute(self, statement: str) -> ResultLike: ...

    def get_version(self) -> str: ...


class PoolLike(Protocol):
    def get_client(self) -> ClientLike: ...

    def return_client(self, client: ClientLike) -> None: ...

    def close(self) -> None: ...


PoolFactory = Callable[[NebulaPoolConfig], PoolLike]


def _default_pool_factory(config: NebulaPoolConfig) -> PoolLike:
    return cast(PoolLike, NebulaPool(config))


class DatabaseGateway:
    """Owns a NebulaPool and safely offloads its synchronous calls."""

    def __init__(self, settings: Settings, pool_factory: PoolFactory | None = None) -> None:
        self._settings = settings
        self._pool_factory = pool_factory or _default_pool_factory
        self._pool: PoolLike | None = None
        self._client: ClientLike | None = None
        self._session_lock = RLock()

    def open(self) -> None:
        if self._pool is not None:
            return
        config = NebulaPoolConfig(
            addresses=self._settings.addresses,
            user_name=self._settings.username,
            password=self._settings.password.get_secret_value(),
            min_client_size=self._settings.pool_min_size,
            max_client_size=self._settings.pool_max_size,
            max_wait_ms=self._settings.pool_wait_timeout_ms,
            connect_timeout_ms=self._settings.connect_timeout_ms,
            request_timeout_ms=self._settings.request_timeout_ms,
            schema=self._settings.default_schema,
            graph=self._settings.default_graph,
            timezone=self._settings.timezone,
            enable_tls=self._settings.tls_enabled,
        )
        try:
            self._pool = self._pool_factory(config)
        except Exception as exc:  # noqa: BLE001 - redact all SDK startup failures at boundary
            raise _safe_database_error(exc, operation="connect") from None

    def close(self) -> None:
        with self._session_lock:
            pool, self._pool = self._pool, None
            client, self._client = self._client, None
            if pool is not None:
                try:
                    if client is not None:
                        pool.return_client(client)
                finally:
                    pool.close()

    def _require_pool(self) -> PoolLike:
        if self._pool is None:
            raise NebulaMCPError(
                category="configuration_error",
                message="Database gateway is not open",
                suggestion="Open the database gateway before executing tools",
            )
        return self._pool

    def _require_client(self) -> ClientLike:
        pool = self._require_pool()
        if self._client is None:
            self._client = pool.get_client()
        return self._client

    def _execute_sync(self, statement: str) -> ResultLike:
        with self._session_lock:
            try:
                return self._require_client().execute(statement)
            except NebulaMCPError:
                raise
            except Exception as exc:  # noqa: BLE001 - redact SDK failures
                raise _safe_database_error(exc, operation="query") from None

    async def execute(self, statement: str) -> ResultLike:
        return await anyio.to_thread.run_sync(self._execute_sync, statement)

    def _version_sync(self) -> str:
        with self._session_lock:
            try:
                client = self._require_client()
                # SDK get_version() is cached. Check the retained session itself
                # without borrowing a new client or silently reconnecting.
                health = client.execute("RETURN 1")
                if health.status_code != "00000":
                    raise NebulaMCPError(
                        category="connection_error", database_code=health.status_code,
                        message="Database session health check failed",
                        suggestion="Check database availability and explicitly reconfigure "
                        "the connection if the session has expired",
                    )
                return client.get_version()
            except NebulaMCPError:
                raise
            except Exception as exc:  # noqa: BLE001 - redact SDK failures
                raise _safe_database_error(exc, operation="version") from None

    async def version(self) -> str:
        return await anyio.to_thread.run_sync(self._version_sync)


def _safe_database_error(exc: Exception, *, operation: str) -> NebulaMCPError:
    exception_name = type(exc).__name__.lower()
    if "auth" in exception_name:
        return NebulaMCPError(
            category="authentication_error",
            message="Database authentication failed",
            suggestion="Check the configured database username and password",
        )
    if isinstance(exc, TimeoutError) or "timeout" in exception_name:
        return NebulaMCPError(
            category="connection_error",
            message="Database request timed out",
            retryable=True,
            suggestion="Check network reachability and configured timeouts",
        )
    if operation == "connect":
        return NebulaMCPError(
            category="connection_error",
            message="Database connection failed",
            retryable=True,
            suggestion="Check host, port, TLS mode, and server availability",
        )
    if operation == "version":
        return NebulaMCPError(
            category="database_error",
            message="Failed to read database version",
            retryable=True,
        )
    return NebulaMCPError(
        category="database_error",
        message="Database query failed",
        retryable=False,
        suggestion="Validate the GQL and target graph before retrying",
    )
