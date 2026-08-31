from __future__ import annotations

from collections.abc import Iterable
from typing import Any, ClassVar

from nebula_mcp.models import ResultLimits
from nebula_mcp.result_parser import parse_result

NODE_A = {
    "id": 1,
    "type": "Corp",
    "labels": ["Corporation"],
    "properties": {"name": "A"},
}
NODE_B = {
    "id": 2,
    "type": "Corp",
    "labels": ["Corporation"],
    "properties": {"name": "B"},
}
EDGE_AB = {
    "src_id": 1,
    "dst_id": 2,
    "rank": 0,
    "type": "Invest",
    "labels": ["INVEST"],
    "properties": {"weight": 0.8},
    "direction": "OUTGOING",
}


class OneShotResult:
    status_code = "00000"
    status_message = ""
    latency_us = 17
    extra_info: ClassVar[dict[str, int]] = {"affected_nodes": 0, "affected_edges": 0}
    column_names: ClassVar[list[str]] = ["value"]

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.size = len(rows)
        self.calls = 0

    def as_primitive_by_row(self) -> Iterable[dict[str, Any]]:
        self.calls += 1
        if self.calls > 1:
            raise AssertionError("cursor consumed twice")
        yield from self.rows


def limits(*, rows: int = 10, nodes: int = 10, edges: int = 10, bytes: int = 100_000) -> ResultLimits:
    return ResultLimits(rows=rows, nodes=nodes, edges=edges, bytes=bytes)


def test_path_uses_edges_for_hop_count_and_consumes_rows_once() -> None:
    result = OneShotResult(
        [
            {
                "value": {
                    "string_representation": "(1)-[0]->(2)",
                    "length": 2,
                    "start_node": NODE_A,
                    "end_node": NODE_B,
                    "nodes": [NODE_A, NODE_B],
                    "edges": [EDGE_AB],
                }
            }
        ]
    )

    parsed = parse_result(result, graph="demo", limits=limits())

    assert result.calls == 1
    assert parsed.status.ok is True
    assert parsed.status.latency_us == 17
    assert parsed.graph.paths[0].sdk_length == 2
    assert parsed.graph.paths[0].hop_count == 1
    assert len(parsed.graph.nodes) == 2
    assert len(parsed.graph.edges) == 1


def test_duplicate_nodes_are_replaced_by_richer_values() -> None:
    result = OneShotResult(
        [
            {"value": {"id": 1, "type": "Corp", "labels": [], "properties": {}}},
            {"value": NODE_A},
        ]
    )

    parsed = parse_result(result, graph="demo", limits=limits())

    assert len(parsed.graph.nodes) == 1
    assert parsed.graph.nodes[0].properties == {"name": "A"}
    assert parsed.graph.nodes[0].placeholder is False


def test_edge_only_result_adds_endpoint_placeholders() -> None:
    parsed = parse_result(OneShotResult([{"value": EDGE_AB}]), graph="demo", limits=limits())

    assert len(parsed.graph.edges) == 1
    assert {node.key for node in parsed.graph.nodes} == {"demo:1", "demo:2"}
    assert all(node.placeholder for node in parsed.graph.nodes)


def test_row_node_and_edge_limits_report_exact_reasons() -> None:
    result = OneShotResult(
        [
            {"value": {"nodes": [NODE_A, NODE_B], "edges": [EDGE_AB], "length": 2}},
            {"value": NODE_A},
        ]
    )

    parsed = parse_result(result, graph="demo", limits=limits(rows=1, nodes=1, edges=1))

    assert parsed.table.returned_row_count == 1
    assert parsed.table.result_row_count == 2
    assert parsed.truncation.truncated is True
    assert set(parsed.truncation.reasons) >= {"max_rows", "max_nodes", "max_edges"}


def test_byte_limit_stops_before_oversized_row() -> None:
    result = OneShotResult([{"value": "x" * 200}])

    parsed = parse_result(result, graph=None, limits=limits(bytes=32))

    assert parsed.table.rows == []
    assert parsed.truncation.reasons == ("max_bytes",)


def test_failed_status_is_preserved_without_claiming_success() -> None:
    result = OneShotResult([])
    result.status_code = "42001"
    result.status_message = "syntax error"

    parsed = parse_result(result, graph=None, limits=limits())

    assert parsed.status.ok is False
    assert parsed.status.code == "42001"
    assert parsed.status.message == "syntax error"
