"""Standalone semantic inspection of final runtime packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pxr import Usd, UsdGeom, UsdUtils

from marslab_scene.errors import ContractValueError


@dataclass(frozen=True, slots=True)
class RuntimePackageReport:
    default_prim: str
    up_axis: str
    meters_per_unit: float
    terrain_mesh_paths: tuple[str, ...]
    unresolved_dependencies: tuple[str, ...]


def validate_runtime_package(package_path: Path | str) -> RuntimePackageReport:
    """Open a final package and require MarsLab terrain and dependency contracts."""
    path = Path(package_path).expanduser().resolve()
    stage = Usd.Stage.Open(str(path))
    if not stage:
        detail = f"runtime package cannot be opened: {path.name}"
        raise ContractValueError(detail)
    default_prim = stage.GetDefaultPrim().GetPath().pathString
    up_axis = str(UsdGeom.GetStageUpAxis(stage))
    meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(stage))
    if (default_prim, up_axis, meters_per_unit) != ("/World", "Z", 1.0):
        raise ContractValueError("runtime package world conventions are invalid")
    terrain = stage.GetPrimAtPath("/World/MarsTerrain")
    terrain_mesh_paths = tuple(
        prim.GetPath().pathString for prim in Usd.PrimRange(terrain) if prim.IsA(UsdGeom.Mesh)
    )
    if not terrain_mesh_paths:
        raise ContractValueError("runtime package has no terrain mesh")
    _, _, unresolved = UsdUtils.ComputeAllDependencies(str(path))
    unresolved_dependencies = tuple(sorted(str(item) for item in unresolved))
    if unresolved_dependencies:
        detail = f"runtime package has unresolved dependencies: {list(unresolved_dependencies)}"
        raise ContractValueError(detail)
    return RuntimePackageReport(
        default_prim=default_prim,
        up_axis=up_axis,
        meters_per_unit=meters_per_unit,
        terrain_mesh_paths=terrain_mesh_paths,
        unresolved_dependencies=unresolved_dependencies,
    )
