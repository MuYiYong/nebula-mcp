"""Bounded extraction of the SDK's execution plan, independent of row iteration."""

from __future__ import annotations

import json
from typing import Any

from nebula_mcp.models import ProfileOutput

_FIELDS = (
    "id", "name", "details", "time_ms", "rows", "memory_kib", "blocked_ms",
    "queued_ms", "consume_ms", "produce_ms", "finish_ms", "batches", "concurrency",
    "other_stats_json",
)


def extract_profile(result: Any, *, max_bytes: int) -> ProfileOutput:
    root = getattr(result, "plan_desc", None)
    output = ProfileOutput(latency_us=result.latency_us)
    if root is None or not root.name:
        return output
    stack = [(root, 0)]
    used = 0
    while stack:
        node, depth = stack.pop()
        row = {field: getattr(node, field, None) for field in _FIELDS}
        row["depth"] = depth
        used += len(json.dumps(row, ensure_ascii=False).encode("utf-8"))
        if used > max_bytes or len(output.operators) >= 1000:
            return output.model_copy(update={"truncated": True})
        output.operators.append(row)
        stack.extend((child, depth + 1) for child in reversed(node.children))
    return output
