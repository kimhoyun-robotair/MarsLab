from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NewType, TypeAlias

AssetPath = NewType("AssetPath", str)
JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


def _json_strings(values: tuple[str, ...] | frozenset[str]) -> list[JsonValue]:
    result: list[JsonValue] = []
    result.extend(sorted(values))
    return result


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    severity: Severity
    message: str
    path: str


@dataclass(frozen=True, slots=True)
class SceneFacts:
    default_prim: str | None
    up_axis: str
    meters_per_unit: float
    prim_count: int
    mesh_paths: tuple[str, ...]
    collision_paths: tuple[str, ...]
    physics_scene_paths: tuple[str, ...]
    layer_ids: tuple[str, ...]
    asset_ids: tuple[str, ...]
    unresolved_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoverFacts:
    default_prim: str | None
    up_axis: str
    meters_per_unit: float
    prim_names: frozenset[str]
    articulation_paths: tuple[str, ...]
    layer_ids: tuple[str, ...]
    asset_ids: tuple[str, ...]
    unresolved_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValidationReport:
    kind: str
    path: str
    facts: SceneFacts | RoverFacts | None = None
    diagnostics: tuple[Diagnostic, ...] = ()
    metadata: tuple[tuple[str, str | int | bool], ...] = ()

    @property
    def ok(self) -> bool:
        return not any(item.severity is Severity.ERROR for item in self.diagnostics)

    def to_dict(self) -> dict[str, JsonValue]:
        facts: dict[str, JsonValue] | None = None
        if isinstance(self.facts, SceneFacts):
            facts = {
                "default_prim": self.facts.default_prim,
                "up_axis": self.facts.up_axis,
                "meters_per_unit": self.facts.meters_per_unit,
                "prim_count": self.facts.prim_count,
                "mesh_paths": _json_strings(self.facts.mesh_paths),
                "collision_paths": _json_strings(self.facts.collision_paths),
                "physics_scene_paths": _json_strings(self.facts.physics_scene_paths),
                "layer_ids": _json_strings(self.facts.layer_ids),
                "asset_ids": _json_strings(self.facts.asset_ids),
                "unresolved_ids": _json_strings(self.facts.unresolved_ids),
            }
        if isinstance(self.facts, RoverFacts):
            facts = {
                "default_prim": self.facts.default_prim,
                "up_axis": self.facts.up_axis,
                "meters_per_unit": self.facts.meters_per_unit,
                "prim_names": _json_strings(self.facts.prim_names),
                "articulation_paths": _json_strings(self.facts.articulation_paths),
                "layer_ids": _json_strings(self.facts.layer_ids),
                "asset_ids": _json_strings(self.facts.asset_ids),
                "unresolved_ids": _json_strings(self.facts.unresolved_ids),
            }
        return {
            "schema_version": 1,
            "kind": self.kind,
            "path": self.path,
            "ok": self.ok,
            "facts": facts,
            "diagnostics": [
                {
                    "code": item.code,
                    "severity": str(item.severity),
                    "message": item.message,
                    "path": item.path,
                }
                for item in self.diagnostics
            ],
            "metadata": dict(self.metadata),
        }


class AssetValidationError(RuntimeError):
    def __init__(self, path: Path, diagnostics: tuple[Diagnostic, ...]) -> None:
        self.path = path
        self.diagnostics = diagnostics
        codes = ", ".join(item.code for item in diagnostics)
        super().__init__(f"asset validation failed for {path}: {codes}")


class StageOpenError(RuntimeError):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"OpenUSD could not open stage: {path}")


__all__ = [
    "AssetPath",
    "AssetValidationError",
    "Diagnostic",
    "JsonValue",
    "RoverFacts",
    "SceneFacts",
    "Severity",
    "StageOpenError",
    "ValidationReport",
]
