"""Loss-aware conversion of YueShu result values to JSON."""

from __future__ import annotations

import base64
import json
import math
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import fields, is_dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Protocol, TypeAlias, TypeGuard, cast

from pydantic import BaseModel

from nebula_mcp.errors import NebulaMCPError

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class EmbeddingVectorLike(Protocol):
    dimension: int
    values: Sequence[object]


class DurationLike(Protocol):
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    microsecond: int


def _typed_value(type_name: str, value: JsonValue) -> dict[str, JsonValue]:
    return {"$type": type_name, "value": value}


def _sort_key(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _is_duration(value: object) -> TypeGuard[DurationLike]:
    return type(value).__name__.lower().endswith("duration") and all(
        hasattr(value, name)
        for name in ("year", "month", "day", "hour", "minute", "second", "microsecond")
    )


def _is_embedding_vector(value: object) -> TypeGuard[EmbeddingVectorLike]:
    return hasattr(value, "dimension") and hasattr(value, "values")


def to_json_value(value: object) -> JsonValue:
    """Convert a value without silently discarding its database type."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        if math.isnan(value):
            return _typed_value("float", "NaN")
        return _typed_value("float", "Infinity" if value > 0 else "-Infinity")
    if isinstance(value, datetime):
        return _typed_value("datetime", value.isoformat())
    if isinstance(value, date):
        return _typed_value("date", value.isoformat())
    if isinstance(value, time):
        return _typed_value("time", value.isoformat())
    if isinstance(value, bytes):
        return {
            "$type": "bytes",
            "encoding": "base64",
            "value": base64.b64encode(value).decode("ascii"),
        }
    if isinstance(value, Decimal):
        return _typed_value("decimal", str(value))
    if isinstance(value, BaseModel):
        return to_json_value(value.model_dump(mode="python"))
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_json_value(getattr(value, field.name))
            for field in fields(value)
        }
    if _is_embedding_vector(value):
        converted_values = to_json_value(value.values)
        if not isinstance(converted_values, list):
            raise NebulaMCPError(
                category="serialization_error",
                message="Embedding vector values are not a sequence",
            )
        return {
            "$type": "embedding_vector",
            "dimension": value.dimension,
            "values": converted_values,
        }
    if _is_duration(value):
        component_names = ("year", "month", "day", "hour", "minute", "second", "microsecond")
        components: dict[str, JsonValue] = {
            name: int(cast(int, getattr(value, name))) for name in component_names
        }
        return {
            "$type": "duration",
            "value": str(value),
            "components": components,
        }
    if isinstance(value, Mapping):
        return {str(key): to_json_value(item) for key, item in value.items()}
    if isinstance(value, AbstractSet) and not isinstance(value, (str, bytes)):
        converted = [to_json_value(item) for item in value]
        converted.sort(key=_sort_key)
        return {"$type": "set", "values": converted}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [to_json_value(item) for item in value]
    raise NebulaMCPError(
        category="serialization_error",
        message=f"Unsupported result value type: {type(value).__name__}",
        suggestion="Return a YueShu primitive or a supported scalar/container value",
    )
