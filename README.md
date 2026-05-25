# MarsLab

**Standardized Mars simulation platform for SLAM, autonomous navigation, and
field-robotics research, built on NVIDIA Isaac Sim 5.x.**

MarsLab gives planetary-robotics researchers a single, scriptable, ROS2-native
testbed for repeatable Mars experiments. The runtime consumes a pre-built
external USDA terrain (any HiRISE-derived USD scene authored upstream in
[`MarsLab-Utils`](https://github.com/kimhoyun-robotair/MarsLab-Utils)) plus a
single `configs/default.yaml` describing the Mars atmosphere + lighting, then
spawns the M2020 Perseverance rover with a full ROS2 bridge on top.

* **Reproducible by design** — every randomized process accepts a `seed`; one
  YAML + one `--usda` path = identical output every run.
* **External terrain authoring** — terrain meshes (HiRISE / procedural / cave
  / habitat) are baked into USDA upstream by MarsLab-Utils. MarsLab only
  consumes them, so terrain authoring code (DEM loader, procedural generator,
  rock placer, cave builder, structure loader) no longer lives in this repo.
* **ROS2 Jazzy native** — `cmd_vel`, odometry, IMU, RGB, depth, RGB-D point
  cloud, 3D + 2D LiDAR, full TF tree.
* **Pydantic-validated** — every YAML field is type-checked at load time;
  typos fail loudly before Isaac Sim boots.
* **CLI overrides for experiment variants** — change sun position via
  `--sun-azimuth-deg`/`--sun-elevation-deg`; toggle headless / no-ROS2 /
  no-atmosphere with their respective flags. No YAML edit needed for
  per-experiment tweaks.

**Target paper:** iSpaRo 2026 (regular paper, deadline 2026-06-15).
**License:** Apache 2.0.

---

## 1. Quick Start

```bash
# 1. Clone (with submodules — pulls the M2020 URDF + meshes fork)
git clone --recurse-submodules https://github.com/kimhoyun-robotair/MarsLab.git
cd MarsLab
# (If you already cloned without --recurse-submodules:
#   git submodule update --init)

# 2. Install Python deps (Isaac Sim 5.x must already be installed locally)
pip install -e ".[dev]" --break-system-packages

# 3. Build a USDA terrain upstream (one-time, in MarsLab-Utils repo):
#    See https://github.com/kimhoyun-robotair/MarsLab-Utils — HiRISEGen,
#    CraterComposer, RockyComposer, etc. produce USDA scene files.
#    Example output: ~/MarsLab-Utils/HiRISEGen/out/jezero_enhanced/terrain_scene.usda

# 4. Convert the M2020 URDF -> USD once (no GPU rover spawn until this exists):
marslab/isaac_python.sh marslab/fix_urdf_inertia.py        # idempotent mass+inertia rewrite
marslab/isaac_python.sh marslab/convert_urdf_to_usd.py     # URDF -> assets/robots/rover/m2020.usd

# 5. Run the sim.  Single line:
marslab/isaac_python.sh marslab/main.py \
    --usda ~/MarsLab-Utils/HiRISEGen/out/jezero_enhanced/terrain_scene.usda
```

Companion terminal (required for full TF):

```bash
source /opt/ros/jazzy/setup.bash
ros2 launch ~/MarsLab/launch/rover_state_publisher.launch.py
```

Drive it (third terminal):

```bash
source /opt/ros/jazzy/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
    --ros-args -r __ns:=/rover
```

Watch it in RViz: `rviz2`, then add the topics under `/rover/*`.

---

## 2. All CLI Arguments

`marslab/main.py` is the only runtime entry point. Every experiment variant is
expressed as a CLI flag combination on top of the single `configs/default.yaml`.

| Flag | Type | Default | Description |
|---|---|---|---|
| `--usda PATH` | str | (required) | Path to the pre-built USDA terrain (HiRISE / procedural / cave). Built upstream in MarsLab-Utils. |
| `--scenario PATH` | str | `configs/default.yaml` | YAML supplying `mars_env` + `rendering` + `dynamic_atmosphere` blocks. Most users never override. |
| `--rover-yaml PATH` | str | `configs/rover_m2020.yaml` | Rover sensors + control + ROS2 config. |
| `--z-offset FLOAT` | float | `0.1` | Vertical clearance above the DEM-sampled surface at the USDA bbox centre (meters). |
| `--sun-azimuth-deg FLOAT` | float | `None` (use YAML) | Override `mars_env.sun_azimuth_deg` for this run only. |
| `--sun-elevation-deg FLOAT` | float | `None` (use YAML) | Override `mars_env.sun_elevation_deg` for this run only. |
| `--headless` | flag | off | Boot Isaac Sim without the GUI viewport (CI, batch experiments). |
| `--no-ros2` | flag | off | Skip the rclpy bridge entirely (sensor topics never publish). Useful for rover physics smoke tests. |
| `--no-atmosphere` | flag | off | Skip the dynamic sun + sky dome + fog stack. A fallback `DistantLight` is added so the camera is not black. |

### 2a. Reference invocations

```bash
# Default — overhead sun, dynamic atmosphere, ROS2 on, viewport visible.
marslab/isaac_python.sh marslab/main.py \
    --usda ~/MarsLab-Utils/HiRISEGen/out/jezero_enhanced/terrain_scene.usda

# Morning sun experiment (formerly the "spacecraft_landing" preset).
marslab/isaac_python.sh marslab/main.py \
    --usda ~/MarsLab-Utils/HiRISEGen/out/jezero_enhanced/terrain_scene.usda \
    --sun-azimuth-deg 135 \
    --sun-elevation-deg 40

# Headless CI run (no viewport, full sim runs in the background).
marslab/isaac_python.sh marslab/main.py \
    --usda ~/MarsLab-Utils/HiRISEGen/out/cerberus_canyon/terrain_scene.usda \
    --headless

# No ROS2 (rover physics only, no topics published).
marslab/isaac_python.sh marslab/main.py \
    --usda ~/MarsLab-Utils/HiRISEGen/out/jezero_enhanced/terrain_scene.usda \
    --no-ros2

# No atmosphere stack (debug viewport jitter or pure terrain+rover validation).
marslab/isaac_python.sh marslab/main.py \
    --usda ~/MarsLab-Utils/HiRISEGen/out/jezero_enhanced/terrain_scene.usda \
    --no-atmosphere

# Custom z-offset (rover spawn 0.8 m above DEM centre — for bouldery terrain).
marslab/isaac_python.sh marslab/main.py \
    --usda ~/MarsLab-Utils/HiRISEGen/out/cerberus_canyon/terrain_scene.usda \
    --z-offset 0.8

# Custom scenario YAML (e.g. dust-storm preset with tau=2.5).
marslab/isaac_python.sh marslab/main.py \
    --usda ~/MarsLab-Utils/HiRISEGen/out/jezero_enhanced/terrain_scene.usda \
    --scenario configs/dust_storm.yaml

# Custom rover config (e.g. alternate sensor layout).
marslab/isaac_python.sh marslab/main.py \
    --usda ~/MarsLab-Utils/HiRISEGen/out/jezero_enhanced/terrain_scene.usda \
    --rover-yaml configs/rover_m2020_lidar_only.yaml

# Composite — morning sun + headless + custom z-offset.
marslab/isaac_python.sh marslab/main.py \
    --usda ~/MarsLab-Utils/HiRISEGen/out/jezero_enhanced/terrain_scene.usda \
    --sun-azimuth-deg 135 \
    --sun-elevation-deg 40 \
    --headless \
    --z-offset 0.6
```

### 2b. Log output

```bash
# Pipe to a log file for later inspection.
marslab/isaac_python.sh marslab/main.py \
    --usda ~/MarsLab-Utils/HiRISEGen/out/jezero_enhanced/terrain_scene.usda \
    2>&1 | tee ~/MarsLab/tmp/run.log
```

### 2c. ROS2 verification (third terminal)

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic list                                       # all /rover/* topics live?
ros2 topic echo /rover/odom --once                    # rover pose stream
ros2 topic echo /tf --once                            # full TF tree
ros2 topic pub --once /rover/cmd_vel geometry_msgs/Twist \
    '{linear: {x: 0.5}, angular: {z: 0.0}}'           # drive forward at 0.5 m/s
```

---

## 3. USDA Requirements

Any USDA passed via `--usda` must satisfy:

* `upAxis = "Z"`, `metersPerUnit = 1`.
* At least one visible `UsdGeom.Mesh` under the default prim (used for DEM
  surface sampling).
* `UsdPhysics.CollisionAPI` on at least one mesh so the rover wheels have
  contact geometry.

### Rover spawn modes

Spawn position is resolved by `marslab.main._resolve_spawn` from the
`spawn:` block in `configs/rover_m2020.yaml`. Four modes are supported:

| `spawn.mode` | XY resolution | Use case |
|---|---|---|
| `dem_center` *(default)* | DEM bbox centre | Legacy behaviour |
| `dem_relative` | `dem_center + xy` | Spawn at a fixed offset from DEM centre |
| `absolute` | `xy` in world frame | Multi-rover scenes or non-centred terrains |
| `trajectory_start` | First sample of `spawn.trajectory_path` (a TUM file) | Run a reference trajectory from its own start point |

`surface_z` is sampled from the DEM mesh at the resolved XY (median of mesh
points within a small radius). Final Z = `surface_z + spawn.z_offset` (YAML
`spawn.z_offset` overrides the CLI `--z-offset` flag if both are set).

`spawn.orientation_rpy` controls the spawn yaw, except in
`trajectory_start` mode where `spawn.use_yaw_from_trajectory: true`
(default) overrides yaw with `2·atan2(qz, qw)` from the TUM first sample.

#### Example — spawn rover at the start of a TrajectoryComposer TUM

```yaml
# configs/rover_m2020.yaml
spawn:
  mode: "trajectory_start"
  trajectory_path: "../MarsLab-Utils/TrajectoryComposer/out/jezero_rocky_loop/trajectory.tum"
  z_offset: 0.1
  use_yaw_from_trajectory: true
```

The rover will spawn at the trajectory's first `(tx, ty)` with its yaw
aligned to the trajectory's first sample, ready for direct ATE evaluation
against the reference TUM.

Any nested `PhysicsScene` inside the USDA is auto-deactivated so the
Mars-gravity `/physicsScene` created by `marslab.sim.world_setup.create_world`
remains the sole active physics scene.

---

## 4. ROS2 Topics

Default rover namespace is `/rover/` (override via `rover.ros2.namespace` in
`configs/rover_m2020.yaml`).

### Subscribed (input)

| Topic | Type | QoS preset | Schema field |
|---|---|---|---|
| `/rover/cmd_vel` | `geometry_msgs/Twist` | RELIABLE/depth=10 | `Ros2BridgeConfig.cmd_vel_qos` |

### Published (output)

| Topic | Type | QoS preset | Schema field |
|---|---|---|---|
| `/rover/odom` | `nav_msgs/Odometry` | RELIABLE/depth=10 | `Ros2BridgeConfig.odom_qos` |
| `/rover/imu` | `sensor_msgs/Imu` | BEST_EFFORT/depth=5 | `Ros2BridgeConfig.sensor_qos` |
| `/rover/rgb/image_raw` + `/rover/rgb/camera_info` | `sensor_msgs/Image`, `CameraInfo` | BEST_EFFORT/depth=5 | `Ros2BridgeConfig.sensor_qos` |
| `/rover/depth/image_raw` + `/rover/depth/points` | `sensor_msgs/Image`, `PointCloud2` | BEST_EFFORT/depth=5 | `Ros2BridgeConfig.sensor_qos` |
| `/rover/lidar/points` | `sensor_msgs/PointCloud2` | BEST_EFFORT/depth=5 | `Ros2BridgeConfig.sensor_qos` |
| `/rover/scan` | `sensor_msgs/LaserScan` | BEST_EFFORT/depth=5 | `Ros2BridgeConfig.sensor_qos` |
| `/clock` | `rosgraph_msgs/Clock` | (Isaac Sim default) | OmniGraph node |
| `/rover/joint_states` | `sensor_msgs/JointState` | RELIABLE + TRANSIENT_LOCAL/100 | `Ros2BridgeConfig.tf_qos` |
| `/tf` + `/tf_static` + `/robot_description` | std | RELIABLE + TRANSIENT_LOCAL/100 | `Ros2BridgeConfig.tf_qos` |

### TF authority

MarsLab uses the **ROS-standard `robot_state_publisher` pattern**:

* **Isaac Sim** publishes `sensor_msgs/JointState` on `/rover/joint_states`
  every tick + static sensor offsets on `/tf_static`.
* **rclpy** publishes `odom -> Body_Chassis` on `/tf` from PhysX
  ground-truth pose.
* **ROS** runs `robot_state_publisher` (the bundled launch file) consuming
  `/rover/joint_states` + the latched `/rover/robot_description` URDF and
  emits the full chassis link-tree TF (`Body_Chassis -> Body_Wheel*`, etc.)
  on `/tf`.

Launch the companion `robot_state_publisher` (separate terminal):

```bash
ros2 launch ~/MarsLab/launch/rover_state_publisher.launch.py
```

Override URDF path / namespace via launch args:

```bash
ros2 launch ~/MarsLab/launch/rover_state_publisher.launch.py \
    urdf_path:=/path/to/m2020.urdf namespace:=rover2
```

### RViz Fixed Frame guidance

| Fixed Frame | Use case |
|---|---|
| `odom` (default) | Local ground-truth viewing, planning |
| `map` | RTAB-Map global localisation |
| `base_link` | Sensor mount + TF chain debugging |
| `Body_Chassis` | Raw URDF link inspection |

Since the rc1b URDF rewrite (2026-05-04) the JPL m2020 URDF link frames are
REP-103 aligned (+X forward, +Y left, +Z up) end-to-end. The rover prim
spawns with identity orientation; no X-roll compensation anywhere.

### Note on color RGB-D point clouds

`/rover/depth/points` carries **XYZ + intensity**, not XYZRGB. To get an
XYZRGB stream, run the standard ROS2 fusion node externally:

```bash
ros2 run depth_image_proc point_cloud_xyzrgb_node \
    --ros-args \
    -r rgb/image_rect_color:=/rover/rgb/image_raw \
    -r rgb/camera_info:=/rover/rgb/camera_info \
    -r depth_registered/image_rect:=/rover/depth/image_raw \
    -r points:=/rover/depth/points_xyzrgb
```

See `docs/colored_pointcloud.md` for the full pattern.

---

## 5. 3D LiDAR Odometry (kinematic-icp / RTAB-Map)

3D LiDAR-based odometry has been validated against two open-source stacks.
Each stack interprets the relationship between PointCloud data axis and
`frame_id` differently, so `configs/rover_m2020.yaml`'s
`sensors.lidar_3d.local_orientation_rpy_deg` must be flipped per stack.

**Common prerequisite**: the main sim + the
`robot_state_publisher` launch file from Section 1 must be running.

### kinematic-icp (KISS-ICP)

YAML setting in `configs/rover_m2020.yaml`:
```yaml
sensors:
  lidar_3d:
    local_orientation_rpy_deg: [0.0, 0.0, 0.0]
```

Launch:
```bash
ros2 launch kinematic_icp online_node.launch.py \
    lidar_topic:=/rover/lidar/points \
    base_frame:=base_link \
    use_sim_time:=True \
    use_2d_lidar:=false \
    tf_timeout:=0.5 \
    visualize:=true
```

#### Partial-scan caveat (LiDAR rotation ≪ sim tick rate)

Isaac Sim's `ROS2RtxLidarHelper` defaults to `inputs:fullScan = False`,
meaning each simulation tick publishes only the angular slice that the
LiDAR rotated through since the previous tick. When
`lidar_3d.rotation_rate_hz` is close to the sim tick rate (e.g. the
bundled `Example_Rotary` profile at 30 Hz on a 30 Hz tick) the slice
covers nearly a full revolution and registrators stay happy, but vendor
profiles with realistic rotation (e.g. Ouster `OS1` at 10 Hz) emit
~36° slices that destabilise kiss-icp / kinematic-icp adaptive
thresholds and crash the node.

Two workarounds are supported:

1. **YAML-only (recommended for quick experiments)** — raise
   `lidar_3d.rotation_rate_hz` to match the sim tick rate. This is the
   default for `configs/rover_m2020.yaml`:
   ```yaml
   sensors:
     lidar_3d:
       rotation_rate_hz: 30   # 10 → 30 to mirror the sim tick rate
   ```
   The trade-off is physical fidelity: Ouster `OS1` actually rotates
   at 10 / 20 Hz, so scan-time effects (motion compensation, deskew)
   no longer reflect the real sensor.

2. **OmniGraph helper flag (physically correct, requires code edit)** —
   enable accumulation inside `ROS2RtxLidarHelper` so a full revolution
   is published per message regardless of rotation rate. The line lives
   in `marslab/ros2_bridge/sensor_graph_builder.py` next to the other
   `Lidar3DHelper.inputs:*` keys; the inline NOTE there records the
   exact snippet:
   ```python
   ("Lidar3DHelper.inputs:fullScan", True),
   ```
   Use this when you keep the realistic `rotation_rate_hz` and want
   kiss-icp / RTAB-Map to consume a full 360° (or YAML-cropped FOV)
   per frame. Publish rate then drops to the LiDAR rotation rate.

### RTAB-Map (3D LiDAR mode)

YAML setting:
```yaml
sensors:
  lidar_3d:
    local_orientation_rpy_deg: [180.0, 0.0, 0.0]
```

The exact reason the two stacks demand different `lidar_link` axes is
tracked in `work_log/Version1.5.md` (alongside the proper fix: extending
`marslab/sensors/sensor_spawner.py` to apply `AddOrientOp` on the LiDAR prim
itself).

---

## 6. Architecture

Three principles govern every structural decision:

* **P1 — Flat.** No premature abstraction. No plugin systems, no god
  objects, no registration mechanisms.
* **P2 — Unidirectional data flow.** Config → pure-Python compute → Isaac
  Sim scene → native sim loop. No circular imports.
* **P3 — Offline-first testing.** Every pure-compute module (Beer's law,
  COMIMART, sun position, config validation) runs in CI without Isaac Sim
  or a GPU.

### Module map (post v1.0 cleanup)

| Module | Responsibility | Isaac Sim required? |
|---|---|---|
| `marslab/config/` | YAML load, pydantic validation, seed propagation | No |
| `marslab/environment/` | Mars physics: sun position, Beer's law, COMIMART, sky | No |
| `marslab/rendering/` | Sky dome, sun light, atmosphere fog, render mode | Yes |
| `marslab/robots/` | URDF→USD spawn, articulation, drive API | Yes |
| `marslab/sensors/` | Camera, LiDAR, IMU attachment + config | Yes |
| `marslab/ros2_bridge/` | rclpy + OmniGraph publishers / subscribers | Yes |
| `marslab/runtime/` | Boot orchestration (`atmosphere_boot`) + main loop | Yes |
| `marslab/sim/` | Kit boot, world + physics scene setup | Yes |
| `marslab/gui/` | Atmosphere panel + interactive controls | Yes |
| `marslab/main.py` | Production CLI entry point | Yes |
| `marslab/convert_urdf_to_usd.py` | One-shot URDF→USD converter | Yes (Kit) |
| `marslab/fix_urdf_inertia.py` | URDF mass + inertia inject (idempotent) | No |
| `marslab/quaternion.py` | Pure quaternion utilities | No |

Removed in v1.0 (moved to `delete_later/`): `marslab/terrain/`,
`marslab/scene/`, `marslab/runtime/stage2_boot.py`,
`marslab/runtime/stage2_scene.py`, `marslab/config/scenario_loader.py`,
`marslab/config/spawn_resolver.py`, `marslab/runtime/config_loader.py`.
Terrain authoring + scene composition are now upstream in MarsLab-Utils;
runtime only consumes the resulting USDA.

The full guideline catalogue (G1-G10 and OP-1 through OP-5) lives in
`CLAUDE.md`.

---

## 7. Citation, License, Roadmap

### License

Apache 2.0 — see `LICENSE`. All MarsLab source code is original. We study
OmniLRS, RLRoverLab, SRB, and `unitree_sim_isaaclab` for algorithmic and
pattern inspiration but do not copy code or naming.

### Third-Party Assets

The Perseverance (M2020) rover URDF and glTF meshes are vendored as a git
submodule under `assets/m2020-urdf-models/` (a fork of
`github.com/nasa-jpl/m2020-urdf-models`, NASA/JPL release IDs URS307049 and
URS309682). See `THIRD_PARTY_LICENSES.md` for the full attribution.

### Citation

```bibtex
@inproceedings{kim2026marslab,
  title     = {MarsLab: A Standardized Mars Simulation Platform for Field
               Robotics},
  author    = {Kim, Hoyun and ...},
  booktitle = {Proceedings of the International Symposium on Space Robotics
               (iSpaRo)},
  year      = {2026},
  note      = {Paper not yet accepted; placeholder citation.}
}
```

### Roadmap

* **v1.0 (current, iSpaRo 2026 submission):** single-rover M2020, ROS2
  bridge, SLAM, dynamic atmosphere. USDA terrain consumed from upstream
  MarsLab-Utils.
* **v1.5 (post-iSpaRo, engineering follow-ons):**
    * GUI USDA loader.
    * Non-ROS2 dataset export (HDF5 / Parquet) for ML training.
    * Multi-rover coordination.
    * Fault injection (sensor dropout, wheel slip, IMU bias drift).
* **v2.0 (post-iSpaRo, photorealism):** Hapke BRDF on regolith, dust
  dynamics, 4K HDRI, anti-tiling, photogrammetry rocks.
* **v3.0 (future):** Bekker / Janosi terramechanics, RL environments
  (Isaac Lab Gym API), Ls-parameterized seasonal variation.

---

## Requirements

* **NVIDIA Isaac Sim 5.x** (standalone install)
* **Python 3.12+**
* **ROS2 Jazzy** (for the runtime bridge; not needed for unit tests)
* **GPU:** NVIDIA RTX series (tested on RTX 5070 Ti)
* **OS:** Ubuntu 22.04+

Python dependencies pin in `pyproject.toml` (`pydantic>=2.0`, `pyyaml>=6.0`,
`numpy>=1.24`, `scipy>=1.10`).

---

## Running the Test Suite

Unit tests run on CPU, no Isaac Sim required:

```bash
pytest tests/unit/ -q
black --check marslab/ tests/
ruff check marslab/ tests/
```

Isaac Sim runtime verification is performed by launching the full
simulation against a USDA + the default scenario YAML and confirming spawn
/ cmd_vel / sensor topics in RViz:

```bash
marslab/isaac_python.sh marslab/main.py \
    --usda ~/MarsLab-Utils/HiRISEGen/out/jezero_enhanced/terrain_scene.usda
```

---

## Where to Read Next

* `docs/colored_pointcloud.md` — `depth_image_proc` XYZRGB fusion pattern.
* `docs/odometry_ground_truth.md` — odom publisher + RTAB-Map handoff.
* `CLAUDE.md` (English) / `CLAUDE_kor.md` (Korean) — developer-side
  guidelines, principles, and the sprint plan toward iSpaRo 2026.
* `work_log/LOG.md` — append-only development history.
