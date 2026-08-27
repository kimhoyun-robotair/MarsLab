"""Actual Isaac/Kit and MarsLab assembly validation boundary."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from marslab_scene.errors import SceneBuildError
from marslab_scene.isaac_environment import PxrRuntimeHandle, ensure_pxr_runtime

if TYPE_CHECKING:
    from marslab.config.schema.root import MarsLabConfig
    from marslab.runtime.assembly import StageHandle
    from marslab.runtime.atmosphere_boot import AtmosphereInit


@dataclass(frozen=True, slots=True)
class IsaacRuntimeReport:
    status: Literal["PASS", "FAIL"]
    input_tier: Literal["synthetic", "canonical", "paper"]
    scene_sha256: str
    base_config_sha256: str
    temporary_config_sha256: str
    python_version: str
    isaac_version: str
    kit_version: str
    simulation_app_started: bool
    world_initialized: bool
    marslab_assembly_invoked: bool
    runtime_updates_completed: int
    terrain_mesh_paths: tuple[str, ...]
    unresolved_dependencies: tuple[str, ...]
    exit_code: int
    error_type: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class _RuntimeExecution:
    app: PxrRuntimeHandle | None
    app_started: bool
    world_initialized: bool
    assembly_invoked: bool
    updates: int
    terrain_mesh_paths: tuple[str, ...]
    isaac_version: str
    kit_version: str
    error_type: str | None
    error_message: str | None
    unresolved_dependencies: tuple[str, ...]


def run_isaac_runtime_smoke(
    scene_path: Path | str,
    base_runtime_config: Path | str,
    *,
    input_tier: Literal["synthetic", "canonical", "paper"] = "synthetic",
    report_path: Path | str | None = None,
    emit_console: bool = False,
) -> IsaacRuntimeReport:
    """Start Isaac/Kit and invoke MarsLab assembly against a temporary config copy."""
    scene = Path(scene_path).expanduser().resolve()
    base_config = Path(base_runtime_config).expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="marslab-runtime-smoke-") as raw_directory:
        temporary_root = Path(raw_directory)
        temporary_config = _prepare_runtime_config(temporary_root, base_config, scene)
        temporary_config_sha256 = _sha256(temporary_config)
        config = import_module("marslab.config").load_config(temporary_config)
        execution = _execute_runtime(config)
    passed = (
        execution.error_type is None
        and execution.app_started
        and execution.world_initialized
        and execution.assembly_invoked
        and execution.updates >= 1
        and bool(execution.terrain_mesh_paths)
        and not execution.unresolved_dependencies
    )
    report = IsaacRuntimeReport(
        status="PASS" if passed else "FAIL",
        input_tier=input_tier,
        scene_sha256=_sha256(scene),
        base_config_sha256=_sha256(base_config),
        temporary_config_sha256=temporary_config_sha256,
        python_version=sys.version.split()[0],
        isaac_version=execution.isaac_version,
        kit_version=execution.kit_version,
        simulation_app_started=execution.app_started,
        world_initialized=execution.world_initialized,
        marslab_assembly_invoked=execution.assembly_invoked,
        runtime_updates_completed=execution.updates,
        terrain_mesh_paths=execution.terrain_mesh_paths,
        unresolved_dependencies=execution.unresolved_dependencies,
        exit_code=0 if passed else 1,
        error_type=execution.error_type,
        error_message=execution.error_message,
    )
    if report_path is not None:
        write_isaac_runtime_report(report, report_path)
    if emit_console:
        _ = sys.stdout.write(json.dumps(asdict(report), sort_keys=True) + "\n")
        _ = sys.stdout.flush()
    if execution.app is not None:
        if report.exit_code != 0:
            os._exit(report.exit_code)
        execution.app.close()
    return report


def write_isaac_runtime_report(report: IsaacRuntimeReport, path: Path | str) -> None:
    """Persist a stable runtime report for the exact process observation."""
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    _ = destination.write_text(
        json.dumps(asdict(report), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _prepare_runtime_config(root: Path, base_config: Path, scene: Path) -> Path:
    config_root = root / "configs"
    config_root.mkdir()
    assets = root / "assets"
    assets.symlink_to(base_config.parent.parent / "assets", target_is_directory=True)
    destination = config_root / base_config.name
    _ = shutil.copy2(base_config, destination)
    lines = destination.read_text(encoding="utf-8").splitlines(keepends=True)
    matching = [index for index, line in enumerate(lines) if line.startswith("  usdz_path:")]
    if len(matching) != 1:
        raise SceneBuildError("base runtime config must contain exactly one scene.usdz_path")
    lines[matching[0]] = f"  usdz_path: {scene.as_posix()}\n"
    _ = destination.write_text("".join(lines), encoding="utf-8")
    return destination


def _execute_runtime(config: MarsLabConfig) -> _RuntimeExecution:
    app = None
    app_started = False
    world_initialized = False
    assembly_invoked = False
    updates = 0
    terrain_mesh_paths: tuple[str, ...] = ()
    isaac_version = "unknown"
    kit_version = "unknown"
    error_type: str | None = None
    error_message: str | None = None
    unresolved_dependencies: tuple[str, ...] = ()
    try:
        atmosphere = _prepare_atmosphere(config)
        app = _require_isaac_runtime(headless=config.runtime.headless)
        app_started = True
        if config.runtime.ros2_enabled:
            sim_boot = import_module("marslab.sim.boot")
            import_module("isaacsim.core.utils.extensions").enable_extension(
                sim_boot.DEFAULT_ROS2_BRIDGE_EXTENSION
            )
        app.update()
        package_report = import_module(
            "marslab_scene.usd.runtime_package"
        ).validate_runtime_package(config.scene.usdz_path)
        unresolved_dependencies = package_report.unresolved_dependencies
        isaac_version = str(import_module("isaacsim.core.version").get_version()[0])
        kit_version = str(import_module("omni.kit.app").get_app().get_app_version())
        world, stage = import_module("marslab.sim.world_setup").create_world(
            physics_dt=atmosphere.physics_dt,
            gravity=config.mars_env.gravity,
        )
        world_initialized = True
        _ = import_module("marslab.runtime.assembly").assemble_pre_reset(
            world=world,
            stage=stage,
            scene_path=str(config.scene.usdz_path),
            rover=config.rover,
            render_config=config.rendering,
            atmosphere_init=atmosphere,
            atmosphere_enabled=config.runtime.atmosphere_enabled,
            ros2_enabled=config.runtime.ros2_enabled,
        )
        assembly_invoked = True
        terrain_mesh_paths = _require_terrain_meshes(stage)
        app.update()
        updates = 1
    except Exception as error:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK
        error_type = type(error).__name__
        error_message = str(error)
    return _RuntimeExecution(
        app=app,
        app_started=app_started,
        world_initialized=world_initialized,
        assembly_invoked=assembly_invoked,
        updates=updates,
        terrain_mesh_paths=terrain_mesh_paths,
        isaac_version=isaac_version,
        kit_version=kit_version,
        error_type=error_type,
        error_message=error_message,
        unresolved_dependencies=unresolved_dependencies,
    )


def _require_isaac_runtime(*, headless: bool) -> PxrRuntimeHandle:
    app = ensure_pxr_runtime(headless=headless)
    if app is None:
        raise SceneBuildError("actual Isaac runtime was not activated")
    return app


def _require_terrain_meshes(stage: StageHandle) -> tuple[str, ...]:
    pxr = import_module("pxr")
    terrain_root = stage.GetPrimAtPath("/World/Terrain")
    mesh_paths = tuple(
        prim.GetPath().pathString
        for prim in pxr.Usd.PrimRange(terrain_root)
        if prim.IsA(pxr.UsdGeom.Mesh)
    )
    if not mesh_paths:
        raise SceneBuildError("MarsLab assembly found no mesh under /World/Terrain")
    return mesh_paths


def _prepare_atmosphere(config: MarsLabConfig) -> AtmosphereInit:
    mars = config.mars_env
    sun_position = import_module("marslab.environment.sun_position").compute_sun_position(
        mars.sun_azimuth_deg,
        mars.sun_elevation_deg,
    )
    tau = mars.dust_optical_depth
    return import_module("marslab.runtime.atmosphere_boot").AtmosphereInit(
        tau=tau,
        solar_constant=mars.solar_constant,
        sun_azimuth_deg=mars.sun_azimuth_deg,
        sun_elevation_deg=mars.sun_elevation_deg,
        sol_duration_seconds=float(mars.sol_duration_seconds),
        gravity=float(mars.gravity),
        physics_dt=mars.physics_dt,
        direct_intensity=import_module(
            "marslab.environment.light_intensity"
        ).compute_direct_intensity(mars.solar_constant, tau, sun_position.zenith_angle_rad),
        diffuse_fraction=import_module(
            "marslab.environment.diffuse_fraction"
        ).compute_diffuse_fraction_1d_approx(tau),
        sky_params=import_module("marslab.environment.sky_dome").compute_sky_dome_params(
            tau,
            str(config.rendering.sky_dome_hdri_dir),
            config.rendering.sky_dome,
        ),
        sun_pos=sun_position,
        hdri_dir=str(config.rendering.sky_dome_hdri_dir),
        sky_dome_config=config.rendering.sky_dome,
        dynamic=mars.dynamic_atmosphere,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
