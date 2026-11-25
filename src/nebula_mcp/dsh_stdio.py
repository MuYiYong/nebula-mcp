"""Fixed, read-only stdio entry point used by the DSH bundle."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from nebula_mcp import __version__
from nebula_mcp.server import create_server


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="nebula-mcp-dsh")
    parser.add_argument("--version", action="version", version=f"nebula-mcp-dsh {__version__}")
    parser.parse_args(argv)
    create_server(dsh_read_only=True).run("stdio")


if __name__ == "__main__":
    main()
