"""Phase 1 Stage 3 monolithic runtime: rover + scene + ROS2 in one file.

This entrypoint is a verbatim splice of the two proven Stage 1/2 runtimes:

*   Backbone: ``scripts/phase1/run_stage1.py`` (M2020 spawn, sensor rig,
    OmniGraph, ROS2 cmd_vel/odom, Ackermann main loop — validated
    through Stage 1.14 on 2026-04-17).
*   Inserted scene block: ``scripts/phase1/run_stage2.py`` L173-363
    (HiRISE/procedural/cave terrain mesh, PBR material, Golombek rock
    placement, dynamic sun + sky dome + atmosphere fog — validated
    scene-only for all five scenarios).

The monolithic file exists because the modular version
(``scripts/phase1/run_stage3.py`` + ``marslab/robots/rover.py`` +
``marslab/sensors/rover_rig.py`` + ``marslab/ros2_bridge/*``) silently
abort Isaac Sim on startup despite the module surface being
structurally identical to ``run_stage1``.  Per
``feedback_monolithic_before_modular.md``: two individually-validated
monolithic pipelines are merged into a single file first, verified
end-to-end, and only afterwards re-extracted into modules one function
at a time with smoke re-verification per extraction.

The only marslab imports permitted here are **pure Python or Isaac-Sim
modules already validated by run_stage2**:

*   ``marslab.config.scenario_loader`` — deep-merge + spawn resolution.
*   ``marslab.terrain.*`` — mesh_builder, cave_mesh_builder,
    material_applicator, rock_placer, rock_instancer.
*   ``marslab.environment.*`` — sun_position, light_intensity,
    diffuse_fraction, sky_dome.
*   ``marslab.rendering.*`` — sun_renderer, sky_renderer,
    atmosphere_fog, render_settings.
*   ``marslab.config.schema.RenderingConfig`` (pydantic model).

``marslab.robots.rover`` / ``marslab.sensors.rover_rig`` /
``marslab.ros2_bridge.*`` are **NOT imported** — those are the paths
implicated in the Stage 3 silent abort and will be re-exercised only
after monolithic smoke passes.

Usage:
    scripts/isaac_python.sh scripts/phase1/run_stage3_monolithic.py \\
        --config configs/scenarios/jezero_flat.yaml

    # Log capture — ``2>&1 | tee`` is shell redirection, NOT argparse:
    scripts/isaac_python.sh scripts/phase1/run_stage3_monolithic.py \\
        --config configs/scenarios/jezero_flat.yaml 2>&1 | tee ~/stage3.log
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Tuple

import numpy as np
import yaml  # noqa: F401  (kept for parity with run_stage1; unused directly)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# marslab.* imports require the repo root on sys.path.
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# scenario_loader is pure-Python (no Isaac Sim) — safe at module scope.
from marslab.config.scenario_loader import (  # noqa: E402
    load_scenario_config,
    resolve_spawn_pose,
)
from marslab.robots.rover_control import ackermann_command  # noqa: E402

# =============================================================================
# Pure helpers — verbatim from run_stage1.py L90-170 (offline-testable).
# =============================================================================


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the closed interval ``[low, high]``."""
    if low > high:
        raise ValueError(f"clamp bounds inverted: low={low} > high={high}")
    if value < low:
        return low
    if value > high:
        return high
    return value


def clamp_twist(v: float, w: float, v_max: float, w_max: float) -> Tuple[float, float]:
    """Clamp a 2D twist (linear, angular) to symmetric limits."""
    return clamp(v, -v_max, v_max), clamp(w, -w_max, w_max)


def rpy_to_quat(roll: float, pitch: float, yaw: float) -> Tuple[float, float, float, float]:
    """Convert roll-pitch-yaw (radians) to quaternion (w, x, y, z).

    Uses the ZYX intrinsic convention (yaw around Z, then pitch around Y,
    then roll around X) which is the standard for URDF and ROS.

    Returns:
        ``(w, x, y, z)`` tuple with scalar-first quaternion.
    """
    cr, sr = np.cos(roll / 2.0), np.sin(roll / 2.0)
    cp, sp = np.cos(pitch / 2.0), np.sin(pitch / 2.0)
    cy, sy = np.cos(yaw / 2.0), np.sin(yaw / 2.0)

    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return float(w), float(x), float(y), float(z)


def resolve_joint_indices(dof_names: List[str], requested: List[str]) -> List[int]:
    """Resolve each requested joint name to its index inside ``dof_names``.

    Args:
        dof_names: Ordered DOF names reported by an Articulation.
        requested: Joint names the caller wants indices for.

    Returns:
        List of int indices, matching the order of ``requested``.

    Raises:
        ValueError: If any requested joint name is not in ``dof_names``.
    """
    name_to_index = {name: idx for idx, name in enumerate(dof_names)}
    missing = [name for name in requested if name not in name_to_index]
    if missing:
        raise ValueError(
            f"Joint(s) not present in articulation DOF list: {missing}. "
            f"Available DOFs: {list(dof_names)}"
        )
    return [name_to_index[name] for name in requested]


# =============================================================================
# Terrain elevation loader — verbatim from run_stage2.py L67-144.
# =============================================================================


def load_terrain_elevation(
    terrain_cfg: Dict[str, Any],
) -> tuple[np.ndarray, dict, float]:
    """Load terrain elevation from config (procedural or HiRISE DEM).

    Args:
        terrain_cfg: The ``terrain`` section of the config.

    Returns:
        Tuple of (elevation, metadata, resolution).

    Raises:
        ValueError: If terrain source is unknown or misconfigured.
    """
    source = terrain_cfg.get("source", "procedural")
    resolution = float(terrain_cfg.get("terrain_resolution", 1.0))

    if source == "procedural":
        preset = terrain_cfg.get("procedural_preset", "flat")
        size = tuple(terrain_cfg.get("terrain_size", [256, 256]))
        seed = int(terrain_cfg.get("seed", 42))

        if preset == "cave":
            # Cave returns surface elevation only; 3D mesh built later
            from marslab.terrain.cave_generator import generate_cave_mesh

            cave_cfg = terrain_cfg.get("cave", {})
            # wall_albedo_range is a material param, not geometry — exclude from mesh gen
            geom_cfg = {k: v for k, v in cave_cfg.items() if k != "wall_albedo_range"}
            cave_data = generate_cave_mesh(
                domain_size=size,
                resolution=resolution,
                seed=seed,
                **geom_cfg,
            )
            elevation = cave_data["surface_elevation"]
            metadata = cave_data["metadata"]
            # Stash cave_data in terrain_cfg for scene building stage
            terrain_cfg["_cave_data"] = cave_data
        else:
            from marslab.terrain.procedural_generator import generate_terrain

            # Collect preset-specific params (e.g. canyon_depth, canyon_floor_width)
            preset_params = {k: v for k, v in terrain_cfg.items() if k.startswith("canyon_")}
            elevation, metadata = generate_terrain(
                preset,
                size,
                resolution,
                seed,
                kwargs=preset_params,
            )

    elif source == "hirise":
        from marslab.terrain.dem_loader import crop_dem, load_converted_dem

        converted_dir = terrain_cfg.get("converted_dem_dir")
        if converted_dir is None:
            raise ValueError("terrain.converted_dem_dir required for source='hirise'")

        dem_dir = os.path.join(REPO_ROOT, converted_dir)
        elevation, metadata = load_converted_dem(dem_dir)
        resolution = float(metadata.get("resolution_x", resolution))

        # Apply optional crop
        crop = terrain_cfg.get("dem_crop")
        if crop is not None:
            elevation, metadata = crop_dem(
                elevation,
                metadata,
                row=int(crop["row"]),
                col=int(crop["col"]),
                height=int(crop["height"]),
                width=int(crop["width"]),
            )
    else:
        raise ValueError(f"Unknown terrain source: '{source}'")

    return elevation, metadata, resolution


# =============================================================================
# CLI
# =============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        required=True,
        help="Path to Stage 3 scenario YAML (e.g. configs/scenarios/jezero_flat.yaml).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Isaac Sim without the GUI. Default is GUI mode.",
    )
    parser.add_argument(
        "--no-ros2",
        action="store_true",
        help="Skip rclpy / OmniGraph ROS2 bridge (offline rover+scene diagnostic).",
    )
    args = parser.parse_args()
    # Strip whitespace — CLI paste often leaves trailing \n or ` 2>&1` debris
    # (see plan § 10.4).
    args.config = args.config.strip()
    return args


# =============================================================================
# main()
# =============================================================================


def main() -> int:
    args = parse_args()

    # -------------------------------------------------------------------------
    # § 7.1-7.5  Pure-Python prelude — no Isaac Sim imports yet.
    # -------------------------------------------------------------------------
    config_path = os.path.abspath(args.config)
    cfg = load_scenario_config(config_path)
    print(f"[run_stage3_mono] Loaded scenario: {config_path}", flush=True)

    mars_cfg = cfg["mars_env"]
    terrain_cfg = cfg["terrain"]
    rendering_cfg = cfg["rendering"]
    rover_cfg = cfg.get("rover") or {}
    if not rover_cfg:
        print(
            "[run_stage3_mono] FATAL: scenario has no 'rover' block. "
            "Stage 3 monolithic requires a rover; use run_stage2.py for scene-only.",
            file=sys.stderr,
        )
        return 2
    sensors_cfg = rover_cfg["sensors"]
    control_cfg = rover_cfg["control"]
    ros2_cfg = rover_cfg["ros2"]

    elevation, metadata, resolution = load_terrain_elevation(terrain_cfg)
    print(
        f"[run_stage3_mono] Terrain: {elevation.shape} @ {resolution} m/px, "
        f"z=[{elevation.min():.1f}, {elevation.max():.1f}] m",
        flush=True,
    )

    # --- Compute atmosphere parameters (run_stage2.py L181-201 verbatim) ----
    from marslab.environment.diffuse_fraction import compute_diffuse_fraction
    from marslab.environment.light_intensity import compute_direct_intensity
    from marslab.environment.sky_dome import compute_sky_dome_params
    from marslab.environment.sun_position import compute_sol_sun_position, compute_sun_position

    sun_pos = compute_sun_position(
        azimuth_deg=float(mars_cfg.get("sun_azimuth_deg", 180)),
        elevation_deg=float(mars_cfg.get("sun_elevation_deg", 45)),
    )
    tau = float(mars_cfg.get("dust_optical_depth", 0.3))
    solar_constant = float(mars_cfg.get("solar_constant_mean", 589))
    direct_intensity = compute_direct_intensity(solar_constant, tau, sun_pos.zenith_angle_rad)
    diffuse_frac = compute_diffuse_fraction(tau)
    hdri_dir = os.path.join(REPO_ROOT, rendering_cfg.get("sky_dome_hdri_dir", "assets/sky/hdri/"))
    sky_params = compute_sky_dome_params(tau, hdri_dir)
    print(
        f"[run_stage3_mono] Atmosphere: tau={tau}, direct={direct_intensity:.1f} W/m2, "
        f"diffuse_frac={diffuse_frac:.2f}",
        flush=True,
    )

    # --- Resolve rover spawn pose from scenario spec -----------------------
    spawn_xyz = resolve_spawn_pose(rover_cfg, elevation, metadata, resolution)
    print(
        f"[run_stage3_mono] Spawn xyz = ({spawn_xyz[0]:.3f}, "
        f"{spawn_xyz[1]:.3f}, {spawn_xyz[2]:.3f})",
        flush=True,
    )

    # --- USD existence check (run_stage1.py L201-211 verbatim) --------------
    usd_rel = rover_cfg["usd_path"]
    usd_abs = (
        usd_rel if os.path.isabs(usd_rel) else os.path.abspath(os.path.join(REPO_ROOT, usd_rel))
    )
    if not os.path.isfile(usd_abs):
        print(
            f"[run_stage3_mono] Rover USD missing: {usd_abs}. "
            f"Run scripts/phase1/convert_urdf_to_usd.py first.",
            file=sys.stderr,
        )
        return 3

    # -------------------------------------------------------------------------
    # § 7.7  Isaac Sim boot — lazy imports so pure helpers stay offline-testable.
    # -------------------------------------------------------------------------
    from isaacsim import SimulationApp  # noqa: E402

    simulation_app = SimulationApp(
        {"headless": bool(args.headless), "renderer": "RaytracedLighting"}
    )

    # All omni.* / isaacsim.* / rclpy imports must come AFTER SimulationApp().
    import omni.graph.core as og  # noqa: E402
    import omni.usd  # noqa: E402
    from isaacsim.core.api import World  # noqa: E402
    from isaacsim.core.prims import Articulation  # noqa: E402
    from isaacsim.core.utils.extensions import enable_extension  # noqa: E402
    from isaacsim.core.utils.stage import (  # noqa: E402
        add_reference_to_stage,
        is_stage_loading,
    )
    from pxr import Gf, Sdf, UsdGeom, UsdPhysics  # noqa: E402

    enable_extension("isaacsim.ros2.bridge")
    simulation_app.update()

    import rclpy  # noqa: E402
    import rclpy.parameter  # noqa: E402
    from geometry_msgs.msg import TransformStamped, Twist  # noqa: E402
    from nav_msgs.msg import Odometry  # noqa: E402
    from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster  # noqa: E402

    # -------------------------------------------------------------------------
    # § 7.8-7.10  World + Mars gravity + stage.
    # -------------------------------------------------------------------------
    physics_dt = 1.0 / 60.0
    world = World(
        stage_units_in_meters=1.0,
        physics_dt=physics_dt,
        rendering_dt=physics_dt,
    )
    # NOTE: intentionally NOT calling world.scene.add_default_ground_plane().
    # Terrain mesh (DEM/procedural/cave) replaces the default ground.

    gravity = float(mars_cfg.get("gravity", 3.72))
    physics_ctx = world.get_physics_context()
    physics_ctx.set_gravity(-gravity)
    physics_ctx.set_solver_type("TGS")
    print(f"[run_stage3_mono] Gravity: {gravity} m/s^2", flush=True)

    stage = omni.usd.get_context().get_stage()

    # 29 DOF + high-gain drives need more solver iterations than default 4/1.
    # PhysicsContext has no set_solver_*_iteration_count in Isaac Sim 5.x;
    # set via USD PhysxScene attributes instead.
    physics_scene_prim = stage.GetPrimAtPath("/physicsScene")
    if physics_scene_prim.IsValid():
        physics_scene_prim.CreateAttribute(
            "physxScene:solverPositionIterationCount", Sdf.ValueTypeNames.Int
        ).Set(16)
        physics_scene_prim.CreateAttribute(
            "physxScene:solverVelocityIterationCount", Sdf.ValueTypeNames.Int
        ).Set(4)
        print(
            "[run_stage3_mono] Solver iterations: pos=16, vel=4 on /physicsScene",
            flush=True,
        )
    else:
        print(
            "[run_stage3_mono] WARNING: /physicsScene not found; default solver iterations.",
            file=sys.stderr,
        )

    # -------------------------------------------------------------------------
    # § 7.12  Terrain + material + rocks (run_stage2.py L230-349 verbatim).
    # -------------------------------------------------------------------------
    is_cave = terrain_cfg.get("procedural_preset") == "cave"

    if is_cave:
        # Cave: 3D mesh pipeline (bypasses heightmap-to-mesh)
        from marslab.terrain.cave_mesh_builder import build_cave_scene
        from marslab.terrain.material_applicator import apply_cave_material

        cave_data = terrain_cfg["_cave_data"]
        norm_elevation = build_cave_scene(cave_data, stage)
        print(
            f"[run_stage3_mono] Cave scene built: "
            f"tube={len(cave_data['tube_mesh'].vertices)} verts, "
            f"skylights={len(cave_data['skylight_positions'])}, "
            f"breakdown={len(cave_data['breakdown_positions'])} blocks",
            flush=True,
        )

        # Cave-specific materials
        cave_cfg = terrain_cfg.get("cave", {})
        cave_albedo = tuple(cave_cfg.get("wall_albedo_range", [0.05, 0.15]))
        cave_seed = int(terrain_cfg.get("seed", 42))
        apply_cave_material(stage, "/World/Cave/Tube", cave_albedo, cave_seed)
        apply_cave_material(stage, "/World/Cave/Floor", cave_albedo, cave_seed + 1)
        for i in range(len(cave_data["skylight_meshes"])):
            apply_cave_material(
                stage,
                f"/World/Cave/Skylight_{i}",
                cave_albedo,
                cave_seed + 2 + i,
            )

        # Surface gets standard Mars terrain material
        from marslab.terrain.material_applicator import apply_terrain_material

        surface_albedo = tuple(mars_cfg.get("surface_albedo_range", [0.10, 0.40]))
        texture_dir = terrain_cfg.get("texture_dir")
        if texture_dir:
            texture_dir = os.path.join(REPO_ROOT, texture_dir)
        apply_terrain_material(
            stage,
            "/World/Cave/Surface",
            albedo_range=surface_albedo,
            seed=cave_seed,
            texture_dir=texture_dir,
        )
        print("[run_stage3_mono] Cave materials applied.", flush=True)
        # Cave lighting: sun/sky/fog stay on (same as other scenarios).
        # Tube shell + surface cap physically block sunlight; skylight
        # holes let natural light into the tube interior.

    else:
        # Standard heightmap pipeline (Scenario 1-4)
        from marslab.terrain.mesh_builder import build_terrain_mesh

        uv_scale = float(terrain_cfg.get("uv_scale", 1.0))
        terrain_prim_path = "/World/Terrain"
        norm_elevation = build_terrain_mesh(
            elevation,
            resolution,
            stage,
            terrain_prim_path,
            uv_scale,
        )
        print(
            f"[run_stage3_mono] Terrain mesh: {terrain_prim_path}, "
            f"normalized z=[{norm_elevation.min():.2f}, {norm_elevation.max():.2f}]",
            flush=True,
        )

        # Apply terrain material (PBR)
        from marslab.terrain.material_applicator import apply_terrain_material

        albedo_range = tuple(mars_cfg.get("surface_albedo_range", [0.10, 0.40]))
        texture_dir = terrain_cfg.get("texture_dir")
        if texture_dir:
            texture_dir = os.path.join(REPO_ROOT, texture_dir)
        apply_terrain_material(
            stage,
            terrain_prim_path,
            albedo_range=albedo_range,
            seed=int(terrain_cfg.get("seed", 42)),
            texture_dir=texture_dir,
        )
        print("[run_stage3_mono] Terrain material applied.", flush=True)

    # --- Rock placement (Golombek SFD) — both cave and standard -----------
    rock_k = float(terrain_cfg.get("rock_sfd_k", 0))
    if rock_k > 0:
        from marslab.terrain.rock_instancer import place_rocks_on_terrain
        from marslab.terrain.rock_placer import sample_rocks_golombek

        d_range = tuple(terrain_cfg.get("rock_diameter_range", [0.20, 3.0]))
        area_m2 = float(norm_elevation.shape[0] * resolution * norm_elevation.shape[1] * resolution)
        rocks = sample_rocks_golombek(
            area_m2=area_m2,
            k=rock_k,
            diameter_range=d_range,
            seed=int(terrain_cfg.get("seed", 42)),
        )
        rock_mesh_dir = terrain_cfg.get("rock_mesh_dir")
        if rock_mesh_dir:
            rock_mesh_dir = os.path.join(REPO_ROOT, rock_mesh_dir)
        rock_texture_dir = terrain_cfg.get("rock_texture_dir")
        if rock_texture_dir:
            rock_texture_dir = os.path.join(REPO_ROOT, rock_texture_dir)
        place_rocks_on_terrain(
            stage=stage,
            rocks=rocks,
            elevation=norm_elevation,
            resolution=resolution,
            seed=int(terrain_cfg.get("seed", 42)),
            rock_color=tuple(terrain_cfg.get("rock_color", [0.42, 0.28, 0.20])),
            rock_roughness=float(terrain_cfg.get("rock_roughness", 0.92)),
            rock_mesh_dir=rock_mesh_dir,
            rock_texture_dir=rock_texture_dir,
        )
        print(f"[run_stage3_mono] Placed {len(rocks)} rocks (k={rock_k}).", flush=True)
    else:
        print("[run_stage3_mono] Rock placement skipped (rock_sfd_k=0).", flush=True)

    # -------------------------------------------------------------------------
    # § 7.13  Atmosphere renderers (run_stage2.py L351-363 verbatim).
    # -------------------------------------------------------------------------
    from marslab.config.schema import RenderingConfig
    from marslab.rendering.atmosphere_fog import configure_atmosphere_fog
    from marslab.rendering.render_settings import set_render_mode
    from marslab.rendering.sky_renderer import configure_sky_dome, update_sky_dome
    from marslab.rendering.sun_renderer import configure_sun_light, update_sun_light

    render_config = RenderingConfig(**rendering_cfg)
    set_render_mode(render_config)
    configure_sun_light(stage, sun_pos, direct_intensity, diffuse_frac, render_config)
    configure_sky_dome(stage, sky_params, diffuse_frac, render_config)
    configure_atmosphere_fog(stage, tau, render_config)
    print("[run_stage3_mono] Atmosphere configured (sun + sky + fog).", flush=True)

    # --- Dynamic atmosphere setup (run_stage2 L365-408 verbatim) -----------
    dyn_cfg = mars_cfg.get("dynamic_atmosphere", {})
    dynamic_enabled = bool(dyn_cfg.get("enabled", False))

    sol_duration = float(mars_cfg.get("sol_duration_seconds", 88642))
    update_interval = 10  # default

    if dynamic_enabled:
        time_scale = float(dyn_cfg.get("time_scale", 200.0))
        update_interval = int(dyn_cfg.get("update_interval_frames", 10))

        sun_sweep_cfg = dyn_cfg.get("sun_sweep", {})
        sweep_start_az = float(sun_sweep_cfg.get("start_azimuth_deg", 90.0))
        sweep_end_az = float(sun_sweep_cfg.get("end_azimuth_deg", 270.0))
        sweep_max_el = float(sun_sweep_cfg.get("max_elevation_deg", 60.0))

        print(
            f"[run_stage3_mono] Dynamic atmosphere ON: time_scale={time_scale}x, "
            f"update_interval={update_interval}",
            flush=True,
        )
    else:
        time_scale = 200.0
        sweep_start_az = 90.0
        sweep_end_az = 270.0
        sweep_max_el = 60.0
        print("[run_stage3_mono] Dynamic atmosphere OFF (static).", flush=True)

    atmosphere_state: Dict[str, Any] = {
        "tau": tau,
        "sun_mode": "auto" if dynamic_enabled else "manual",
        "sun_azimuth_deg": float(mars_cfg.get("sun_azimuth_deg", 180)),
        "sun_elevation_deg": float(mars_cfg.get("sun_elevation_deg", 45)),
        "time_of_sol": 0.0,
        "direct_intensity": direct_intensity,
        "diffuse_fraction": diffuse_frac,
    }

    # --- Interactive atmosphere panel (GUI only, run_stage2 L410-422 parity) ---
    atmo_panel = None
    if not args.headless:
        try:
            from marslab.gui.atmosphere_panel import AtmospherePanel

            atmo_panel = AtmospherePanel(atmosphere_state)
            print("[run_stage3_mono] Atmosphere control panel created.", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[run_stage3_mono] GUI panel unavailable ({exc}), using YAML config.",
                flush=True,
            )

    # -------------------------------------------------------------------------
    # § 7.14  Rover USD reference + spawn pose (run_stage1.py L253-309 adapted).
    # Only substantive changes vs. run_stage1: spawn_pos comes from
    # resolve_spawn_pose (DEM-aware), spawn_rpy from rover_cfg["spawn"].
    # -------------------------------------------------------------------------
    prim_path = rover_cfg["prim_path"]

    add_reference_to_stage(usd_path=usd_abs, prim_path=prim_path)
    # Spin the stage until the referenced layer is fully loaded.
    while is_stage_loading():
        simulation_app.update()

    chassis_path = f"{prim_path}/Body_Chassis"
    chassis_prim = stage.GetPrimAtPath(chassis_path)
    if not chassis_prim.IsValid():
        print(
            f"[run_stage3_mono] Expected chassis prim missing: {chassis_path}. "
            f"Inspect converter output.",
            file=sys.stderr,
        )
        simulation_app.close()
        return 3

    # Lift the articulation root to the resolved spawn point.
    rover_prim = stage.GetPrimAtPath(prim_path)
    xform = UsdGeom.Xformable(rover_prim)
    xform.ClearXformOpOrder()
    translate_op = xform.AddTranslateOp()
    translate_op.Set(Gf.Vec3d(float(spawn_xyz[0]), float(spawn_xyz[1]), float(spawn_xyz[2])))

    # Apply spawn orientation (RPY from config → quaternion).
    # Prefer rover_cfg["spawn"]["orientation_rpy"] (Stage 3 spec);
    # fall back to rover_cfg["spawn_orientation_rpy"] (Stage 1 legacy).
    spawn_block = rover_cfg.get("spawn") if isinstance(rover_cfg.get("spawn"), dict) else {}
    spawn_rpy = spawn_block.get(
        "orientation_rpy",
        rover_cfg.get("spawn_orientation_rpy", [0.0, 0.0, 0.0]),
    )
    qw, qx, qy, qz = rpy_to_quat(float(spawn_rpy[0]), float(spawn_rpy[1]), float(spawn_rpy[2]))
    orient_op = xform.AddOrientOp()
    orient_op.Set(Gf.Quatf(float(qw), float(qx), float(qy), float(qz)))

    # -------------------------------------------------------------------------
    # § 7.15  CoM / damping (run_stage1.py L311-351 verbatim).
    # -------------------------------------------------------------------------
    com_offset = rover_cfg.get("com_offset")
    if com_offset is not None:
        art_root_path = f"{chassis_path}/Body_Chassis"
        art_root_prim = stage.GetPrimAtPath(art_root_path)
        if art_root_prim.IsValid():
            if not art_root_prim.HasAPI(UsdPhysics.MassAPI):
                UsdPhysics.MassAPI.Apply(art_root_prim)
            mass_api = UsdPhysics.MassAPI(art_root_prim)
            mass_api.GetCenterOfMassAttr().Set(
                Gf.Vec3f(float(com_offset[0]), float(com_offset[1]), float(com_offset[2]))
            )
            print(f"[run_stage3_mono] CoM override on {art_root_path}: {com_offset}")
        else:
            print(
                f"[run_stage3_mono] WARNING: {art_root_path} not found; " f"skipping CoM override.",
                file=sys.stderr,
            )

    # Apply angular and linear damping to the articulation root body.
    art_root_path = f"{chassis_path}/Body_Chassis"
    art_root_prim = stage.GetPrimAtPath(art_root_path)
    if art_root_prim.IsValid():
        angular_damping = float(rover_cfg.get("angular_damping", 0.0))
        if angular_damping > 0.0:
            attr = art_root_prim.CreateAttribute(
                "physxRigidBody:angularDamping", Sdf.ValueTypeNames.Float
            )
            attr.Set(angular_damping)
            print(f"[run_stage3_mono] Angular damping {angular_damping} on {art_root_path}")
        linear_damping = float(rover_cfg.get("linear_damping", 0.0))
        if linear_damping > 0.0:
            attr = art_root_prim.CreateAttribute(
                "physxRigidBody:linearDamping", Sdf.ValueTypeNames.Float
            )
            attr.Set(linear_damping)
            print(f"[run_stage3_mono] Linear damping {linear_damping} on {art_root_path}")

    # -------------------------------------------------------------------------
    # § 7.16  Find the moving rigid body prim (run_stage1.py L353-370 verbatim).
    # -------------------------------------------------------------------------
    # After URDF→USD with merge_fixed_joints=False, the prim tree has:
    #   /World/Rover/Body_Chassis          ← Xform + ArticulationRootAPI (STATIC)
    #   /World/Rover/Body_Chassis/Body_Chassis  ← RigidBodyAPI (MOVES with physics)
    # ALL sensors and ComputeOdom must target the RigidBodyAPI child;
    # parenting under the outer Xform leaves them fixed in world space.
    rigid_body_path = chassis_path  # fallback
    for child in chassis_prim.GetChildren():
        if child.HasAPI(UsdPhysics.RigidBodyAPI):
            rigid_body_path = str(child.GetPath())
            print(f"[run_stage3_mono] Rigid body (moves): {rigid_body_path}")
            break
    else:
        print(
            f"[run_stage3_mono] WARNING: no RigidBodyAPI child under {chassis_path}; "
            f"sensors will be static!",
            file=sys.stderr,
        )

    # -------------------------------------------------------------------------
    # § 7.17  Sensors (run_stage1.py L372-441, lidar key remap only).
    # -------------------------------------------------------------------------
    camera_cfg = sensors_cfg["camera"]
    # Stage-3 config uses "lidar_3d"; Stage-1 phase1.yaml used "lidar".
    # Accept either so this file remains a drop-in for both schemas.
    lidar_cfg = sensors_cfg.get("lidar_3d") or sensors_cfg.get("lidar")
    if lidar_cfg is None:
        print(
            "[run_stage3_mono] FATAL: sensors block has no 'lidar_3d' or 'lidar'.",
            file=sys.stderr,
        )
        simulation_app.close()
        return 4
    imu_cfg = sensors_cfg["imu"]

    from isaacsim.sensors.camera import Camera  # noqa: E402
    from isaacsim.sensors.physics import IMUSensor  # noqa: E402
    from isaacsim.sensors.rtx import LidarRtx  # noqa: E402

    # Camera orientation strategy: ANY xformOp modification on the Camera
    # prim itself corrupts the RTX depth pipeline (vertical striping).
    # Tested and failed: constructor orientation, AddOrientOp, set_local_pose.
    # Fix: place translation + orientation on a PARENT Xform prim. The Camera
    # prim has no xformOps of its own, but inherits the correct world-space
    # transform from the parent chain.
    cam_orient_deg = camera_cfg.get("local_orientation_rpy_deg", [0.0, 0.0, 0.0])
    has_cam_orient = any(abs(v) > 0.01 for v in cam_orient_deg)

    if has_cam_orient:
        cam_qw, cam_qx, cam_qy, cam_qz = rpy_to_quat(
            np.radians(float(cam_orient_deg[0])),
            np.radians(float(cam_orient_deg[1])),
            np.radians(float(cam_orient_deg[2])),
        )
        camera_xform_path = f"{rigid_body_path}/stage1_camera_xform"
        camera_xform = UsdGeom.Xform.Define(stage, camera_xform_path)
        camera_xform.ClearXformOpOrder()
        cx_translate = camera_xform.AddTranslateOp()
        cx_translate.Set(Gf.Vec3d(*[float(x) for x in camera_cfg["local_translation"]]))
        cx_orient = camera_xform.AddOrientOp()
        cx_orient.Set(Gf.Quatf(float(cam_qw), float(cam_qx), float(cam_qy), float(cam_qz)))
        camera_prim_path = f"{camera_xform_path}/stage1_camera"
        print(
            f"[run_stage3_mono] Camera parent Xform: {camera_xform_path} "
            f"rpy_deg={cam_orient_deg}",
            flush=True,
        )
    else:
        camera_prim_path = f"{rigid_body_path}/stage1_camera"

    camera = Camera(
        prim_path=camera_prim_path,
        resolution=tuple(camera_cfg["resolution"]),
        # Translation/orientation on parent Xform if oriented, else on Camera.
        translation=(
            None
            if has_cam_orient
            else np.asarray(camera_cfg["local_translation"], dtype=np.float32)
        ),
    )
    camera.initialize()
    camera.set_focal_length(float(camera_cfg["focal_length"]) / 10.0)
    camera.set_clipping_range(
        float(camera_cfg["clipping_range"][0]), float(camera_cfg["clipping_range"][1])
    )

    lidar_prim_path = f"{rigid_body_path}/stage1_lidar"
    lidar = LidarRtx(  # noqa: F841  (handle kept alive for extension lifetime)
        prim_path=lidar_prim_path,
        config_file_name=lidar_cfg["profile"],
        translation=np.asarray(lidar_cfg["local_translation"], dtype=np.float32),
    )
    lidar.initialize()

    # 2D LiDAR (LaserScan) — optional, mirrors the 3D LiDAR pipeline.
    # config_file_name receives the Isaac-Sim bundled profile *name* only
    # (e.g. "Example_Rotary_2D"), never a filesystem path (§10.8 regression).
    lidar_2d_cfg = sensors_cfg.get("lidar_2d")
    lidar_2d_prim_path = None
    if lidar_2d_cfg is not None:
        lidar_2d_prim_path = f"{rigid_body_path}/stage1_lidar_2d"
        lidar_2d = LidarRtx(  # noqa: F841  (handle kept alive for extension lifetime)
            prim_path=lidar_2d_prim_path,
            config_file_name=lidar_2d_cfg["profile"],
            translation=np.asarray(lidar_2d_cfg["local_translation"], dtype=np.float32),
        )
        lidar_2d.initialize()
        print(
            f"[run_stage3_mono] 2D LiDAR attached at {lidar_2d_prim_path} "
            f"profile='{lidar_2d_cfg['profile']}'",
            flush=True,
        )

    imu_prim_path = f"{rigid_body_path}/stage1_imu"
    imu = IMUSensor(
        prim_path=imu_prim_path,
        translation=np.asarray(imu_cfg["local_translation"], dtype=np.float32),
        frequency=int(ros2_cfg["rates"]["imu"]),
    )
    imu.initialize()

    # -------------------------------------------------------------------------
    # § 7.18  OmniGraph — BEFORE world.reset() (run_stage1.py L443-527 verbatim).
    # NOTE: ComputeOdom + PubOdom removed. Odometry is computed and
    # published manually via rclpy in the main loop (see below).
    # -------------------------------------------------------------------------
    ns = ros2_cfg["namespace"]
    topics = ros2_cfg["topics"]

    def ns_topic(name: str) -> str:
        return f"/{ns}/{name}"

    graph_path = "/World/Stage1ROS2Graph"
    keys = og.Controller.Keys
    create_nodes = [
        ("OnTick", "omni.graph.action.OnPlaybackTick"),
        ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
        ("PubClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
        # ComputeOdom + PubOdom removed — odometry via rclpy below.
        ("PubTF", "isaacsim.ros2.bridge.ROS2PublishRawTransformTree"),
        ("ReadIMU", "isaacsim.sensors.physics.IsaacReadIMU"),
        ("PubIMU", "isaacsim.ros2.bridge.ROS2PublishImu"),
        ("RPCamera", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
        ("CamRGB", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        # Separate render product for depth to avoid buffer conflict
        # with RGB sharing the same render product.
        ("RPDepth", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
        ("CamDepth", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("RPLidar", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
        ("LidarHelper", "isaacsim.ros2.bridge.ROS2RtxLidarHelper"),
    ]
    connect_edges = [
        ("OnTick.outputs:tick", "PubClock.inputs:execIn"),
        ("ReadSimTime.outputs:simulationTime", "PubClock.inputs:timeStamp"),
        ("OnTick.outputs:tick", "PubTF.inputs:execIn"),
        ("ReadSimTime.outputs:simulationTime", "PubTF.inputs:timeStamp"),
        ("OnTick.outputs:tick", "ReadIMU.inputs:execIn"),
        ("ReadIMU.outputs:execOut", "PubIMU.inputs:execIn"),
        ("ReadIMU.outputs:angVel", "PubIMU.inputs:angularVelocity"),
        ("ReadIMU.outputs:linAcc", "PubIMU.inputs:linearAcceleration"),
        ("ReadIMU.outputs:orientation", "PubIMU.inputs:orientation"),
        ("ReadSimTime.outputs:simulationTime", "PubIMU.inputs:timeStamp"),
        # RGB: RPCamera → CamRGB
        ("OnTick.outputs:tick", "RPCamera.inputs:execIn"),
        ("RPCamera.outputs:execOut", "CamRGB.inputs:execIn"),
        ("RPCamera.outputs:renderProductPath", "CamRGB.inputs:renderProductPath"),
        # Depth: separate RPDepth → CamDepth
        ("OnTick.outputs:tick", "RPDepth.inputs:execIn"),
        ("RPDepth.outputs:execOut", "CamDepth.inputs:execIn"),
        ("RPDepth.outputs:renderProductPath", "CamDepth.inputs:renderProductPath"),
        # LiDAR
        ("OnTick.outputs:tick", "RPLidar.inputs:execIn"),
        ("RPLidar.outputs:execOut", "LidarHelper.inputs:execIn"),
        ("RPLidar.outputs:renderProductPath", "LidarHelper.inputs:renderProductPath"),
    ]
    set_values = [
        ("PubClock.inputs:topicName", "/clock"),
        # Articulation joint TF on a separate topic to avoid conflict
        # with the manual odom→base_link publisher on /tf.
        ("PubTF.inputs:topicName", "/tf_raw"),
        ("ReadIMU.inputs:imuPrim", [imu_prim_path]),
        ("PubIMU.inputs:topicName", ns_topic(topics["imu"])),
        ("PubIMU.inputs:frameId", "imu_link"),
        ("RPCamera.inputs:cameraPrim", [camera_prim_path]),
        ("RPCamera.inputs:width", int(camera_cfg["resolution"][0])),
        ("RPCamera.inputs:height", int(camera_cfg["resolution"][1])),
        ("CamRGB.inputs:type", "rgb"),
        ("CamRGB.inputs:topicName", ns_topic(topics["rgb"])),
        ("CamRGB.inputs:frameId", "camera_link"),
        ("RPDepth.inputs:cameraPrim", [camera_prim_path]),
        ("RPDepth.inputs:width", int(camera_cfg["resolution"][0])),
        ("RPDepth.inputs:height", int(camera_cfg["resolution"][1])),
        ("CamDepth.inputs:type", "depth"),
        ("CamDepth.inputs:topicName", ns_topic(topics["depth"])),
        ("CamDepth.inputs:frameId", "camera_link"),
        ("RPLidar.inputs:cameraPrim", [lidar_prim_path]),
        ("LidarHelper.inputs:topicName", ns_topic(topics["lidar"])),
        ("LidarHelper.inputs:frameId", "lidar_link"),
        ("LidarHelper.inputs:type", "point_cloud"),
    ]

    # 2D LiDAR OmniGraph additions — same pattern as 3D LiDAR with
    # type="laser_scan" and its own render product.  `topics["scan"]` and
    # `sensors.lidar_2d` come from rover_m2020.yaml; if either is absent
    # the block is skipped and the rest of the graph is unaffected.
    if lidar_2d_cfg is not None and "scan" in topics:
        create_nodes += [
            ("RPLidar2D", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
            ("LidarHelper2D", "isaacsim.ros2.bridge.ROS2RtxLidarHelper"),
        ]
        connect_edges += [
            ("OnTick.outputs:tick", "RPLidar2D.inputs:execIn"),
            ("RPLidar2D.outputs:execOut", "LidarHelper2D.inputs:execIn"),
            (
                "RPLidar2D.outputs:renderProductPath",
                "LidarHelper2D.inputs:renderProductPath",
            ),
        ]
        set_values += [
            ("RPLidar2D.inputs:cameraPrim", [lidar_2d_prim_path]),
            ("LidarHelper2D.inputs:topicName", ns_topic(topics["scan"])),
            ("LidarHelper2D.inputs:frameId", "scan_frame"),
            ("LidarHelper2D.inputs:type", "laser_scan"),
        ]

    graph_handle, _nodes, _prims, _info = og.Controller.edit(
        {"graph_path": graph_path, "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: create_nodes,
            keys.CONNECT: connect_edges,
            keys.SET_VALUES: set_values,
        },
    )
    print(f"[run_stage3_mono] Built OmniGraph at {graph_path}", flush=True)

    # -------------------------------------------------------------------------
    # § 7.19  Pre-reset USD DriveAPI setup (run_stage1.py L529-632 verbatim).
    # -------------------------------------------------------------------------
    # set_effort_modes() only writes to USD, never to PhysX tensors.
    # set_gains() has a PhysX path but set_effort_modes/set_max_efforts do not.
    # Therefore ALL USD DriveAPI attributes (gains, effort type, max force)
    # must be set BEFORE world.reset(), which syncs USD → PhysX cache.
    # After reset, set_gains() overwrites gains in PhysX tensors directly.

    drive_joint_names = list(control_cfg["drive_joint_names"])
    steer_joint_names = list(control_cfg["steer_joint_names"])
    drive_damping = float(control_cfg.get("drive_damping", 100000.0))
    drive_max_force = float(control_cfg.get("drive_max_force", 1000000.0))
    steer_stiffness = float(control_cfg.get("steer_stiffness", 50000.0))
    steer_damping_val = float(control_cfg.get("steer_damping", 5000.0))
    steer_max_force = float(control_cfg.get("steer_max_force", 100000.0))
    suspension_names = control_cfg.get("suspension_joint_names", [])
    suspension_damping_val = float(control_cfg.get("suspension_damping", 0.0))
    drive_type = str(control_cfg.get("drive_type", "acceleration"))
    print(
        f"[run_stage3_mono] Control params from config: drive_damping={drive_damping}, "
        f"drive_type={drive_type}, steer_kp={steer_stiffness}, steer_kd={steer_damping_val}",
        flush=True,
    )

    joints_scope = f"{chassis_path}/joints"
    for jname in drive_joint_names:
        joint_path = f"{joints_scope}/{jname}"
        joint_prim = stage.GetPrimAtPath(joint_path)
        if not joint_prim.IsValid():
            print(
                f"[run_stage3_mono] WARNING: drive joint not found: {joint_path}",
                file=sys.stderr,
            )
            continue
        if not joint_prim.HasAPI(UsdPhysics.DriveAPI, "angular"):
            UsdPhysics.DriveAPI.Apply(joint_prim, "angular")
        drive_api = UsdPhysics.DriveAPI(joint_prim, "angular")
        # Velocity mode: stiffness=0, damping=high.
        joint_prim.CreateAttribute("drive:angular:physics:damping", Sdf.ValueTypeNames.Float).Set(
            drive_damping
        )
        joint_prim.CreateAttribute("drive:angular:physics:stiffness", Sdf.ValueTypeNames.Float).Set(
            0.0
        )
        joint_prim.CreateAttribute("drive:angular:physics:maxForce", Sdf.ValueTypeNames.Float).Set(
            drive_max_force
        )
        # Effort type: "acceleration" auto-compensates for mass/inertia.
        if not drive_api.GetTypeAttr():
            drive_api.CreateTypeAttr().Set(drive_type)
        else:
            drive_api.GetTypeAttr().Set(drive_type)

    for jname in steer_joint_names:
        joint_path = f"{joints_scope}/{jname}"
        joint_prim = stage.GetPrimAtPath(joint_path)
        if not joint_prim.IsValid():
            continue
        if not joint_prim.HasAPI(UsdPhysics.DriveAPI, "angular"):
            UsdPhysics.DriveAPI.Apply(joint_prim, "angular")
        drive_api = UsdPhysics.DriveAPI(joint_prim, "angular")
        # Position mode: stiffness=high, damping=moderate.
        joint_prim.CreateAttribute("drive:angular:physics:stiffness", Sdf.ValueTypeNames.Float).Set(
            steer_stiffness
        )
        joint_prim.CreateAttribute("drive:angular:physics:damping", Sdf.ValueTypeNames.Float).Set(
            steer_damping_val
        )
        joint_prim.CreateAttribute("drive:angular:physics:maxForce", Sdf.ValueTypeNames.Float).Set(
            steer_max_force
        )
        if not drive_api.GetTypeAttr():
            drive_api.CreateTypeAttr().Set(drive_type)
        else:
            drive_api.GetTypeAttr().Set(drive_type)

    for jname in suspension_names:
        joint_path = f"{joints_scope}/{jname}"
        joint_prim = stage.GetPrimAtPath(joint_path)
        if not joint_prim.IsValid():
            continue
        if not joint_prim.HasAPI(UsdPhysics.DriveAPI, "angular"):
            UsdPhysics.DriveAPI.Apply(joint_prim, "angular")
        drive_api = UsdPhysics.DriveAPI(joint_prim, "angular")
        joint_prim.CreateAttribute("drive:angular:physics:damping", Sdf.ValueTypeNames.Float).Set(
            suspension_damping_val
        )
        joint_prim.CreateAttribute("drive:angular:physics:stiffness", Sdf.ValueTypeNames.Float).Set(
            0.0
        )
        if not drive_api.GetTypeAttr():
            drive_api.CreateTypeAttr().Set(drive_type)
        else:
            drive_api.GetTypeAttr().Set(drive_type)

    print(
        f"[run_stage3_mono] USD DriveAPI set (pre-reset): drive_type={drive_type}",
        flush=True,
    )

    # -------------------------------------------------------------------------
    # § 7.20  Articulation + world.reset + initialize (run_stage1.py L634-700).
    # -------------------------------------------------------------------------
    articulation = Articulation(prim_paths_expr=prim_path)
    world.reset()
    articulation.initialize()

    dof_names = list(articulation.dof_names)
    print(f"[run_stage3_mono] Articulation DOFs ({len(dof_names)}): {dof_names}", flush=True)

    drive_indices = resolve_joint_indices(dof_names, drive_joint_names)
    steer_indices = resolve_joint_indices(dof_names, steer_joint_names)
    susp_indices: List[int] = []
    if suspension_names and suspension_damping_val > 0.0:
        susp_indices = resolve_joint_indices(dof_names, list(suspension_names))

    wheel_radius = float(control_cfg["wheel_radius"])
    wheelbase = float(control_cfg["wheelbase"])
    track_steer = float(control_cfg["track_steer"])
    track_middle = float(control_cfg["track_middle"])
    v_max = float(control_cfg["max_linear_velocity"])
    w_max = float(control_cfg["max_angular_velocity"])

    # Initialize steer joints at zero.
    zero_steer = np.zeros(len(steer_indices), dtype=np.float32)
    try:
        articulation.set_joint_positions(zero_steer, joint_indices=np.asarray(steer_indices))
    except Exception as exc:  # noqa: BLE001
        print(
            f"[run_stage3_mono] Warning: could not init steer joints: {exc}",
            file=sys.stderr,
        )

    # -------------------------------------------------------------------------
    # § 7.21  Post-reset: set_gains() overwrites gains in PhysX tensors.
    # -------------------------------------------------------------------------
    print("[run_stage3_mono] Warming up physics handle ...", flush=True)
    for _ in range(10):
        world.step(render=True)

    import omni.timeline  # noqa: E402

    timeline = omni.timeline.get_timeline_interface()
    if timeline.is_stopped():
        print("[run_stage3_mono] Timeline is stopped — calling play().", flush=True)
        timeline.play()
        for _ in range(5):
            world.step(render=True)

    handle_valid = articulation.is_physics_handle_valid()
    print(
        f"[run_stage3_mono] timeline stopped={timeline.is_stopped()}, "
        f"physics_handle_valid={handle_valid}",
        flush=True,
    )

    num_dof = len(dof_names)
    kps = np.zeros((1, num_dof), dtype=np.float32)
    kds = np.zeros((1, num_dof), dtype=np.float32)

    for idx in drive_indices:
        kds[0, idx] = drive_damping
    for idx in steer_indices:
        kps[0, idx] = steer_stiffness
        kds[0, idx] = steer_damping_val
    for idx in susp_indices:
        kds[0, idx] = suspension_damping_val

    articulation.set_gains(kps=kps, kds=kds)
    print("[run_stage3_mono] PD gains reinforced via set_gains().", flush=True)

    # --- Readback verification ---
    actual_kps, actual_kds = articulation.get_gains()
    check_list = []
    for name, idx in zip(drive_joint_names, drive_indices):
        check_list.append((name, idx, 0.0, drive_damping))
    for name, idx in zip(steer_joint_names, steer_indices):
        check_list.append((name, idx, steer_stiffness, steer_damping_val))
    for name, idx in zip(list(suspension_names), susp_indices):
        check_list.append((name, idx, 0.0, suspension_damping_val))

    print("[run_stage3_mono] Gain readback:", flush=True)
    for name, idx, _exp_kp, _exp_kd in check_list:
        print(
            f"  {name}: kp={actual_kps[0, idx]:.1f}  kd={actual_kds[0, idx]:.1f}",
            flush=True,
        )

    # Effort mode readback (verify USD→PhysX sync worked).
    effort_modes = articulation.get_effort_modes()
    if effort_modes is not None:
        sample_modes = [
            effort_modes[0][drive_indices[0]] if effort_modes[0] else "N/A",
            effort_modes[0][steer_indices[0]] if effort_modes[0] else "N/A",
        ]
        print(
            f"[run_stage3_mono] Effort mode readback: drive={sample_modes[0]}, "
            f"steer={sample_modes[1]}",
            flush=True,
        )

    # --- Capture initial rover pose for manual odometry --------------------
    # The odom frame is anchored at the rover's position at t=0. Every tick
    # we compute the delta (current − initial) and publish it as the
    # odom → base_link transform.
    init_poses = articulation.get_world_poses()
    if init_poses is not None:
        _ip, _iq = init_poses
        odom_init_pos = (_ip[0] if _ip.ndim == 2 else _ip).copy()
        odom_init_quat = (_iq[0] if _iq.ndim == 2 else _iq).copy()
    else:
        odom_init_pos = np.zeros(3, dtype=np.float32)
        odom_init_quat = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    print(
        f"[run_stage3_mono] Odom origin: pos=({odom_init_pos[0]:.3f},"
        f"{odom_init_pos[1]:.3f},{odom_init_pos[2]:.3f})",
        flush=True,
    )

    # -------------------------------------------------------------------------
    # § 7.22  rclpy cmd_vel + static TF + manual odom publisher.
    # (run_stage1.py L751-856 verbatim, gated by --no-ros2.)
    # -------------------------------------------------------------------------
    node = None
    static_broadcaster = None  # noqa: F841  (kept alive via local binding)
    odom_tf_broadcaster = None
    odom_pub = None
    odom_init_quat_inv = None
    latest_twist = {"v": 0.0, "w": 0.0}

    if not args.no_ros2:
        rclpy.init(args=None)
        node = rclpy.create_node(
            f"{ns}_stage3_runtime",
            parameter_overrides=[
                rclpy.parameter.Parameter(
                    "use_sim_time",
                    rclpy.parameter.Parameter.Type.BOOL,
                    True,
                )
            ],
        )

        def cmd_vel_cb(msg: Twist) -> None:
            latest_twist["v"] = float(msg.linear.x)
            latest_twist["w"] = float(msg.angular.z)

        cmd_vel_topic = ns_topic(topics["cmd_vel"])
        node.create_subscription(Twist, cmd_vel_topic, cmd_vel_cb, 10)
        print(f"[run_stage3_mono] Subscribed to {cmd_vel_topic}", flush=True)

        # --- Static TF: base_link → sensor frames --------------------------
        # PubTF (ROS2PublishRawTransformTree) only publishes joint-chain TF
        # from the articulation. Sensor prims (camera, lidar, imu) are Isaac
        # Sim creations, not part of the URDF kinematic tree, so their
        # frames are absent from /tf. SLAM/Nav2 need these frames to exist.
        #
        # Publish static transforms from base_link to each sensor frame.
        # Config local_translation is in Body_Chassis local frame (180°
        # X-roll).  In that frame Z- = up, so config (x, y, z) → world
        # (x, -y, -z).
        static_broadcaster = StaticTransformBroadcaster(node)
        sensor_tf_configs = [
            ("camera_link", camera_cfg["local_translation"]),
            ("lidar_link", lidar_cfg["local_translation"]),
            ("imu_link", imu_cfg["local_translation"]),
        ]
        if lidar_2d_cfg is not None:
            sensor_tf_configs.append(("scan_frame", lidar_2d_cfg["local_translation"]))
        static_transforms = []
        for child_frame, local_t in sensor_tf_configs:
            tf_msg = TransformStamped()
            tf_msg.header.frame_id = "base_link"
            tf_msg.child_frame_id = child_frame
            tf_msg.transform.translation.x = float(local_t[0])
            tf_msg.transform.translation.y = -float(local_t[1])
            tf_msg.transform.translation.z = -float(local_t[2])
            tf_msg.transform.rotation.w = 1.0
            tf_msg.transform.rotation.x = 0.0
            tf_msg.transform.rotation.y = 0.0
            tf_msg.transform.rotation.z = 0.0
            static_transforms.append(tf_msg)
            print(
                f"[run_stage3_mono] Static TF: {tf_msg.header.frame_id} → {child_frame} "
                f"t=({tf_msg.transform.translation.x:.2f}, "
                f"{tf_msg.transform.translation.y:.2f}, "
                f"{tf_msg.transform.translation.z:.2f})",
                flush=True,
            )
        static_broadcaster.sendTransform(static_transforms)
        print(
            f"[run_stage3_mono] Published {len(static_transforms)} static TF frames on /tf_static",
            flush=True,
        )

        # --- Manual odom publisher (rclpy) ---------------------------------
        odom_tf_broadcaster = TransformBroadcaster(node)
        odom_pub = node.create_publisher(Odometry, ns_topic(topics["odom"]), 10)
        print(
            f"[run_stage3_mono] Manual odom publisher: "
            f"TF odom→base_link + {ns_topic(topics['odom'])} @ ~60 Hz",
            flush=True,
        )

    # Pure quaternion helpers (closed over odom_init_quat).
    def quat_inverse(q: np.ndarray) -> np.ndarray:
        """Return inverse of unit quaternion [w, x, y, z]."""
        return np.array([q[0], -q[1], -q[2], -q[3]], dtype=np.float32)

    def quat_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Hamilton product of two [w, x, y, z] quaternions."""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array(
            [
                w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
                w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            ],
            dtype=np.float32,
        )

    def quat_rotate_vec(q: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Rotate vector v by quaternion q ([w,x,y,z])."""
        v_quat = np.array([0.0, v[0], v[1], v[2]], dtype=np.float32)
        q_inv = quat_inverse(q)
        result = quat_multiply(quat_multiply(q, v_quat), q_inv)
        return result[1:4]

    odom_init_quat_inv = quat_inverse(odom_init_quat)

    # -------------------------------------------------------------------------
    # § 7.23  Main loop (run_stage1.py L858-1132 verbatim; prefixes adapted).
    # -------------------------------------------------------------------------
    drive_idx_arr = np.asarray(drive_indices, dtype=np.int32)
    steer_idx_arr = np.asarray(steer_indices, dtype=np.int32)

    # Sign convention: 180° X-roll inverts steer Z-axis direction.
    negate_steer = bool(control_cfg.get("negate_steer", False))
    if negate_steer:
        print("[run_stage3_mono] negate_steer=True: inverting steer angles.", flush=True)

    debug_logging = bool(control_cfg.get("debug_logging", False))
    step_count = 0

    # Velocity ramp: limits per-step change in wheel speed targets to prevent
    # the massive impulse that occurs when set_joint_velocity_targets jumps
    # from 0 to 0.375 with high kd in acceleration mode.
    n_drive = len(drive_indices)
    current_drive_targets = np.zeros(n_drive, dtype=np.float32)
    max_wheel_accel_rate = float(control_cfg.get("max_wheel_accel_rate", 0.5))
    per_step_limit = max_wheel_accel_rate * physics_dt
    decel_multiplier = float(control_cfg.get("decel_multiplier", 1.0))
    if max_wheel_accel_rate > 0:
        print(
            f"[run_stage3_mono] Velocity ramp: max_wheel_accel_rate={max_wheel_accel_rate} rad/s², "
            f"per_step_limit={per_step_limit:.6f} rad/s, decel_mult={decel_multiplier}",
            flush=True,
        )

    # Steer angle limits and ramp.
    max_steer_angle = float(control_cfg.get("max_steer_angle", 0.7))
    steer_ramp_rate = float(control_cfg.get("steer_ramp_rate", 2.0))
    n_steer = len(steer_indices)
    current_steer_targets = np.zeros(n_steer, dtype=np.float32)
    steer_per_step_limit = steer_ramp_rate * physics_dt
    print(
        f"[run_stage3_mono] Steer limits: max_angle={max_steer_angle:.2f} rad "
        f"({np.degrees(max_steer_angle):.1f}°), "
        f"ramp_rate={steer_ramp_rate} rad/s, per_step={steer_per_step_limit:.6f} rad",
        flush=True,
    )

    # Dynamic atmosphere timing state.
    elapsed = 0.0

    print("[run_stage3_mono] Entering main loop. Ctrl+C to exit.", flush=True)
    try:
        while simulation_app.is_running():
            if node is not None:
                rclpy.spin_once(node, timeout_sec=0.0)

            v, w = clamp_twist(latest_twist["v"], latest_twist["w"], v_max, w_max)
            steer_angles, wheel_vels = ackermann_command(
                v, w, wheelbase, track_steer, track_middle, wheel_radius
            )
            if negate_steer:
                steer_angles = -steer_angles

            # Clamp steer angles to mechanical limits.
            steer_angles = np.clip(steer_angles, -max_steer_angle, max_steer_angle)

            # Apply steer angle ramp to prevent snap transitions.
            if steer_ramp_rate > 0:
                s_delta = steer_angles - current_steer_targets
                s_delta = np.clip(s_delta, -steer_per_step_limit, steer_per_step_limit)
                current_steer_targets = current_steer_targets + s_delta
                ramped_steer = current_steer_targets
            else:
                ramped_steer = steer_angles

            # Apply drive velocity ramp with asymmetric decel.
            if max_wheel_accel_rate > 0:
                delta = wheel_vels - current_drive_targets
                is_decel = np.abs(wheel_vels) < np.abs(current_drive_targets)
                step_lim = np.where(is_decel, per_step_limit * decel_multiplier, per_step_limit)
                delta = np.clip(delta, -step_lim, step_lim)
                current_drive_targets = current_drive_targets + delta
                ramped_vels = current_drive_targets
            else:
                ramped_vels = wheel_vels

            try:
                articulation.set_joint_position_targets(ramped_steer, joint_indices=steer_idx_arr)
                articulation.set_joint_velocity_targets(ramped_vels, joint_indices=drive_idx_arr)
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[run_stage3_mono] joint target failed: {exc}",
                    file=sys.stderr,
                )

            if debug_logging and step_count % 60 == 0:
                try:
                    actual_pos = articulation.get_joint_positions()
                    actual_vel = articulation.get_joint_velocities()
                    if actual_pos is not None and actual_vel is not None:
                        s_pos = (
                            actual_pos[0, steer_idx_arr]
                            if actual_pos.ndim == 2
                            else actual_pos[steer_idx_arr]
                        )
                        d_vel = (
                            actual_vel[0, drive_idx_arr]
                            if actual_vel.ndim == 2
                            else actual_vel[drive_idx_arr]
                        )
                        print(
                            f"[DIAG {step_count}] twist=({v:.3f},{w:.3f}) "
                            f"steer_cmd={steer_angles} steer_act={s_pos} "
                            f"drive_cmd={ramped_vels} drive_act={d_vel}",
                            flush=True,
                        )
                except Exception:  # noqa: BLE001
                    pass
                try:
                    imu_frame = imu.get_current_frame()
                    if imu_frame is not None and "lin_acc" in imu_frame:
                        la = imu_frame["lin_acc"]
                        print(
                            f"[DIAG {step_count}] imu_acc="
                            f"({la[0]:.4f},{la[1]:.4f},{la[2]:.4f})",
                            flush=True,
                        )
                except Exception:  # noqa: BLE001
                    pass

            # --- Publish odom → base_link TF + Odometry message -----------
            if node is not None and odom_pub is not None and odom_tf_broadcaster is not None:
                try:
                    rover_poses_odom = articulation.get_world_poses()
                    if rover_poses_odom is not None:
                        _rp, _rq = rover_poses_odom
                        cur_pos = _rp[0] if _rp.ndim == 2 else _rp
                        cur_quat = _rq[0] if _rq.ndim == 2 else _rq

                        delta_pos_world = cur_pos - odom_init_pos
                        delta_pos_odom = quat_rotate_vec(odom_init_quat_inv, delta_pos_world)
                        delta_quat = quat_multiply(odom_init_quat_inv, cur_quat)

                        now = node.get_clock().now().to_msg()

                        odom_tf = TransformStamped()
                        odom_tf.header.stamp = now
                        odom_tf.header.frame_id = "odom"
                        odom_tf.child_frame_id = "base_link"
                        odom_tf.transform.translation.x = float(delta_pos_odom[0])
                        odom_tf.transform.translation.y = float(delta_pos_odom[1])
                        odom_tf.transform.translation.z = float(delta_pos_odom[2])
                        odom_tf.transform.rotation.w = float(delta_quat[0])
                        odom_tf.transform.rotation.x = float(delta_quat[1])
                        odom_tf.transform.rotation.y = float(delta_quat[2])
                        odom_tf.transform.rotation.z = float(delta_quat[3])
                        odom_tf_broadcaster.sendTransform(odom_tf)

                        odom_msg = Odometry()
                        odom_msg.header.stamp = now
                        odom_msg.header.frame_id = "odom"
                        odom_msg.child_frame_id = "base_link"
                        odom_msg.pose.pose.position.x = float(delta_pos_odom[0])
                        odom_msg.pose.pose.position.y = float(delta_pos_odom[1])
                        odom_msg.pose.pose.position.z = float(delta_pos_odom[2])
                        odom_msg.pose.pose.orientation.w = float(delta_quat[0])
                        odom_msg.pose.pose.orientation.x = float(delta_quat[1])
                        odom_msg.pose.pose.orientation.y = float(delta_quat[2])
                        odom_msg.pose.pose.orientation.z = float(delta_quat[3])

                        try:
                            lin_vel = articulation.get_linear_velocities()
                            ang_vel = articulation.get_angular_velocities()
                            if lin_vel is not None and ang_vel is not None:
                                lv = lin_vel[0] if lin_vel.ndim == 2 else lin_vel
                                av = ang_vel[0] if ang_vel.ndim == 2 else ang_vel
                                cur_quat_inv = quat_inverse(cur_quat)
                                body_lv = quat_rotate_vec(cur_quat_inv, lv)
                                body_av = quat_rotate_vec(cur_quat_inv, av)
                                odom_msg.twist.twist.linear.x = float(body_lv[0])
                                odom_msg.twist.twist.linear.y = float(body_lv[1])
                                odom_msg.twist.twist.linear.z = float(body_lv[2])
                                odom_msg.twist.twist.angular.x = float(body_av[0])
                                odom_msg.twist.twist.angular.y = float(body_av[1])
                                odom_msg.twist.twist.angular.z = float(body_av[2])
                        except Exception:  # noqa: BLE001
                            pass

                        odom_pub.publish(odom_msg)
                except Exception as odom_exc:  # noqa: BLE001
                    if step_count < 120:
                        print(
                            f"[run_stage3_mono] odom publish failed: {odom_exc}",
                            file=sys.stderr,
                        )

            # --- Dynamic atmosphere update (run_stage2 L434-482 condensed) --
            if dynamic_enabled and step_count % update_interval == 0 and step_count > 0:
                current_tau = atmosphere_state["tau"]
                elapsed += physics_dt * update_interval * time_scale
                t = (elapsed % sol_duration) / sol_duration
                atmosphere_state["time_of_sol"] = t

                dyn_sun_pos = compute_sol_sun_position(
                    time_of_sol_fraction=t,
                    start_azimuth_deg=sweep_start_az,
                    end_azimuth_deg=sweep_end_az,
                    max_elevation_deg=sweep_max_el,
                )
                atmosphere_state["sun_azimuth_deg"] = dyn_sun_pos.azimuth_deg
                atmosphere_state["sun_elevation_deg"] = dyn_sun_pos.elevation_deg

                dyn_intensity = compute_direct_intensity(
                    solar_constant, current_tau, dyn_sun_pos.zenith_angle_rad
                )
                dyn_diffuse = compute_diffuse_fraction(current_tau)
                dyn_sky = compute_sky_dome_params(current_tau, hdri_dir)

                atmosphere_state["direct_intensity"] = dyn_intensity
                atmosphere_state["diffuse_fraction"] = dyn_diffuse

                update_sun_light(stage, dyn_sun_pos, dyn_intensity, dyn_diffuse, render_config)
                update_sky_dome(stage, dyn_sky, dyn_diffuse, render_config)
                configure_atmosphere_fog(stage, current_tau, render_config)

                if atmo_panel is not None:
                    atmo_panel.update_display()

            step_count += 1

            world.step(render=True)
    except KeyboardInterrupt:
        print("[run_stage3_mono] KeyboardInterrupt -- shutting down.", flush=True)
    finally:
        if node is not None:
            try:
                node.destroy_node()
            except Exception:  # noqa: BLE001
                pass
            try:
                rclpy.shutdown()
            except Exception:  # noqa: BLE001
                pass
        # Isaac Sim 5.x shutdown path has known heap corruption after certain
        # extensions; fall back to os._exit(0) if simulation_app.close()
        # cannot complete cleanly. Keep the call for documentation.
        try:
            simulation_app.close()
        except Exception as exc:  # noqa: BLE001
            print(f"[run_stage3_mono] simulation_app.close() raised: {exc}", file=sys.stderr)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
