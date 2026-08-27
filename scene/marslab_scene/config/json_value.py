"""Shared YAML-to-JSON value parser initialized before optional USD runtime loading."""

from typing import Final

from pydantic import JsonValue, TypeAdapter

JSON_VALUE_ADAPTER: Final[TypeAdapter[JsonValue]] = TypeAdapter(JsonValue)
