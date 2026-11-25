"""One-shot read-only connection probe used by the DSH settings test action."""

from __future__ import annotations

import asyncio
import json

from nebula_mcp.config import load_settings
from nebula_mcp.database import DatabaseGateway
from nebula_mcp.service import NebulaService


async def run() -> None:
    settings, _problem = load_settings()
    if settings is None:
        print(json.dumps({"ok": False, "code": "configuration", "message": "连接配置不完整或无效。"}))
        return
    gateway = DatabaseGateway(settings)
    try:
        gateway.open()
        result = await NebulaService(settings, gateway).test_connection()
        print(json.dumps({"ok": True, "version": result.version}))
    except Exception as error:  # noqa: BLE001 - one-shot probe must always report a redacted failure
        code = getattr(error, "code", "connection")
        message = getattr(error, "message", None) or str(error)
        print(json.dumps({"ok": False, "code": str(code)[:64], "message": str(message)[:300]}))
    finally:
        gateway.close()


if __name__ == "__main__":
    asyncio.run(run())
