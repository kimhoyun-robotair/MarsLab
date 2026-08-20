"""Assemble the pre-reset Isaac scene from typed runtime inputs.
The phase creates world, rover, and mandatory sensors once.
Runtime imports remain deferred until the simulator boundary."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import import_module
from typing import Final, Protocol

import numpy as np

from marslab.config.schema.rover import RoverConfig
from marslab.config.schema.scenario import RenderingConfig
from marslab.robots.rover import SpawnedRover
from marslab.ros2_bridge.sensor_graph import SensorGraphHandle
from marslab.runtime.atmosphere_boot import AtmosphereInit
from marslab.sensors.sensor_spawner import SensorHandles

SpawnPosition = tuple[float, float, float]
_TERRAIN_PRIM_PATH: Final = "/World/Terrain"
_LEGACY_CLI_Z_OFFSET: Final = 0.0
_FALLBACK_LIGHT_PATH: Final = "/World/FallbackSun"
_LOG = logging.getLogger(__name__)


class WorldHandle(Protocol):
    def reset(self) -> None: ...


class PrimHandle(Protocol):
    def GetName(self) -> str: ...

    def GetPath(self) -> str: ...

    def IsA(self, schema: type) -> bool: ...

    def IsValid(self) -> bool: ...

    def SetActive(self, active: bool) -> None: ...


class StageHandle(Protocol):
    def GetPrimAtPath(self, path: str) -> PrimHandle: ...

    def Traverse(self) -> Iterable[PrimHandle]: ...


class ArticulationHandle(Protocol):
    def initialize(self) -> None: ...


@dataclass(frozen=True, slots=True)
class PreResetAssembly:
    spawn_xyz: SpawnPosition
    spawn_rpy: SpawnPosition
    rover: SpawnedRover
    sensors: SensorHandles
    sensor_graph: SensorGraphHandle | None
    articulation: ArticulationHandle


def _find_terrain_meshes(
    stage: StageHandle,
    terrain_prim_path: str,
) -> tuple[PrimHandle | None, PrimHandle | None]:
    pxr = import_module("pxr")
    Usd = pxr.Usd
    UsdGeom = pxr.UsdGeom

    terrain_root = stage.GetPrimAtPath(terrain_prim_path)
    if not terrain_root.IsValid():
        raise RuntimeError(f"Terrain prim not found at {terrain_prim_path}")

    visible = collision = None
    for prim in Usd.PrimRange(terrain_root):
        if not prim.IsA(UsdGeom.Mesh):
            continue
        vis_attr = UsdGeom.Imageable(prim).GetVisibilityAttr()
        invisible = vis_attr.IsValid() and vis_attr.Get() == UsdGeom.Tokens.invisible
        if "Collision" in prim.GetName() or invisible:
            if collision is None:
                collision = prim
        elif visible is None:
            visible = prim
    return visible, collision


def _nearest_k_median_z(
    mesh_prim: PrimHandle,
    target_x: float,
    target_y: float,
    k: int = 8,
) -> float:
    pxr = import_module("pxr")
    Usd = pxr.Usd
    UsdGeom = pxr.UsdGeom

    points = UsdGeom.Mesh(mesh_prim).GetPointsAttr().Get()
    if points is None or len(points) == 0:
        raise RuntimeError(
            f"Mesh {mesh_prim.GetPath()} has no authored points; cannot sample " "DEM elevation."
        )
    local_to_world = UsdGeom.XformCache(Usd.TimeCode.Default()).GetLocalToWorldTransform(mesh_prim)
    matrix = np.array(local_to_world, dtype=np.float64)
    pts = np.asarray(points, dtype=np.float64)
    world = pts @ matrix[:3, :3] + matrix[3, :3]
    d2 = (world[:, 0] - target_x) ** 2 + (world[:, 1] - target_y) ** 2
    k = min(k, world.shape[0])
    idx = np.argpartition(d2, k - 1)[:k]
    return float(np.median(world[idx, 2]))


def _sample_dem_surface_z_at(
    stage: StageHandle,
    terrain_prim_path: str,
    target_x: float,
    target_y: float,
) -> float:
    visible, collision = _find_terrain_meshes(stage, terrain_prim_path)
    mesh_prim = collision if collision is not None else visible
    if mesh_prim is None:
        raise RuntimeError(
            f"No UsdGeom.Mesh under {terrain_prim_path}; cannot sample DEM elevation."
        )
    return _nearest_k_median_z(mesh_prim, target_x, target_y)


def _sample_dem_elevation(
    stage: StageHandle,
    terrain_prim_path: str,
) -> SpawnPosition:
    pxr = import_module("pxr")
    Usd = pxr.Usd
    UsdGeom = pxr.UsdGeom

    visible, collision = _find_terrain_meshes(stage, terrain_prim_path)
    if visible is None:
        if collision is None:
            raise RuntimeError(
                f"No UsdGeom.Mesh under {terrain_prim_path}; cannot sample DEM elevation."
            )
        bbox_ref = mesh_prim = collision
    else:
        bbox_ref = visible
        mesh_prim = collision if collision is not None else visible
    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        includedPurposes=[UsdGeom.Tokens.default_],
    )
    bbox = bbox_cache.ComputeWorldBound(bbox_ref).ComputeAlignedRange()
    bmin, bmax = bbox.GetMin(), bbox.GetMax()
    cx = float((bmin[0] + bmax[0]) / 2.0)
    cy = float((bmin[1] + bmax[1]) / 2.0)

    surface_z = _nearest_k_median_z(mesh_prim, cx, cy)
    _LOG.info(
        "DEM center=(%.3f, %.3f) surface_z=%.3f (nearest-k median on %s mesh)",
        cx,
        cy,
        surface_z,
        "collision" if collision is not None else "visible",
    )
    return cx, cy, surface_z


def _reference_user_usda(stage: StageHandle, usda_abs: str) -> None:
    omni_kit_app = import_module("omni.kit.app")
    stage_utils = import_module("isaacsim.core.utils.stage")

    stage_utils.add_reference_to_stage(usd_path=usda_abs, prim_path=_TERRAIN_PRIM_PATH)
    app = omni_kit_app.get_app()
    while stage_utils.is_stage_loading():
        app.update()

    nested_phys = stage.GetPrimAtPath(f"{_TERRAIN_PRIM_PATH}/PhysicsScene")
    if nested_phys.IsValid():
        nested_phys.SetActive(False)
        _LOG.info("Deactivated nested PhysicsScene at %s/PhysicsScene.", _TERRAIN_PRIM_PATH)


def _add_fallback_light_if_missing(stage: StageHandle) -> bool:
    pxr = import_module("pxr")
    Sdf = pxr.Sdf
    UsdLux = pxr.UsdLux

    light_types = (
        UsdLux.DistantLight,
        UsdLux.DomeLight,
        UsdLux.SphereLight,
        UsdLux.RectLight,
        UsdLux.DiskLight,
        UsdLux.CylinderLight,
    )
    for prim in stage.Traverse():
        if any(prim.IsA(light_type) for light_type in light_types):
            _LOG.info("Stage already has a light at %s; skipping fallback.", prim.GetPath())
            return False

    light = UsdLux.DistantLight.Define(stage, Sdf.Path(_FALLBACK_LIGHT_PATH))
    light.CreateIntensityAttr(3000.0)
    light.CreateAngleAttr(0.53)
    light.CreateColorAttr((1.0, 0.85, 0.65))
    _LOG.info("Added fallback DistantLight at %s.", _FALLBACK_LIGHT_PATH)
    return True


def _resolve_spawn_position(
    *,
    stage: StageHandle,
    terrain_prim_path: str,
    rover: RoverConfig,
) -> tuple[SpawnPosition, SpawnPosition]:
    """Resolve the legacy DEM-relative rover pose before the first reset."""
    spawn = rover.spawn
    z_offset = spawn.z_offset if spawn.z_offset is not None else _LEGACY_CLI_Z_OFFSET
    dem_center_x, dem_center_y, _ = _sample_dem_elevation(stage, terrain_prim_path)

    match spawn.mode:
        case "dem_center":
            spawn_x, spawn_y = dem_center_x, dem_center_y
        case "dem_relative":
            spawn_x = dem_center_x + float(spawn.xy[0])
            spawn_y = dem_center_y + float(spawn.xy[1])
        case "absolute":
            spawn_x = float(spawn.xy[0])
            spawn_y = float(spawn.xy[1])
        case unknown:
            raise RuntimeError(
                f"Unknown spawn.mode='{unknown}' in rover YAML; expected one of "
                "dem_center | dem_relative | absolute"
            )

    surface_z = _sample_dem_surface_z_at(stage, terrain_prim_path, spawn_x, spawn_y)
    spawn_xyz = (spawn_x, spawn_y, surface_z + z_offset)
    orientation_rpy = spawn.orientation_rpy
    spawn_rpy = (
        float(orientation_rpy[0]),
        float(orientation_rpy[1]),
        float(orientation_rpy[2]),
    )
    return spawn_xyz, spawn_rpy


def assemble_pre_reset(
    *,
    world: WorldHandle,
    stage: StageHandle,
    scene_path: str,
    rover: RoverConfig,
    render_config: RenderingConfig,
    atmosphere_init: AtmosphereInit,
    atmosphere_enabled: bool,
    ros2_enabled: bool,
) -> PreResetAssembly:
    """Perform the exact scene-to-reset sequence retained from ``main.py``."""
    from marslab.rendering.atmosphere_fog import configure_atmosphere_fog  # noqa: PLC0415
    from marslab.rendering.render_settings import set_render_mode  # noqa: PLC0415
    from marslab.rendering.sky_renderer import configure_sky_dome  # noqa: PLC0415
    from marslab.rendering.sun_renderer import configure_sun_light  # noqa: PLC0415
    from marslab.robots.drive_api_setup import configure_drives  # noqa: PLC0415
    from marslab.robots.rover import spawn_rover  # noqa: PLC0415
    from marslab.ros2_bridge.sensor_graph import build_sensor_graph  # noqa: PLC0415
    from marslab.sensors.sensor_spawner import spawn_sensors  # noqa: PLC0415

    articulation_factory = import_module("isaacsim.core.prims").Articulation
    sensors_config = rover.sensors.model_dump(mode="python")
    ros2_config = rover.ros2.model_dump(mode="python")
    control_config = rover.control.model_dump(mode="python")

    _reference_user_usda(stage, scene_path)

    if atmosphere_enabled:
        set_render_mode(render_config)
        configure_sun_light(
            stage,
            atmosphere_init.sun_pos,
            atmosphere_init.direct_intensity,
            atmosphere_init.diffuse_fraction,
            render_config,
        )
        configure_sky_dome(
            stage,
            atmosphere_init.sky_params,
            atmosphere_init.diffuse_fraction,
            render_config,
        )
        configure_atmosphere_fog(stage, atmosphere_init.tau, render_config)
    else:
        _add_fallback_light_if_missing(stage)

    spawn_xyz, spawn_rpy = _resolve_spawn_position(
        stage=stage,
        terrain_prim_path=_TERRAIN_PRIM_PATH,
        rover=rover,
    )
    spawned_rover = spawn_rover(stage, rover, spawn_xyz)
    sensor_handles = spawn_sensors(
        stage,
        sensors_config,
        ros2_config,
        spawned_rover.rigid_body_path,
    )

    sensor_graph = None
    if ros2_enabled:
        camera_config = sensors_config["camera"]
        sensor_graph = build_sensor_graph(
            ros2_cfg=ros2_config,
            camera_acquisition=sensor_handles.camera_acquisition,
            lidar_3d_acquisition=sensor_handles.lidar_3d_acquisition,
            imu_acquisition=sensor_handles.imu_acquisition,
            depth_sensor_cfg=camera_config.get("depth_sensor"),
            articulation_root_prim_path=f"{spawned_rover.chassis_path}/Body_Chassis",
        )

    configure_drives(stage, spawned_rover.chassis_path, control_config)
    articulation = articulation_factory(prim_paths_expr=spawned_rover.prim_path)
    world.reset()
    return PreResetAssembly(
        spawn_xyz=spawn_xyz,
        spawn_rpy=spawn_rpy,
        rover=spawned_rover,
        sensors=sensor_handles,
        sensor_graph=sensor_graph,
        articulation=articulation,
    )


__all__ = [
    "PreResetAssembly",
    "ArticulationHandle",
    "SensorHandles",
    "SensorGraphHandle",
    "SpawnPosition",
    "SpawnedRover",
    "StageHandle",
    "WorldHandle",
    "assemble_pre_reset",
]
