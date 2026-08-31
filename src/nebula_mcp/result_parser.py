"""Single-pass parsing of bounded YueShu query results."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from nebula_mcp.database import ResultLike
from nebula_mcp.models import (
    GraphEdge,
    GraphNode,
    GraphPath,
    ParsedGraph,
    ParsedResult,
    QueryStatus,
    ResultLimits,
    TableResult,
    TruncationInfo,
)
from nebula_mcp.serialization import JsonValue, to_json_value


class _GraphCollector:
    def __init__(self, *, graph: str | None, limits: ResultLimits) -> None:
        self.graph = graph
        self.limits = limits
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, GraphEdge] = {}
        self.paths: list[GraphPath] = []
        self.reasons: list[str] = []

    def add_reason(self, reason: str) -> None:
        if reason not in self.reasons:
            self.reasons.append(reason)

    def node_key(self, raw_id: JsonValue) -> str:
        return f"{self.graph or '_'}:{_stable_component(raw_id)}"

    def edge_key(
        self, src_id: JsonValue, edge_type: str | None, rank: JsonValue, dst_id: JsonValue
    ) -> str:
        return ":".join(
            (
                self.graph or "_",
                _stable_component(src_id),
                edge_type or "",
                _stable_component(rank),
                _stable_component(dst_id),
            )
        )

    def add_node(self, value: Mapping[str, JsonValue], *, placeholder: bool = False) -> str | None:
        raw_id = value.get("id")
        if raw_id is None:
            return None
        key = self.node_key(raw_id)
        properties = _mapping_value(value.get("properties"))
        labels = _string_list(value.get("labels"))
        type_value = value.get("type")
        node = GraphNode(
            key=key,
            graph=self.graph,
            raw_id=raw_id,
            type_name=type_value if isinstance(type_value, str) else None,
            labels=labels,
            properties=properties,
            placeholder=placeholder,
        )
        previous = self.nodes.get(key)
        if previous is not None:
            if not placeholder and (
                previous.placeholder or len(properties) > len(previous.properties)
            ):
                self.nodes[key] = node
            return key
        if len(self.nodes) >= self.limits.nodes:
            self.add_reason("max_nodes")
            return None
        self.nodes[key] = node
        return key

    def ensure_placeholder(self, raw_id: JsonValue) -> str | None:
        key = self.node_key(raw_id)
        if key in self.nodes:
            return key
        return self.add_node({"id": raw_id}, placeholder=True)

    def add_edge(self, value: Mapping[str, JsonValue]) -> str | None:
        src_id = value.get("src_id")
        dst_id = value.get("dst_id")
        if src_id is None or dst_id is None:
            return None
        src_key = self.ensure_placeholder(src_id)
        dst_key = self.ensure_placeholder(dst_id)
        if src_key is None or dst_key is None:
            self.add_reason("max_edges")
            return None
        rank = value.get("rank", 0)
        edge_type_value = value.get("type")
        edge_type = edge_type_value if isinstance(edge_type_value, str) else None
        key = self.edge_key(src_id, edge_type, rank, dst_id)
        if key in self.edges:
            return key
        if len(self.edges) >= self.limits.edges:
            self.add_reason("max_edges")
            return None
        direction = value.get("direction")
        self.edges[key] = GraphEdge(
            key=key,
            graph=self.graph,
            src_id=src_id,
            dst_id=dst_id,
            rank=rank,
            edge_type=edge_type,
            labels=_string_list(value.get("labels")),
            properties=_mapping_value(value.get("properties")),
            direction=direction if isinstance(direction, str) else None,
        )
        return key

    def walk(self, value: JsonValue) -> None:
        if isinstance(value, list):
            for item in value:
                self.walk(item)
            return
        if not isinstance(value, dict):
            return
        if _is_path(value):
            self.add_path(value)
            return
        if _is_edge(value):
            self.add_edge(value)
            return
        if _is_node(value):
            self.add_node(value)
            return
        for item in value.values():
            self.walk(item)

    def add_path(self, value: Mapping[str, JsonValue]) -> None:
        node_keys: list[str] = []
        nodes = value.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if isinstance(node, dict) and _is_node(node):
                    key = self.add_node(node)
                    if key is not None:
                        node_keys.append(key)

        edge_keys: list[str] = []
        edges = value.get("edges")
        if isinstance(edges, list):
            for edge in edges:
                if isinstance(edge, dict) and _is_edge(edge):
                    key = self.add_edge(edge)
                    if key is not None:
                        edge_keys.append(key)

        sdk_length = value.get("length")
        representation = value.get("string_representation")
        self.paths.append(
            GraphPath(
                sdk_length=sdk_length if isinstance(sdk_length, int) else None,
                hop_count=len(edge_keys),
                node_keys=node_keys,
                edge_keys=edge_keys,
                string_representation=representation if isinstance(representation, str) else None,
            )
        )


def parse_result(result: ResultLike, *, graph: str | None, limits: ResultLimits) -> ParsedResult:
    """Consume a database cursor exactly once and build table and graph views."""

    collector = _GraphCollector(graph=graph, limits=limits)
    rows: list[dict[str, Any]] = []
    used_bytes = 0

    for raw_row in result.as_primitive_by_row():
        if len(rows) >= limits.rows:
            collector.add_reason("max_rows")
            break
        converted = to_json_value(raw_row)
        if not isinstance(converted, dict):
            converted = {"value": converted}
        row_bytes = len(
            json.dumps(
                converted,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )
        if used_bytes + row_bytes > limits.bytes:
            collector.add_reason("max_bytes")
            break
        rows.append(converted)
        used_bytes += row_bytes
        collector.walk(converted)

    if result.size > len(rows) and len(rows) >= limits.rows:
        collector.add_reason("max_rows")

    extra_info = to_json_value(result.extra_info)
    status_extra = extra_info if isinstance(extra_info, dict) else {}
    truncation = TruncationInfo(
        truncated=bool(collector.reasons),
        reasons=tuple(collector.reasons),
    )
    return ParsedResult(
        status=QueryStatus(
            ok=result.status_code == "00000",
            code=result.status_code,
            message=result.status_message,
            latency_us=result.latency_us,
            extra_info=status_extra,
        ),
        table=TableResult(
            columns=list(result.column_names),
            rows=rows,
            returned_row_count=len(rows),
            result_row_count=result.size,
            truncated=truncation.truncated,
        ),
        graph=ParsedGraph(
            graph=graph,
            nodes=list(collector.nodes.values()),
            edges=list(collector.edges.values()),
            paths=collector.paths,
        ),
        truncation=truncation,
    )


def _is_node(value: Mapping[str, JsonValue]) -> bool:
    return "id" in value and "src_id" not in value and "dst_id" not in value


def _is_edge(value: Mapping[str, JsonValue]) -> bool:
    return "src_id" in value and "dst_id" in value


def _is_path(value: Mapping[str, JsonValue]) -> bool:
    return isinstance(value.get("nodes"), list) and isinstance(value.get("edges"), list)


def _stable_component(value: JsonValue) -> str:
    if isinstance(value, str):
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _mapping_value(value: JsonValue | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: JsonValue | None) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
