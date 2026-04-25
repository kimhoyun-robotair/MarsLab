# MarsLab Scenario YAML Format

**Audience:** anyone authoring a new mission scenario or extending an existing
one.  This document describes the YAML structure used by every file under
`configs/scenarios/` and walks through how the loader resolves overrides,
where the pydantic schema lives, and how to add a custom scenario step by
step.

**Companion files:**

* Pydantic schema: `marslab/config/schema/` (one module per top-level block).
* YAML + base loader: `marslab/config/yaml_loader.py`.
* Scenario loader entry point: `marslab/config/scenario_loader.py`.
* Reference scenarios: `configs/scenarios/*.yaml`.
* Sensor presets: `configs/sensors/*.yaml`.
* Rover base config: `configs/robots/rover_m2020.yaml`.

This file targets MarsLab v1.0 (sprint Day 4-5 2026-04-25).  The format is
stable for v1.0; v2.0 may add a `photorealism:` block and v3.0 will add
`terramechanics:` — both will land as additive, optional top-level keys so
v1.0 scenarios continue to load without edits.

---

## 1. Overview — top-level structure

Every scenario YAML is a map with a small, fixed set of top-level keys.
Anything outside this set fails validation (`extra="forbid"` is set on every
schema model — Reviewer 2 #12, 2026-04-24).  The keys are:

| Key                | Required | Schema model                         |
|--------------------|----------|--------------------------------------|
| `base_config`      | optional | (resolved by loader, not validated)  |
| `mars_env`         | yes (via base) | `marslab.config.schema.mars_env.MarsEnvConfig` |
| `terrain`          | yes      | `marslab.config.schema.terrain.TerrainConfig` |
| `rendering`        | yes (via base) | `marslab.config.schema.rendering.RenderingConfig` |
| `rover`            | optional | `marslab.config.schema.robot.RobotConfig` (+ `base_config:`) |
| `scene`            | optional | `marslab.config.schema.scene.SceneConfig` |
| `ros2_bridge`      | optional | `marslab.config.schema.ros2_bridge.Ros2BridgeConfig` |

The full root schema is `marslab.config.schema.root.MarsLabConfig`; it
aggregates the per-block models above.  Validation happens in
`marslab.config.loader.load_and_validate(...)`.

### 1.1 The `base_config:` inheritance pattern

Two independent inheritance mechanisms run in order at the top of
`marslab.config.yaml_loader.load_scenario_config`:

1. **Root-level `base_config:`** — typically pointed at
   `configs/scenarios/_base.yaml`, which carries the shared `mars_env` +
   `rendering` + empty `scene.structure_assets` defaults.  The scenario
   YAML deep-merges on top: scenario wins, lists are replaced (not
   concatenated) by `marslab.config.yaml_loader.deep_merge`.
2. **`rover.base_config:`** — points at `configs/robots/rover_m2020.yaml`
   so the same rover physics + sensor stack lives in one file instead of
   being copied into each scenario.  Runs after the root merge so the
   final dict is `{root_base} + scenario + rover:{robot_base + scenario.rover}`.

A scenario YAML therefore only needs to declare its real overrides; see
`configs/scenarios/jezero_flat.yaml` for the minimal pattern.

```yaml
# configs/scenarios/jezero_flat.yaml (excerpt)
base_config: _base.yaml

mars_env:
  dynamic_atmosphere:
    enabled: true

terrain:
  source: "hirise"
  scenario_name: "jezero_flat"
  converted_dem_dir: "assets/terrain/dem/jezero_crater_converted"
  dem_crop:
    row: 180
    col: 0
    height: 200
    width: 200
  rock_sfd_k: 0
  rock_diameter_range: [0.20, 3.0]
  semantic_classes: ["soil", "bedrock", "sand", "big_rock"]
  texture_dir: "assets/materials/mars_hirise"
  rock_color: [0.42, 0.28, 0.20]
  rock_roughness: 0.92
  rock_mesh_dir: "assets/rocks"
  rock_texture_dir: "assets/materials/mars_rock"
  uv_scale: 1.0
  seed: 42

rover:
  enabled: true
  base_config: "configs/robots/rover_m2020.yaml"
  spawn:
    mode: "dem_center"
    xy: [0.0, 0.0]
    z_offset: 0.5
    orientation_rpy: [3.14159, 0.0, 0.0]
```

### 1.2 What `_base.yaml` provides

Path: `configs/scenarios/_base.yaml`.  Holds the shared `mars_env`
defaults (gravity = 3.72 m/s^2, atmospheric pressure 610 Pa, sun azimuth /
elevation, dynamic atmosphere parameters), the shared `rendering` block
(ray-tracing mode + sky dome + fog), and an empty `scene.structure_assets:
[]` so every scenario inherits a parsable list.  See the file for the full
defaults; this document does not duplicate them to avoid drift.

---

## 2. `mars_env` block

Defined in `marslab/config/schema/mars_env.py` (`MarsEnvConfig`).  Holds
**physics constants** (gravity, atmospheric pressure / density, surface
albedo range) and the **dynamic atmosphere** sub-block that drives the
sun sweep + tau profile at runtime.

| Field                         | Type        | Notes                                          |
|-------------------------------|-------------|-------------------------------------------------|
| `gravity`                     | float       | 3.72 m/s^2 (Mars; do not change for v1.0)       |
| `atmo_pressure`               | int         | Pascals; 610 Pa is the M2020 / MSL mean        |
| `atmo_density`                | float       | kg/m^3; 0.020 default                          |
| `dust_optical_depth`          | float       | tau; clear-ish default 0.3                     |
| `solar_constant_mean`         | float       | W/m^2 at Mars distance (589 default)           |
| `surface_albedo_range`        | [float, float] | [0.10, 0.40] for v1.0                       |
| `sol_duration_seconds`        | int         | 88642 s (24 h 37 m 22 s)                       |
| `dust_opacity_range`          | [float, float] | tau range for domain randomisation          |
| `sun_azimuth_deg`             | float       | 0=N, 90=E, 180=S, 270=W                        |
| `sun_elevation_deg`           | float       | degrees above horizon                          |
| `seed`                        | int         | seed propagated to every randomised function   |
| `dynamic_atmosphere`          | sub-block   | see below                                      |

The `dynamic_atmosphere` sub-block carries the runtime sun sweep and
tau profile:

```yaml
mars_env:
  dynamic_atmosphere:
    enabled: true               # static atmosphere when false
    time_scale: 200.0
    sun_sweep:
      start_azimuth_deg: 90
      end_azimuth_deg: 270
      max_elevation_deg: 60
    tau_profile: "constant"     # "constant" | "ramp" | "sine"
    tau_constant:
      base_tau: 0.3
    update_interval_frames: 10
```

The full schema (including `tau_ramp` / `tau_sine` profiles) lives in
`marslab/config/schema/mars_env.py`.

---

## 3. `terrain` block

Defined in `marslab/config/schema/terrain.py` (`TerrainConfig`,
`DemCropConfig`, `ProceduralCanyonConfig`, `CaveConfig`,
`CaveGeometryConfig`).  Two `source` modes are supported:

* `"hirise"` — load a HiRISE DEM (GeoTIFF, pre-converted to npy +
  metadata.json by `scripts/convert_dem.py`).
* `"procedural"` — generate a synthetic elevation map via
  `marslab.terrain.procedural_generator.generate_terrain` (presets:
  `flat`, `crater`, `hills`, `rocky_plain`, `cave`, `canyon`).

A `dem_crop:` sub-block (HiRISE only) selects the row / col / height /
width pixel window used for the scenario.  See
`configs/scenarios/jezero_crater.yaml` for a fuller crop example.

Rock placement is config-driven via Golombek SFD parameters
(`rock_sfd_k`, `rock_diameter_range`).  A `cave:` sub-block carries
the lava-tube geometry parameters used by
`marslab.terrain.cave_generator`; see
`configs/scenarios/cave_lava_tube.yaml` for a complete example.

---

## 4. `rover` block

The `rover` block enables a single rover and points at the M2020 base
config.  v1.0 ships **a single M2020 rover** — multi-rover support is
deferred to v1.5 (after iSpaRo 2026).  The schema is
`marslab.config.schema.robot.RobotConfig` (chassis + wheels + suspension
+ control + sensors), with the rover-base merge handled by
`marslab/config/yaml_loader.py:load_scenario_config`.

```yaml
rover:
  enabled: true
  base_config: "configs/robots/rover_m2020.yaml"
  spawn:
    mode: "dem_center"     # "dem_center" | "absolute"
    xy: [0.0, 0.0]         # used by dem_center as offset; by absolute as world coords
    z_offset: 0.5          # only with dem_center; clearance above DEM surface
    orientation_rpy: [3.14159, 0.0, 0.0]
  # Optional per-scenario sensor tweaks override the merged rover-base values.
  sensors:
    camera:
      clipping_range: [0.1, 500.0]
```

### 4.1 Sensor preset reference pattern

The rover's `sensors:` sub-tree mirrors `configs/robots/rover_m2020.yaml`
and validates against
`marslab.config.schema.robot.SensorsConfig` (camera + lidar_3d +
optional lidar_2d + imu).

To swap a hardware preset (e.g. switch the 3D LiDAR USD model from the
generic `Example_Rotary` to a Velodyne VLP-16), declare a per-scenario
override on `Lidar3DConfig.usd_profile`:

```yaml
rover:
  sensors:
    lidar_3d:
      usd_profile: "Velodyne_VLP16"   # falls back to profile_name when null
      profile_name: "Velodyne_VLP16"  # JSON profile (matches usd_profile here)
```

Or copy the whole content of `configs/sensors/velodyne_vlp16.yaml` into
the scenario's `sensors.lidar_3d` block.  The two preset YAMLs in
`configs/sensors/` are designed for this drop-in pattern:

* `configs/sensors/velodyne_vlp16.yaml` — Velodyne VLP-16 3D LiDAR.
* `configs/sensors/hokuyo_ust_10lx.yaml` — Hokuyo UST-10LX 2D LaserScan.
* `configs/sensors/m2020_navcam.yaml` — M2020 Perseverance Navcam (RSM, LEFT)
  RGB-D camera, calibrated against Maki et al. 2020 Tables 2 + 3.
* `configs/sensors/m2020_hazcam.yaml` — M2020 Perseverance Hazcam
  (FRONT-LEFT) wide-FOV RGB-D camera.

To use the M2020 Navcam preset for a scenario's RGB-D camera, copy the
file body into the `rover.sensors.camera` block:

```yaml
rover:
  sensors:
    camera:
      parent_link: "Body_Chassis"
      local_translation: [0.3, -0.21, 0.0]
      local_orientation_rpy_deg: [180.0, 0.0, 0.0]
      resolution: [1280, 960]
      focal_length: 19.1
      clipping_range: [0.5, 1000.0]
```

### 4.2 What `configs/robots/rover_m2020.yaml` carries

The rover base config carries:

* USD path + URDF source path (offline conversion target).
* Chassis (mass, inertia tensor, bbox LWH).
* Wheels (radius, mass, friction, restitution, inertia tensor).
* Suspension (rocker / bogie damping).
* Control (drive geometry, max linear / angular velocity, drive joint
  names, cmd_vel timeout).
* Sensors (camera, lidar_3d, lidar_2d, imu — see §4.1).
* ROS2 topic names + publish rates (cmd_vel, /odom, /imu, /rgb,
  /depth, /lidar/points, /scan).

Full file is documented inline; do not duplicate per-scenario tweaks
into this file — put them in the scenario YAML instead.

---

## 5. `scene` block

Defined in `marslab/config/schema/scene.py` (`SceneConfig`,
`StructureConfigSchema`, `StructureAssetConfig`).  The block lets a
scenario dress static structures on top of the terrain — landers, habitat
modules, solar arrays, drop-in OBJ rocks, etc.  Two parallel sub-lists:

| Sub-list             | Asset format       | Loader                                          |
|----------------------|--------------------|-------------------------------------------------|
| `structures:`        | `.usd` / `.usda` / `.usdc` | `marslab.scene.structure_loader.load_structures` |
| `structure_assets:`  | `.obj` / `.stl`            | runtime conversion via `omni.kit.asset_converter` |

The `structure_assets:` list is the v1.0 sprint Day-2 (Task H) addition
for drop-in art — every scenario inherits an empty list from
`_base.yaml` and overrides only the entries it actually wants.

```yaml
# configs/scenarios/jezero_flat.yaml — single drop-in OBJ smoke
scene:
  structure_assets:
    - path: "tests/fixtures/sample_rock.obj"
      position: [10.0, 5.0, 0.0]
      rotation_rpy_deg: [0.0, 0.0, 45.0]
      scale: 1.0
      name: "boulder_01"
```

USD-based structures use `structures:` with a richer schema (per-axis
scale, static/collision toggles, named prim_path override) — see
`marslab/config/schema/scene.py` for the full field list.

---

## 6. `ros2_bridge` block

Defined in `marslab/config/schema/ros2_bridge.py` (`Ros2BridgeConfig`).
Top-level toggle for spawning the ROS2 publisher / subscriber graph:
when `enabled: false` the rover physics still tick but nothing publishes
on /cmd_vel, /odom, /imu, etc.  The default in `_base.yaml` is
`enabled: false` so unit tests and offline visualisation runs do not
require a ROS2 daemon.

---

## 7. Seed reproducibility

Every randomised process — rock placement, procedural elevation noise,
domain randomisation, dust tau profile — accepts a `seed` parameter that
flows from `mars_env.seed` (or a per-block `seed` override like
`terrain.seed`).  The same seed always produces the same output for a
given module + version.  This is enforced by
`tests/unit/test_seed_determinism.py` and by the per-module unit tests
under `tests/unit/`.

If you change `terrain.seed` the rock layout and (for cave / canyon
preset) the skylight / corridor positions move; if you depend on a
specific spawn pose remember to recompute the rover spawn xy alongside
the seed change.  See the comment in
`configs/scenarios/cave_lava_tube.yaml:62-70` for a worked example of
this dependency.

---

## 8. End-to-end walkthrough — adding a custom scenario

Suppose you want to add a "Jezero delta" scenario: a HiRISE crop on the
edge of the Jezero delta with a higher rock density and the rover
spawned 5 m east of the DEM centre.

**Step 1.** Identify the DEM crop region.  Run
`scripts/analyze_dem_regions.py` against the converted Jezero DEM and
note a row / col / height / width window with the slope characteristics
you want.

**Step 2.** Create `configs/scenarios/jezero_delta.yaml`:

```yaml
base_config: _base.yaml

mars_env:
  dynamic_atmosphere:
    enabled: true

terrain:
  source: "hirise"
  scenario_name: "jezero_delta"
  converted_dem_dir: "assets/terrain/dem/jezero_crater_converted"
  dem_crop:
    row: 240
    col: 64
    height: 200
    width: 200
  rock_sfd_k: 0.05                # higher density than jezero_flat (0)
  rock_diameter_range: [0.20, 3.0]
  semantic_classes: ["soil", "bedrock", "sand", "big_rock"]
  texture_dir: "assets/materials/mars_hirise"
  rock_color: [0.42, 0.28, 0.20]
  rock_roughness: 0.92
  rock_mesh_dir: "assets/rocks"
  rock_texture_dir: "assets/materials/mars_rock"
  uv_scale: 1.0
  seed: 42

rover:
  enabled: true
  base_config: "configs/robots/rover_m2020.yaml"
  spawn:
    mode: "dem_center"
    xy: [5.0, 0.0]                # 5 m east of DEM centre
    z_offset: 0.5
    orientation_rpy: [3.14159, 0.0, 0.0]
```

**Step 3.** Validate offline:

```bash
python3 -c "
from marslab.config.loader import load_and_validate
cfg = load_and_validate('configs/scenarios/jezero_delta.yaml')
print('terrain source:', cfg.terrain.source)
print('rock sfd k:', cfg.terrain.rock_sfd_k)
print('rover spawn xy:', cfg.rover.spawn['xy'])
"
```

This exercises the full root-level + rover-level `base_config:` merge
without touching Isaac Sim.

**Step 4.** (Optional) Dressing.  Add a `scene.structure_assets:` list
to drop in OBJ rocks beyond the procedural placer.

**Step 5.** Run the scenario in Isaac Sim:

```bash
PYTHONPATH=/path/to/MarsLab ~/isaacsim/python.sh \
    scripts/phase1/run_stage3_monolithic.py \
    --config configs/scenarios/jezero_delta.yaml
```

(If you are still iterating on the YAML, the offline visualisation
script `scripts/visualize_scenario.py` plots the DEM crop + rock
placement without launching Isaac Sim.)

---

## 9. Schema location reference

Every YAML key validates against a pydantic model under
`marslab/config/schema/`.  The split is:

* `mars_env.py` — `MarsEnvConfig`, `DynamicAtmosphereConfig`,
  `SunSweepConfig`, `TauConstantConfig`, `TauRampConfig`, `TauSineConfig`.
* `rendering.py` — `RenderingConfig`, `SkyDomeConfig`, `FogConfig`,
  `RayTracingConfig`, `PathTracingConfig`.
* `terrain.py` — `TerrainConfig`, `DemCropConfig`,
  `ProceduralCanyonConfig`, `CaveConfig`, `CaveGeometryConfig`.
* `robot.py` — `RobotConfig`, `ChassisConfig`, `WheelsConfig`,
  `SuspensionConfig`, `SkidSteerDriveConfig`, `SensorsConfig`,
  `CameraConfig`, `Lidar3DConfig`, `Lidar2DConfig`, `IMUConfig`,
  `OdometryCovarianceConfig`, `OdomPublisherConfig`.
* `scene.py` — `SceneConfig`, `StructureConfigSchema`,
  `StructureAssetConfig`.
* `ros2_bridge.py` — `Ros2BridgeConfig`.
* `root.py` — `MarsLabConfig` (aggregate).

All models declare `model_config = ConfigDict(extra="forbid")` so a
typo (`focal_lenght`, `rage_min`) fails validation at YAML load time
instead of being silently dropped to a default — this is the Reviewer 2
#12 (2026-04-24) fix that closed the schema-bypass class of bugs.

---

## 10. v1.0 scope statement (rover count)

v1.0 ships a **single M2020 Perseverance rover** per scenario.  Every
reference scenario in `configs/scenarios/` declares one `rover:` block.
Multi-rover coordination — running two M2020 rovers, or one rover plus
one quadruped, in the same scene — is deferred to **v1.5** (post-iSpaRo
2026).  The current `RobotConfig.prim_path` already supports per-instance
prim paths so the schema is multi-rover-ready; only the orchestration
runtime (sensor namespacing, TF tree composition, two articulated drive
loops) remains to be wired.

If you need a multi-rover smoke before v1.5, copy the rover block,
suffix the prim path (`/World/Rover_0`, `/World/Rover_1`), and run the
scenario manually — but expect TF / topic collisions until the v1.5
namespacing work lands.

---

## 11. Where to look next

* **`configs/scenarios/_base.yaml`** — full default values for every
  field touched by `_base.yaml`.
* **`configs/scenarios/jezero_flat.yaml`** — shortest scenario, good
  starting template.
* **`configs/scenarios/cave_lava_tube.yaml`** — most complex scenario
  (procedural cave + per-scenario sensor override).
* **`configs/robots/rover_m2020.yaml`** — full rover base config with
  M2020 ballpark physics + sensor stack.
* **`marslab/config/loader.py`** — `load_and_validate` entry point.
* **`marslab/config/yaml_loader.py`** — `base_config:` resolution +
  `deep_merge` semantics.
* **`tests/unit/test_config_schema.py`** + per-block siblings —
  validation behaviour, including `extra="forbid"` regression tests.
