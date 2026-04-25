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
#         Uses GDAL on the host CPU. Output is cached under
#         assets/dem/processed/<name>.npy + .yaml.
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

Nine reference scenarios ship with v1.0:

| Scenario                  | Source                    | One-line description                                                  |
|---------------------------|---------------------------|-----------------------------------------------------------------------|
| `jezero_flat`             | HiRISE Jezero crater W    | dz=3 m, mean slope ≈2°. Baseline / SLAM regression.                  |
| `jezero_crater`           | HiRISE Jezero crater NE   | dz=12.6 m, max slope 30°. Slope-handling test.                       |
| `jezero_rocks`            | HiRISE Jezero (same crop) | Same DEM, dense Golombek rocks (CFA k=0.08). Obstacle field.         |
| `cerberus_canyon_easy`    | HiRISE Cerberus Fossae S  | 82% traversable. Approach-with-crater nav baseline.                   |
| `cerberus_canyon`         | HiRISE Cerberus Fossae    | 28% impassable, mean slope 25°. Path-planning stress test.           |
| `cave_lava_tube`          | Procedural (MARS-LT-B)    | 200 m wide lava tube, 1 skylight. GPS-denied SLAM.                   |
| `mars_base`               | HiRISE Jezero + structures| Crewed-outpost layout, 40 m goal-pose for Nav2 evaluation.            |
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
| `/tf`                          | `tf2_msgs/TFMessage`          | RELIABLE + TRANSIENT_LOCAL/100 | `Ros2BridgeConfig.tf_qos`        |
| `/tf_static`                   | `tf2_msgs/TFMessage`          | RELIABLE + TRANSIENT_LOCAL/100 | `Ros2BridgeConfig.tf_qos`        |

`/rover/depth/points` carries `frame_id: camera_optical_frame` (REP-103
optical convention). `/rover/lidar/points` and `/rover/scan` use
`camera_link`-style sensor frames published on `/tf_static` at boot.

`/tf` has **two authorities** by REP-105 design:

* The Isaac Sim OmniGraph publishes the articulation chain
  (`base_link → wheels`, `base_link → camera_link`, etc.).
* `marslab.ros2_bridge.odometry_publisher` publishes `odom → base_link`
  every physics step.

This is canonical multi-publisher TF — all of RViz, Nav2, and
`slam_toolbox` subscribe to `/tf` and merge the trees automatically.

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

For richer scenes, see `configs/scenarios/mars_base.yaml` (habitat + solar
arrays + airlock + comm dish + ISRU plant) and
`configs/scenarios/spacecraft_landing.yaml` (lander + heat shield +
parachute debris field).

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
