from __future__ import annotations

import pytest
from pydantic import SecretStr

from nebula_mcp.config import Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        addresses="db-a:9669,db-b:9669",
        username="reader",
        password=SecretStr("runtime-secret"),
        default_schema="default_schema",
        default_graph="demo_graph",
        connect_timeout_ms=4_000,
        request_timeout_ms=8_000,
        pool_wait_timeout_ms=2_000,
        pool_min_size=1,
        pool_max_size=3,
        timezone="Asia/Shanghai",
    )
