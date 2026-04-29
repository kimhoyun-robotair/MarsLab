# MarsLab

**Standardized Mars simulation platform for SLAM, autonomous navigation, and
field-robotics research, built on NVIDIA Isaac Sim 5.x.**

MarsLab gives planetary-robotics researchers a single, scriptable, ROS2-native
testbed for repeatable Mars experiments. Nine reference scenarios — from a
flat Jezero plain to a 200 m wide lava tube — ship as YAML configs that load
the same M2020 Perseverance rover and the same Mars-calibrated atmosphere,
so a SLAM or Nav2 result on one scenario is directly comparable to results on
the others.

* **Reproducible by design** — every randomized process accepts a `seed`; one
  YAML, one seed, identical output every run.
* **Real and procedural terrain** — load HiRISE GeoTIFFs of Jezero / Cerberus
  Fossae or generate procedural terrain (`flat`, `crater`, `hills`,
  `rocky_plain`, `canyon`) with zero external assets.
* **ROS2 Jazzy native** — `cmd_vel`, odometry, IMU, RGB, depth, RGB-D point
  cloud, 3D + 2D LiDAR, full TF tree.
* **Drop-in `.obj` / `.stl` assets** — add a boulder, a lander, a habitat
  module by pointing one YAML field at a file path.
* **SLAM + Nav2 wired** — `slam_toolbox` and `nav2_bringup` configs ship in
  `configs/slam/` and `configs/nav2/`.
* **Pydantic-validated** — every YAML field is type-checked at load time;
  typos fail loudly before Isaac Sim boots.

**Target paper:** iSpaRo 2026 (regular paper, deadline 2026-06-16).
**License:** Apache 2.0.
**Korean readers:** dev-side guide is in `CLAUDE_kor.md`. End-user docs
(this README, `docs/scenario_format.md`, `docs/colored_pointcloud.md`) are
English-only by design.

---

## 1. Quick Start (60 seconds)

```bash
# 1. Clone (with submodules — pulls the M2020 URDF + meshes fork)
git clone --recurse-submodules https://github.com/kimhoyun-robotair/MarsLab.git
cd MarsLab
# (If you already cloned without --recurse-submodules:
#   git submodule update --init)

# 2. Install Python deps (Isaac Sim 5.x must already be installed locally)
sudo apt-get install -y libgdal-dev gdal-bin
pip install -e ".[dev]" --break-system-packages

# 3. Run a fully self-contained procedural scenario.
#    No external DEM, no external assets, no other YAMLs to read.
scripts/isaac_python.sh scripts/phase1/run_stage4.py \
    --config configs/scenarios/template_single_file.yaml
```

That's it. The simulator boots a 256 m × 256 m procedurally-generated rocky
plain with one M2020 rover, a butterscotch sky at τ=0.3, the full ROS2
bridge advertising `/rover/*`, and a sun sweep that animates over the
duration of a Sol.

Drive it (a second terminal):

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
    --ros-args -r __ns:=/rover
```

**Required** companion (a third terminal): `robot_state_publisher` reads
the latched `/rover/robot_description` URDF + the OmniGraph-published
`/rover/joint_states` and emits the full articulation TF chain on `/tf`.
Without it, `/joint_states` is the only TF-related topic alive and
RViz `RobotModel`, SLAM, and Nav2 all fail to resolve `Body_Wheel*` /
sensor frames.

```bash
ros2 launch ~/MarsLab/launch/rover_state_publisher.launch.py
```

Watch it in RViz:

```bash
ros2 launch slam_toolbox online_async_launch.py \
    params_file:=$(pwd)/configs/slam/slam_toolbox_async.yaml
rviz2  # add /rover/scan, /rover/depth/points, /rover/lidar/points, /map
```

---

## 2. Two Terrain Modes

MarsLab supports two complementary terrain pipelines. The choice is one
field in the scenario YAML.

### 2a. Procedural (zero external assets)

```yaml
# configs/scenarios/template_single_file.yaml
terrain:
  source: "procedural"
  procedural_preset: "rocky_plain"   # flat | crater | hills | rocky_plain | canyon
  terrain_size: [256, 256]           # rows, cols (px)
  terrain_resolution: 1.0            # m / px
  rock_sfd_k: 0.05                   # Golombek CFA (0.0–0.15)
  seed: 42                           # ← change this for a brand-new terrain
```

Five presets ship in v1.0 (canyon and cave require small extra blocks; see
`configs/scenarios/procedural_canyon.yaml` and
`configs/scenarios/cave_lava_tube.yaml`). The presets are pure-Python — no
GDAL, no GeoTIFF download — so they run on a machine that has only the base
MarsLab install.

**Reproducibility:** flip `seed: 42` to `seed: 12345` and re-run; the
terrain mesh, rock placement, and rover spawn relative to the new
elevation are entirely different but bit-exact reproducible the next time.

### 2b. HiRISE DEM (real Mars topography)

Two-step workflow. **Step 1 is offline preprocessing** (no Isaac Sim, no
GPU); step 2 is the same `run_stage4.py` invocation as the procedural
case.

```bash
# Step 1: convert a HiRISE GeoTIFF to numpy + metadata.
#         Uses GDAL on the host CPU. Output is written to
#         assets/mars_assets/DEM/<region>/{elevation.npy,metadata.json}.
scripts/isaac_python.sh scripts/convert_dem.py \
    --config configs/dem_conversion/sample_jezero.yaml

# Step 2: run the simulator with a scenario that points at the
#         processed DEM via terrain.dem_path.
scripts/isaac_python.sh scripts/phase1/run_stage4.py \
    --config configs/scenarios/template_hirise.yaml
```

`configs/dem_conversion/sample_jezero.yaml` ships with a Jezero crater
crop. To swap regions, edit the GeoTIFF source, the crop window
(`row_offset`, `col_offset`, `crop_size`), and the optional vertical
exaggeration in that one file.

---

## 3. Available Scenarios

Eight reference scenarios ship with v1.0:

| Scenario                  | Source                    | One-line description                                                  |
|---------------------------|---------------------------|-----------------------------------------------------------------------|
| `jezero_flat`             | HiRISE Jezero crater W    | dz=3 m, mean slope ≈2°. Baseline / SLAM regression.                  |
| `jezero_crater`           | HiRISE Jezero crater NE   | dz=12.6 m, max slope 30°. Slope-handling test.                       |
| `jezero_rocks`            | HiRISE Jezero (same crop) | Same DEM, dense Golombek rocks (CFA k=0.08). Obstacle field.         |
| `cerberus_canyon_easy`    | HiRISE Cerberus Fossae S  | 82% traversable. Approach-with-crater nav baseline.                   |
| `cerberus_canyon`         | HiRISE Cerberus Fossae    | 28% impassable, mean slope 25°. Path-planning stress test.           |
| `cave_lava_tube`          | Procedural (MARS-LT-B)    | 200 m wide lava tube, 1 skylight. GPS-denied SLAM.                   |
| `spacecraft_landing`      | HiRISE Jezero + structures| InSight-style lander + heat shield + parachute debris field.          |
| `procedural_canyon`       | Procedural                | Synthetic canyon corridor, 30 m floor, 40 m walls. Confined nav.      |

Plus three first-class **templates** — copy these to start a new scenario:

| Template                                          | Use it when …                                                  |
|---------------------------------------------------|-----------------------------------------------------------------|
| `configs/scenarios/template_single_file.yaml`     | You want a 240-line self-contained scenario, no `base_config:` includes (best for demos / academic reproducibility). |
| `configs/scenarios/template_hirise.yaml`          | You're authoring a new HiRISE DEM scenario and want to follow the standard 2-step pipeline. |
| `configs/dem_conversion/sample_jezero.yaml`       | You're writing the DEM-to-numpy preprocessing config for step 1. |

Paper figures for each scenario will be regenerated post-paper via
`scripts/visualize_scenario.py` and friends; they are not committed to this
repo.

---

## 4. ROS2 Topics

Default rover namespace is `/rover/` (override via
`rover.ros2.namespace` in the scenario YAML).

### Subscribed (input)

| Topic                       | Type                       | QoS preset       | Schema field                       |
|-----------------------------|----------------------------|------------------|------------------------------------|
| `/rover/cmd_vel`            | `geometry_msgs/Twist`      | RELIABLE/depth=10| `Ros2BridgeConfig.cmd_vel_qos`     |

### Published (output)

| Topic                          | Type                          | QoS preset                  | Schema field                       |
|--------------------------------|-------------------------------|------------------------------|------------------------------------|
| `/rover/odom`                  | `nav_msgs/Odometry`           | RELIABLE/depth=10            | `Ros2BridgeConfig.odom_qos`        |
| `/rover/imu`                   | `sensor_msgs/Imu`             | BEST_EFFORT/depth=5          | `Ros2BridgeConfig.sensor_qos`      |
| `/rover/rgb/image_raw`         | `sensor_msgs/Image`           | BEST_EFFORT/depth=5          | `Ros2BridgeConfig.sensor_qos`      |
| `/rover/depth/image_raw`       | `sensor_msgs/Image`           | BEST_EFFORT/depth=5          | `Ros2BridgeConfig.sensor_qos`      |
| `/rover/depth/points`          | `sensor_msgs/PointCloud2`     | BEST_EFFORT/depth=5          | `Ros2BridgeConfig.sensor_qos`      |
| `/rover/lidar/points`          | `sensor_msgs/PointCloud2`     | BEST_EFFORT/depth=5          | `Ros2BridgeConfig.sensor_qos`      |
| `/rover/scan`                  | `sensor_msgs/LaserScan`       | BEST_EFFORT/depth=5          | `Ros2BridgeConfig.sensor_qos`      |
| `/clock`                       | `rosgraph_msgs/Clock`         | (Isaac Sim default)          | OmniGraph node                     |
| `/rover/joint_states`          | `sensor_msgs/JointState`      | RELIABLE + TRANSIENT_LOCAL/100 | `Ros2BridgeConfig.tf_qos`        |
| `/tf`                          | `tf2_msgs/TFMessage`          | RELIABLE + TRANSIENT_LOCAL/100 | `Ros2BridgeConfig.tf_qos`        |
| `/tf_static`                   | `tf2_msgs/TFMessage`          | RELIABLE + TRANSIENT_LOCAL/100 | `Ros2BridgeConfig.tf_qos`        |

`/rover/depth/points` carries `frame_id: camera_optical_frame` (REP-103
optical convention). `/rover/lidar/points` and `/rover/scan` use
`<sensor_parent_frame_id>`-style sensor frames published on
`/tf_static` at boot.

### TF authority

MarsLab uses the **ROS-standard `robot_state_publisher` pattern**
(default since C2):

* **Isaac Sim** publishes `sensor_msgs/JointState` on `/rover/joint_states`
  every tick.
* **ROS** runs `robot_state_publisher` consuming `/joint_states` + the
  latched `/rover/robot_description` (URDF) and emits the full link
  tree TF (`Body_Chassis → Body_Wheel*`, etc.) on `/tf`.
* **rclpy** publishes static sensor offsets on `/tf_static` and -- when
  `publish_odom_tf=True` -- `odom → Body_Chassis` on `/tf`.

Single TF authority -- no `topic_tools relay` required.  Launch the
companion `robot_state_publisher` with the bundled launch file:

```bash
ros2 launch ~/MarsLab/launch/rover_state_publisher.launch.py
```

The launch file reads
`assets/m2020-urdf-models/rover/m2020.urdf`, rewrites the relative
mesh paths to absolute `file://` URIs, and feeds the URDF as the
`robot_description` **parameter** on the `robot_state_publisher`
node (NOT a topic remap -- `robot_description` is a ROS parameter,
even though late-joining tools like RViz also accept the URDF on a
latched topic of the same name).  Override the URDF path or the
namespace via launch args:

```bash
ros2 launch ~/MarsLab/launch/rover_state_publisher.launch.py \
    urdf_path:=/path/to/m2020.urdf namespace:=rover2
```

SLAM/Nav2 launch parameters accept any `base_frame` -- pin to
`base_link` (REP-103) or to the URDF root link name (`Body_Chassis`)
depending on the upstream stack.

**`odom -> base_link` authority** (Phase 2, 2026-04-29 default):
`marslab.ros2_bridge.odometry_publisher` broadcasts the rover's
PhysX-derived ground-truth pose on `/tf` so external visual SLAM
(RTAB-Map `rgbd_odometry`, ORB-SLAM3, ...) is no longer required for
the odom transform.  `init_quat_world` is pinned to identity in
`scripts/phase1/main.py` so the published `odom` frame equals the
world REP-103 frame.  Set `ros2.publish_odom_tf: false` in the
rover YAML to delegate the transform back to a visual SLAM stack;
never run both -- two publishers on the same transform produce
jitter that breaks downstream consumers.

### RViz Fixed Frame guidance

Pick the Fixed Frame based on what you are debugging:

| Fixed Frame | Use case | Rover orientation |
|---|---|---|
| `odom` (default) | `marslab.ros2_bridge.odometry_publisher` ground-truth, Nav2 local planning | Correct (chassis up, wheels down) |
| `map` | RTAB-Map / slam_toolbox global localisation | Correct |
| `base_link` | Frame chain debugging (sensor mounts, wrapper transform) | Inverted (graphics-style URDF link frame) |
| `Body_Chassis` | Raw URDF link inspection | Inverted |

The JPL m2020 URDF authors link frames in a graphics-style (Z-down)
convention inherited from the JPL RSVP visualisation tool, not REP-103.
The Stage-3 spawn applies a 180-deg X-roll on the rover prim
(`spawn_orientation_rpy = [pi, 0, 0]` in
`configs/robots/rover_m2020.yaml`) so the rover renders correctly
inside Isaac Sim.  The same X-roll surfaces on `odom -> base_link`
when `publish_odom_tf: true`, and the URDF chain inside
`Body_Chassis` cancels it back out under the `odom` and `map`
frames -- which is why those Fixed Frames render correctly while
`base_link` and `Body_Chassis` themselves do not.  See
`docs/frame_conventions.md` for the full derivation.

The legacy `PubTF`-on-`/tf_raw` + `topic_tools relay /tf_raw /tf`
workflow is reachable via `ros2.publish_joint_states: false` +
`enable_isaac_nameoverride: true` for v0.7 scenarios that depend on
it.

### QoS preset reasoning

The four QoS profiles map to ROS2 conventions:

* **`cmd_vel_qos`** → RELIABLE/depth=10. Matches Nav2 `controller_server`
  output (REP-2003 SystemDefault). Flip to `best_effort` if driving with
  `teleop_twist_keyboard`.
* **`odom_qos`** → RELIABLE/depth=10. `nav_msgs/Odometry` REP-2003
  SystemDefault.
* **`sensor_qos`** → BEST_EFFORT/depth=5. The ROS2 `sensor_data`
  convention. **Required** for `slam_toolbox` LaserScan subscribers,
  which default to BEST_EFFORT.
* **`tf_qos`** → RELIABLE + TRANSIENT_LOCAL/depth=100. Matches `tf2_ros`
  defaults. TRANSIENT_LOCAL on `/tf_static` lets a late-joining
  `slam_toolbox` still latch the static sensor frames.

Override any of them in `rover.ros2` of your scenario YAML — see
`marslab/config/schema/ros2_bridge.py::Ros2BridgeConfig` for the full
field list.

### Note on color RGB-D point clouds

`/rover/depth/points` carries **XYZ + intensity**, not XYZRGB. Isaac Sim's
RGB-D camera does not emit a color-fused point cloud natively. To get an
XYZRGB stream, run the standard ROS2 fusion node externally:

```bash
ros2 run depth_image_proc point_cloud_xyzrgb_node \
    --ros-args \
    -r rgb/image_rect_color:=/rover/rgb/image_raw \
    -r rgb/camera_info:=/rover/rgb/camera_info \
    -r depth_registered/image_rect:=/rover/depth/image_raw \
    -r points:=/rover/depth/points_xyzrgb
```

See `docs/colored_pointcloud.md` for the full pattern, including TF
alignment and frame conventions.

---

## 5. Authoring a Custom Scenario

The fastest path is to copy
`configs/scenarios/template_single_file.yaml`, save under a new name, and
edit four fields. Every field below is annotated inline in the template
with a `← 자주 바꾸는 곳` ("frequently changed") marker.

### 5a. Change rover top speed

```yaml
rover:
  control:
    max_linear_velocity: 1.0       # was 0.5 m/s
    max_angular_velocity: 0.8      # was 0.5 rad/s
```

### 5b. Move the rover spawn

```yaml
rover:
  spawn:
    mode: "absolute"               # dem_center | dem_relative | absolute
    xy: [10.0, -5.0]               # m, world frame
    z_offset: 0.5                  # clearance above terrain at (xy)
    orientation_rpy: [3.14159, 0.0, 0.0]
```

### 5c. Crank up the dust storm

```yaml
mars_env:
  dust_optical_depth: 2.5          # 0.3 = clear, 1.0 = hazy, 4.0 = global storm
```

### 5d. Re-roll the procedural terrain

```yaml
terrain:
  seed: 99                         # any integer
```

### Pydantic validation

Every field listed above is enforced by a `pydantic.BaseModel` with
`model_config = ConfigDict(extra="forbid")`. **Typos fail at YAML load
time** with a `pydantic.ValidationError` that names the offending key
and the closest valid alternative — long before Isaac Sim boots. See
`marslab/config/schema/` and the full schema reference at
`docs/scenario_format.md` (473 lines, every field documented).

---

## 6. Drop-in 3D Assets (`.obj` / `.stl`)

Any `.obj` or `.stl` file on disk can be placed in the scene by adding one
block to the scenario YAML. From `configs/scenarios/jezero_flat.yaml:54-60`:

```yaml
scene:
  structure_assets:
    - path: "tests/fixtures/sample_rock.obj"
      position: [10.0, 5.0, 0.0]
      rotation_rpy_deg: [0.0, 0.0, 45.0]
      scale: 1.0
      name: "boulder_01"
```

Both `.obj` and `.stl` flow through the same `marslab.scene.structure_loader`
code path — pick whichever exporter your modelling tool supports. The path
is resolved relative to the MarsLab repo root.

For richer scenes, see `configs/scenarios/spacecraft_landing.yaml`
(lander + heat shield + parachute debris field).

---

## 7. SLAM + Nav2 Integration

SLAM and Nav2 configs ship under `configs/slam/` and `configs/nav2/`. They
are vanilla `slam_toolbox` and `nav2_bringup` parameter files — no MarsLab
fork — so any tutorial that targets stock ROS2 Jazzy applies directly.

```bash
# 2D SLAM with slam_toolbox.
ros2 launch slam_toolbox online_async_launch.py \
    params_file:=$(pwd)/configs/slam/slam_toolbox_async.yaml

# Autonomous navigation with Nav2.
ros2 launch nav2_bringup navigation_launch.py \
    params_file:=$(pwd)/configs/nav2/nav2_params.yaml
```

`slam_toolbox` requires BEST_EFFORT QoS on `/rover/scan`. MarsLab's default
already satisfies this — `Ros2BridgeConfig.sensor_qos.reliability =
"best_effort"` ships out of the box, so no QoS overrides are needed.

For Nav2 smoke testing, set goals interactively in RViz with the
**"2D Goal Pose"** tool. (We deliberately do not ship a waypoint-runner
script — RViz is the canonical Nav2 driver and reproducibility comes
from logging `/tf` + `/rosout`, not from re-running a Python script.)

### 7c. 3D LiDAR odometry (kinematic-icp / RTAB-Map)

3D LiDAR-based odometry has been validated against two open-source
stacks.  Each stack interprets the relationship between PointCloud
data axis and `frame_id` differently, so
`configs/robots/rover_m2020.yaml`'s
`sensors.lidar_3d.local_orientation_rpy_deg` must be flipped per
stack.  The other LiDAR runtime parameters (`range_min` / `range_max`
/ `horizontal_fov_deg` / `vertical_fov_deg` / `rotation_rate_hz`) are
applied through the OmniSensorGenericLidarCoreAPI override path and
work the same way in both stacks.

**Common prerequisite**: Stage-3 + the
`robot_state_publisher` launch file from
[Section 1](#1-quick-start-60-seconds) must already be running.

#### kinematic-icp (KISS-ICP)

YAML:

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

Param breakdown: `lidar_topic` is the Stage-3 PointCloud2;
`base_frame` is the X-roll wrapper frame from
`rover_state_publisher.launch.py`; `use_sim_time` aligns kinematic-icp
to Isaac Sim's `/clock`; `use_2d_lidar:=false` selects the 3-D
PointCloud path; `tf_timeout` is the TF lookup grace; `visualize`
launches kinematic-icp's own RViz config.

Why identity rpy: kinematic-icp assumes the PointCloud raw data axis
matches the ROS axis of `frame_id=lidar_link`.  Isaac Sim's RTX LiDAR
publishes data in the USD prim's local frame, and our spawner leaves
the LiDAR prim orient at identity, so the broadcast must also be
identity for the two axes to coincide.

#### RTAB-Map (3D LiDAR mode)

YAML:

```yaml
sensors:
  lidar_3d:
    local_orientation_rpy_deg: [180.0, 0.0, 0.0]
```

RTAB-Map's 3-D LiDAR mode lifts the PointCloud through
`lidar_link → base_link → odom → map` and accumulates in the map
frame.  Empirically the X-rolled `lidar_link` broadcast cancels with
the rest of the chain to produce a consistent map; identity rpy
(the kinematic-icp setting) leaves the map skewed.

The exact reason the two stacks demand different `lidar_link` axes
remains open and is tracked in `work_log/Version1.5.md` (alongside
the proper fix: extending `marslab/sensors/sensor_spawner.py` to
apply `AddOrientOp` on the LiDAR prim itself, mirroring the camera /
IMU spawn pattern, so the same yaml setting works for both stacks).

---

## 8. Architecture

Three principles govern every structural decision:

* **P1 — Flat.** No premature abstraction. No plugin systems, no god
  objects, no registration mechanisms. Procedural code first; classes only
  when complexity demands it.
* **P2 — Unidirectional data flow.** Config → pure-Python compute →
  Isaac Sim scene → native sim loop. No module modifies the simulation
  loop. No circular imports.
* **P3 — Offline-first testing.** Every pure-compute module (Beer's law,
  COMIMART, Golombek SFD, config validation, label conversion) runs in
  CI without Isaac Sim or a GPU.

### Module map

| Module             | Responsibility                                   | Isaac Sim required? |
|--------------------|--------------------------------------------------|---------------------|
| `marslab/config/`  | YAML load, pydantic validation, seed propagation | No                  |
| `marslab/environment/` | Mars physics: sun, Beer's law, COMIMART, sky | No                  |
| `marslab/terrain/` | DEM loading, mesh build, rock placement, materials | Partial           |
| `marslab/scene/`   | Structure loader (`.obj`/`.stl` drop-in)         | Yes                 |
| `marslab/rendering/` | Sky dome, sun light, atmosphere fog, render mode | Yes               |
| `marslab/robots/`  | URDF→USD spawn, articulation, drive API          | Yes                 |
| `marslab/sensors/` | Camera, LiDAR, IMU attachment + config           | Yes                 |
| `marslab/ros2_bridge/` | rclpy + OmniGraph publishers / subscribers   | Yes                 |
| `marslab/runtime/` | Stage-2 / Stage-3 boot + main loop               | Yes                 |
| `marslab/gui/`     | Atmosphere panel + interactive controls          | Yes                 |

The full guideline catalogue (G1-G13 and CLAUDE.md operating principles
OP-1 through OP-5) lives in `CLAUDE.md`. This README mentions them only in
passing — they're a developer concern, not a user concern.

---

## 9. Citation, License, Roadmap

### License

Apache 2.0 — see `LICENSE`. All MarsLab source code is original. We study
OmniLRS, RLRoverLab, SRB, and `unitree_sim_isaaclab` for algorithmic and
pattern inspiration but do not copy code or naming.

### Third-Party Assets

The Perseverance (M2020) rover URDF and glTF meshes are vendored as a
git submodule under `assets/m2020-urdf-models/` (a fork of
`github.com/nasa-jpl/m2020-urdf-models`, NASA/JPL release IDs URS307049
and URS309682). Models courtesy of the Mars 2020 Perseverance and
Ingenuity teams; URDF conversion by JPL RSVP team. See
`THIRD_PARTY_LICENSES.md` for the full attribution and license note.

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

* **v1.0 (current, iSpaRo 2026 submission):** engineering quality. Nine
  scenarios, single M2020 rover, ROS2 bridge, SLAM + Nav2, dynamic
  atmosphere, pydantic-validated YAML throughout.
* **v1.5 (post-iSpaRo, engineering follow-ons):**
    * GUI `.obj` / `.stl` loader (no YAML edit needed).
    * Non-ROS2 dataset export (HDF5 / Parquet) for ML training pipelines.
    * Scenario DSL — a lightweight shorthand for the most common scenario
      patterns.
    * Multi-rover coordination (the schema is already multi-rover-ready;
      runtime orchestration is the remaining work).
    * Fault injection (sensor dropout, wheel slip, IMU bias drift).
* **v2.0 (post-iSpaRo, photorealism):** Hapke BRDF on regolith, dust
  dynamics, 4K HDRI, anti-tiling, photogrammetry rocks, OmniLRS-level
  shading.
* **v3.0 (future):** Bekker / Janosi terramechanics, RL environments
  (Isaac Lab Gym API), Ls-parameterized seasonal variation.

---

## Requirements

* **NVIDIA Isaac Sim 5.x** (standalone install)
* **Python 3.10+**
* **ROS2 Jazzy** (for the runtime bridge; not needed for unit tests)
* **GPU:** NVIDIA RTX series (tested on RTX 5070 Ti)
* **OS:** Ubuntu 22.04+
* `libgdal-dev`, `gdal-bin` (for HiRISE GeoTIFF preprocessing)

Python dependencies pin in `pyproject.toml` (`pydantic>=2.0`, `pyyaml>=6.0`,
`numpy>=1.24`, `GDAL>=3.8`, `scipy>=1.10`, `trimesh`).

---

## Running the Test Suite

Unit tests run on CPU, no Isaac Sim required:

```bash
pytest tests/unit/ -q                      # 1151+ tests
black --check marslab/ scripts/ tests/
ruff check   marslab/ scripts/ tests/
```

Isaac Sim integration tests (manual; user-driven per project convention):

```bash
scripts/isaac_python.sh scripts/run_integration_test.py
```

See `tests/integration/` for the IMU-gravity, ROS2-topic, and
slam_toolbox integration gates.

---

## Where to Read Next

* `docs/scenario_format.md` — full scenario YAML schema reference.
* `docs/colored_pointcloud.md` — `depth_image_proc` XYZRGB fusion pattern.
* `CLAUDE.md` (English) / `CLAUDE_kor.md` (Korean) — developer-side
  guidelines, principles, and the 8-week sprint plan toward iSpaRo 2026.
* `work_log/LOG.md` — append-only development history. A new contributor
  reads this file to catch up on every decision MarsLab has made.
