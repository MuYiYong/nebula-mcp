from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args, command = parser.parse_known_args(argv)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(command) + "\n")
    if command == ["mcp", "get", "nebula", "--json"]:
        if not args.state.exists():
            print("No MCP server named 'nebula' found.", file=sys.stderr)
            return 1
        print(args.state.read_text(encoding="utf-8"))
        return 0
    if command[:3] == ["mcp", "add", "nebula"]:
        separator = command.index("--")
        launch = command[separator + 1 :]
        payload = {
            "name": "nebula",
            "transport": {
                "type": "stdio",
                "command": launch[0],
                "args": launch[1:],
                "env": None,
                "env_vars": [],
                "cwd": None,
            },
        }
        args.state.write_text(json.dumps(payload), encoding="utf-8")
        return 0
    if command == ["mcp", "remove", "nebula"]:
        if (
            os.environ.get("FAKE_CODEX_REMOVE_FAIL") == "1"
            or os.environ.get("NEBULA_FAKE_CODEX_REMOVE_FAIL") == "1"
        ):
            print("simulated remove failure", file=sys.stderr)
            return 1
        args.state.unlink(missing_ok=True)
        return 0
    print("unsupported fake codex command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
