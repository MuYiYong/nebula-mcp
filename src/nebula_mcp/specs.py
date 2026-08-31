"""Portable graph and chart artifact specifications."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from nebula_mcp.models import (
    Analysis,
    ChartSpec,
    CytoscapeElement,
    CytoscapeElements,
    GraphSpec,
    ParsedResult,
)
from nebula_mcp.serialization import JsonValue

_VEGA_LITE_V5_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"


def build_cytoscape_graph(parsed: ParsedResult) -> GraphSpec:
    """Build a client-renderable Cytoscape elements specification."""

    nodes = [
        CytoscapeElement(
            data={
                "id": node.key,
                "raw_id": node.raw_id,
                "graph": node.graph,
                "type": node.type_name,
                "labels": node.labels,
                "properties": node.properties,
                "placeholder": node.placeholder,
            }
        )
        for node in parsed.graph.nodes
    ]
    edges = [
        CytoscapeElement(
            data={
                "id": edge.key,
                "source": f"{edge.graph or '_'}:{_id_component(edge.src_id)}",
                "target": f"{edge.graph or '_'}:{_id_component(edge.dst_id)}",
                "graph": edge.graph,
                "type": edge.edge_type,
                "rank": edge.rank,
                "labels": edge.labels,
                "properties": edge.properties,
                "direction": edge.direction,
            }
        )
        for edge in parsed.graph.edges
    ]
    return GraphSpec(
        graph=parsed.graph.graph,
        elements=CytoscapeElements(nodes=nodes, edges=edges),
        paths=[path.model_dump(mode="json") for path in parsed.graph.paths],
        truncated=parsed.truncation.truncated,
    )


def _id_component(value: object) -> str:
    """Mirror the parser's stable ID representation."""

    if isinstance(value, str):
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_vega_lite_specs(
    rows: Sequence[Mapping[str, JsonValue]],
    analysis: Analysis,
    max_charts: int = 3,
) -> list[ChartSpec]:
    """Choose a bounded, deterministic set of Vega-Lite v5 specifications."""

    if max_charts <= 0 or not rows:
        return []
    values = [dict(row) for row in rows]
    temporal = [name for name, column in analysis.columns.items() if column.kind == "temporal"]
    categorical = [
        name for name, column in analysis.columns.items() if column.kind == "categorical"
    ]
    numeric = [name for name, column in analysis.columns.items() if column.kind == "numeric"]
    specs: list[ChartSpec] = []

    for temporal_name in temporal:
        for numeric_name in numeric:
            _append_chart(
                specs,
                max_charts,
                description=f"{numeric_name} over {temporal_name} in returned rows",
                values=values,
                mark="line",
                encoding={
                    "x": {"field": temporal_name, "type": "temporal"},
                    "y": {"field": numeric_name, "type": "quantitative"},
                },
            )

    for category_name in categorical:
        for numeric_name in numeric:
            _append_chart(
                specs,
                max_charts,
                description=f"Mean {numeric_name} by {category_name} in returned rows",
                values=values,
                mark="bar",
                encoding={
                    "x": {"field": category_name, "type": "nominal", "sort": "-y"},
                    "y": {
                        "field": numeric_name,
                        "type": "quantitative",
                        "aggregate": "mean",
                    },
                },
            )

    for x_index, x_name in enumerate(numeric):
        for y_name in numeric[x_index + 1 :]:
            _append_chart(
                specs,
                max_charts,
                description=f"{y_name} versus {x_name} in returned rows",
                values=values,
                mark="point",
                encoding={
                    "x": {"field": x_name, "type": "quantitative"},
                    "y": {"field": y_name, "type": "quantitative"},
                },
            )

    for numeric_name in numeric:
        _append_chart(
            specs,
            max_charts,
            description=f"Distribution of {numeric_name} in returned rows",
            values=values,
            mark="bar",
            encoding={
                "x": {"field": numeric_name, "type": "quantitative", "bin": True},
                "y": {"aggregate": "count", "type": "quantitative"},
            },
        )
    return specs


def _append_chart(
    specs: list[ChartSpec],
    max_charts: int,
    *,
    description: str,
    values: list[dict[str, JsonValue]],
    mark: str,
    encoding: dict[str, Any],
) -> None:
    if len(specs) >= max_charts:
        return
    specs.append(
        ChartSpec(
            description=description,
            spec={
                "$schema": _VEGA_LITE_V5_SCHEMA,
                "description": description,
                "data": {"values": values},
                "mark": mark,
                "encoding": encoding,
            },
        )
    )
