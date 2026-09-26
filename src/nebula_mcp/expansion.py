"""Safe fixed-shape GQL for interactive one-hop graph expansion."""

from __future__ import annotations

import re

from nebula_mcp.errors import NebulaMCPError

GRAPH_REFERENCE = re.compile(
    r"(?:(?:/[A-Za-z_][A-Za-z0-9_]*)+|#[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*)\Z"
)


def build_expand_statement(graph: str, element_id: int, limit: int) -> str:
    """Build a bounded one-hop query from validated scalar inputs."""
    if GRAPH_REFERENCE.fullmatch(graph) is None:
        raise NebulaMCPError(
            category="validation_error",
            message="Invalid graph reference for node expansion",
            suggestion="Use the graph reference returned by the original query",
        )
    return (
        f"USE {graph}\n"
        f"MATCH (source WHERE element_id(source) = {element_id})-[edge]-(neighbor)\n"
        "RETURN source, edge, neighbor\n"
        f"LIMIT {limit}"
    )
