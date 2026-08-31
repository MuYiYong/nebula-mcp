"""Deterministic stdio MCP process used only by protocol tests."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, ClassVar

from pydantic import SecretStr

from nebula_mcp.config import Settings
from nebula_mcp.server import create_server
from nebula_mcp.service import NebulaService


class FakeResult:
    status_code = "00000"
    status_message = ""
    latency_us = 1
    extra_info: ClassVar[dict[str, Any]] = {}
    column_names: ClassVar[list[str]] = []
    size = 0

    def as_primitive_by_row(self) -> Iterable[dict[str, Any]]:
        return iter(())


class FakeGateway:
    async def version(self) -> str:
        return "5.3.0"

    async def execute(self, statement: str) -> FakeResult:
        del statement
        return FakeResult()


def main() -> None:
    settings = Settings(
        addresses="fixture.invalid:9669",
        username="fixture",
        password=SecretStr("fixture-only"),
    )
    service = NebulaService(settings, FakeGateway())
    create_server(service=service).run("stdio")


if __name__ == "__main__":
    main()
