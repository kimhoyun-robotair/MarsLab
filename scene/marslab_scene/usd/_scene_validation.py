"""Final scene semantic validation independent of USDA byte serialization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pxr import Usd, UsdGeom, UsdUtils

from marslab_scene.errors import ContractValueError

_LAYER_CHILDREN: Final = ("RockLib", "Rocks", "Habitat")


@dataclass(frozen=True, slots=True)
class SceneValidationContract:
    terrain_sublayer: str
    rock_count: int | None
    habitat_enabled: bool


@dataclass(frozen=True, slots=True)
class SceneSemanticReport:
    default_prim: str
    up_axis: str
    meters_per_unit: float
    terrain_sublayers: tuple[str, ...]
    world_children: tuple[str, ...]
    rock_count: int
    habitat_count: int
    unresolved_dependencies: tuple[str, ...]

    def as_mapping(self) -> dict[str, str | float | int | list[str]]:
        return {
            "default_prim": self.default_prim,
            "up_axis": self.up_axis,
            "meters_per_unit": self.meters_per_unit,
            "terrain_sublayers": list(self.terrain_sublayers),
            "world_children": list(self.world_children),
            "rock_count": self.rock_count,
            "habitat_count": self.habitat_count,
            "unresolved_dependencies": list(self.unresolved_dependencies),
        }


def validate_scene_stage(
    stage_path: Path,
    contract: SceneValidationContract,
) -> SceneSemanticReport:
    """Validate final hierarchy, conventions, arrays, and dependency closure."""
    stage = Usd.Stage.Open(str(stage_path))
    if not stage:
        detail = f"USD stage cannot be opened: {stage_path.name}"
        raise ContractValueError(detail)
    default_prim = stage.GetDefaultPrim().GetPath().pathString
    up_axis = str(UsdGeom.GetStageUpAxis(stage))
    meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(stage))
    if (default_prim, up_axis, meters_per_unit) != ("/World", "Z", 1.0):
        raise ContractValueError("final stage world conventions are invalid")
    sublayers = tuple(stage.GetRootLayer().subLayerPaths)
    if sublayers != (contract.terrain_sublayer,):
        raise ContractValueError("terrain must be composed as exactly one relative sublayer")
    children = tuple(child.GetName() for child in stage.GetPrimAtPath("/World").GetChildren())
    terrain_children = _terrain_children(stage_path.parent / contract.terrain_sublayer)
    layer_children = tuple(
        name
        for name in _LAYER_CHILDREN
        if (name in {"RockLib", "Rocks"} and contract.rock_count is not None)
        or (name == "Habitat" and contract.habitat_enabled)
    )
    expected_children = terrain_children + layer_children
    if children != expected_children:
        raise ContractValueError("final scene hierarchy does not match enabled layers")
    terrain = stage.GetPrimAtPath("/World/MarsTerrain")
    if not terrain or not any(prim.IsA(UsdGeom.Mesh) for prim in Usd.PrimRange(terrain)):
        raise ContractValueError("terrain subtree has no composed mesh")
    rock_count = _validate_scene_rocks(stage, contract.rock_count)
    habitat_count = int(bool(stage.GetPrimAtPath("/World/Habitat")))
    if habitat_count != int(contract.habitat_enabled):
        raise ContractValueError("habitat prim does not match layer contract")
    _, _, unresolved = UsdUtils.ComputeAllDependencies(str(stage_path))
    if unresolved:
        detail = f"USD stage has unresolved dependencies: {sorted(unresolved)}"
        raise ContractValueError(detail)
    return SceneSemanticReport(
        default_prim=default_prim,
        up_axis=up_axis,
        meters_per_unit=meters_per_unit,
        terrain_sublayers=sublayers,
        world_children=children,
        rock_count=rock_count,
        habitat_count=habitat_count,
        unresolved_dependencies=tuple(sorted(str(item) for item in unresolved)),
    )


def _terrain_children(stage_path: Path) -> tuple[str, ...]:
    stage = Usd.Stage.Open(str(stage_path))
    if not stage:
        raise ContractValueError("composed terrain sublayer cannot be opened")
    world = stage.GetPrimAtPath("/World")
    if not world:
        raise ContractValueError("terrain sublayer must provide MarsTerrain exactly once")
    children = tuple(child.GetName() for child in world.GetChildren())
    if children.count("MarsTerrain") != 1:
        raise ContractValueError("terrain sublayer must provide MarsTerrain exactly once")
    if any(name in _LAYER_CHILDREN for name in children):
        raise ContractValueError("terrain sublayer conflicts with final layer hierarchy")
    return children


def _validate_scene_rocks(stage: Usd.Stage, expected_count: int | None) -> int:
    instancer = UsdGeom.PointInstancer.Get(stage, "/World/Rocks/Instancer")
    if expected_count is None:
        if instancer:
            raise ContractValueError("rock instancer exists without a rock layer")
        return 0
    if not instancer:
        raise ContractValueError("rock layer has no PointInstancer")
    positions = instancer.GetPositionsAttr().Get()
    indices = instancer.GetProtoIndicesAttr().Get()
    scales = instancer.GetScalesAttr().Get()
    orientations = instancer.GetOrientationsAttr().Get()
    if any(len(values) != expected_count for values in (positions, indices, scales, orientations)):
        raise ContractValueError("PointInstancer array lengths do not match rock layer")
    targets = instancer.GetPrototypesRel().GetTargets()
    if len(targets) == 0:
        raise ContractValueError("PointInstancer has no prototype targets")
    if any(index < 0 or index >= len(targets) for index in indices):
        raise ContractValueError("PointInstancer prototype index is out of range")
    return expected_count
