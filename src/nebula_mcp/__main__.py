"""Command-line entry point for the local stdio server."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from nebula_mcp import __version__
from nebula_mcp.server import create_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nebula-mcp",
        description="Run the YueShu 5.3 MCP server over stdio.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--codex-marketplace", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    create_server(codex_marketplace=args.codex_marketplace).run("stdio")


if __name__ == "__main__":
    main()
