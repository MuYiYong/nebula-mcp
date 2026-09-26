from __future__ import annotations

import pytest
from pydantic import ValidationError

from nebula_mcp.errors import NebulaMCPError
from nebula_mcp.expansion import build_expand_statement
from nebula_mcp.models import ExpandNodeInput


@pytest.mark.parametrize(
    ("graph", "prefix"),
    [
        ("demo", "USE demo"),
        ("/default_schema/demo", "USE /default_schema/demo"),
        ("#scratch", "USE #scratch"),
    ],
)
def test_build_expand_statement_uses_fixed_shape(graph: str, prefix: str) -> None:
    statement = build_expand_statement(graph, 289166301065117700, 50)

    assert statement == (
        f"{prefix}\n"
        "MATCH (source WHERE element_id(source) = 289166301065117700)-[edge]-(neighbor)\n"
        "RETURN source, edge, neighbor\n"
        "LIMIT 50"
    )


@pytest.mark.parametrize(
    "graph",
    ["demo; DROP GRAPH x", "demo graph", "/demo/../x", "", "#bad/name"],
)
def test_build_expand_statement_rejects_graph_injection(graph: str) -> None:
    with pytest.raises(NebulaMCPError, match="graph reference"):
        build_expand_statement(graph, 1, 20)


@pytest.mark.parametrize(
    "element_id",
    [str(-(2**63) - 1), str(2**63), True, 1, "01", "+1", " 1", "1.0"],
)
def test_expand_node_input_requires_a_canonical_int64_string(element_id: object) -> None:
    with pytest.raises(ValidationError):
        ExpandNodeInput(graph="demo", element_id=element_id)  # type: ignore[arg-type]


@pytest.mark.parametrize("element_id", [str(-(2**63)), "0", str(2**63 - 1)])
def test_expand_node_input_accepts_full_int64_range_without_json_precision_loss(
    element_id: str,
) -> None:
    request = ExpandNodeInput(graph="demo", element_id=element_id)

    assert request.element_id == element_id


@pytest.mark.parametrize("max_rows", [0, 10_001])
def test_expand_node_input_bounds_the_row_limit(max_rows: int) -> None:
    with pytest.raises(ValidationError):
        ExpandNodeInput(graph="demo", element_id="1", max_rows=max_rows)
