# MarsLab

**Standardized Mars simulation platform for SLAM, autonomous navigation, and
field-robotics research, built on NVIDIA Isaac Sim 5.x.**

MarsLab gives planetary-robotics researchers a single, scriptable, ROS2-native
testbed for repeatable Mars experiments. The runtime consumes a self-contained
Scene USDZ package, a scenario YAML for Mars atmosphere + lighting, and the
versioned M2020 rover USD bundle with its companion ROS assets.

* **Reproducible by design** — every randomized process accepts a `seed`; one
  Scene package plus one YAML configuration produces the same setup every run.
* **Explicit runtime inputs** — scene authoring is outside MarsLab's runtime
  scope. The supplied Scene USDZ and Rover assets are consumed as inputs; this
  repository does not generate terrain, rocks, habitats, or rover USD at run
  time.
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

# 3. Run the packaged Jezero reference scene.  --usda is retained during the
#    pre-S06 transition even though the input is a self-contained USDZ package.
marslab/isaac_python.sh marslab/main.py \
    --usda assets/scene/jezero_plain/jezero_plain.usdz \
    --scenario configs/default.yaml \
    --rover-yaml configs/rover_m2020.yaml \
    --no-ros2
```

Companion terminal (required for full TF):

```bash
source /opt/ros/jazzy/setup.bash
ros2 launch launch/rover_state_publisher.launch.py
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
| `--usda PATH` | str | (required) | Legacy pre-S06 parser flag for the required Scene USDZ package. |
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
    --usda assets/scene/jezero_plain/jezero_plain.usdz

# Morning sun experiment (formerly the "spacecraft_landing" preset).
marslab/isaac_python.sh marslab/main.py \
    --usda assets/scene/jezero_plain/jezero_plain.usdz \
    --sun-azimuth-deg 135 \
    --sun-elevation-deg 40

# Headless CI run (no viewport, full sim runs in the background).
marslab/isaac_python.sh marslab/main.py \
    --usda assets/scene/grand_canyon/grand_canyon.usdz \
    --headless

# No ROS2 (rover physics only, no topics published).
marslab/isaac_python.sh marslab/main.py \
    --usda assets/scene/jezero_plain/jezero_plain.usdz \
    --no-ros2

# No atmosphere stack (debug viewport jitter or pure terrain+rover validation).
marslab/isaac_python.sh marslab/main.py \
    --usda assets/scene/jezero_plain/jezero_plain.usdz \
    --no-atmosphere

# Custom z-offset (rover spawn 0.8 m above DEM centre — for bouldery terrain).
marslab/isaac_python.sh marslab/main.py \
    --usda assets/scene/grand_canyon/grand_canyon.usdz \
    --z-offset 0.8

# Composite — morning sun + headless + custom z-offset.
marslab/isaac_python.sh marslab/main.py \
    --usda assets/scene/jezero_plain/jezero_plain.usdz \
    --sun-azimuth-deg 135 \
    --sun-elevation-deg 40 \
    --headless \
    --z-offset 0.6
```

### 2b. Log output

```bash
# Pipe to a log file for later inspection.
marslab/isaac_python.sh marslab/main.py \
    --usda assets/scene/jezero_plain/jezero_plain.usdz \
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

## 3. Scene and Rover Inputs

MarsLab ships four reference Scene USDZ packages under `assets/scene/`:
Jezero Plain, Main Crater, Mars Base, and Grand Canyon. The current parser
continues to spell the scene argument `--usda` until S06; pass the selected
USDZ file to that flag during this compatibility window.

The rover is an explicit versioned input. `configs/rover_m2020.yaml` names
`assets/robots/rover/m2020.usd`; its ROS companion URDF and meshes remain in
the `assets/m2020-urdf-models` submodule. Keep these assets intact when
cloning or packaging a runtime checkout. MarsLab does not convert or generate
either Scene or Rover assets at startup.

The scene must expose collision geometry suitable for rover contact. A nested
`PhysicsScene`, when present, is deactivated so MarsLab's Mars-gravity
`/physicsScene` remains the sole active physics scene.

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
| `/rover/imu_noisy` | `sensor_msgs/Imu` | BEST_EFFORT/depth=5 | `Ros2BridgeConfig.sensor_qos` (only published when `imu.sigma_lin_acc > 0` or `sigma_ang_vel > 0`) |
| `/rover/rgb/image_raw` + `/rover/rgb/camera_info` | `sensor_msgs/Image`, `CameraInfo` | BEST_EFFORT/depth=5 | `Ros2BridgeConfig.sensor_qos` |
| `/rover/depth/image_raw` + `/rover/depth/points` | `sensor_msgs/Image`, `PointCloud2` | BEST_EFFORT/depth=5 | `Ros2BridgeConfig.sensor_qos` |
| `/rover/lidar/points` | `sensor_msgs/PointCloud2` | BEST_EFFORT/depth=5 | `Ros2BridgeConfig.sensor_qos` |
| `/rover/scan` | `sensor_msgs/LaserScan` | BEST_EFFORT/depth=5 | `Ros2BridgeConfig.sensor_qos` |
| `/clock` | `rosgraph_msgs/Clock` | (Isaac Sim default) | OmniGraph node |
| `/rover/joint_states` | `sensor_msgs/JointState` | RELIABLE + TRANSIENT_LOCAL/100 | `Ros2BridgeConfig.tf_qos` |
| `/tf` + `/tf_static` + `/robot_description` | std | RELIABLE + TRANSIENT_LOCAL/100 | `Ros2BridgeConfig.tf_qos` |

### IMU topic selection (raw vs noisy)

MarsLab publishes IMU data on **two separate topics**. Downstream consumers
(SLAM, path follower, sensor fusion) must explicitly pick one:

| Topic | Source | Use case |
|---|---|---|
| `/rover/imu` | Isaac Sim OmniGraph `PubIMU` node (raw) | Ground-truth IMU with no noise. Useful for algorithm bring-up, debugging, ideal-condition baselines. **Does not model real-sensor characteristics.** |
| `/rover/imu_noisy` | rclpy Python publisher with seeded Gaussian noise (`sigma_lin_acc`, `sigma_ang_vel`) | Reproducible noisy IMU for SLAM benchmarking. Same `sensors.seed` → identical noise sequence (see `marslab/ros2_bridge/imu_noise_publisher.py`). Multi-seed ATE experiments should subscribe here. |

Only `/rover/imu` is always published. `/rover/imu_noisy` is published only
when `imu.sigma_lin_acc > 0` or `imu.sigma_ang_vel > 0` in `rover_m2020.yaml`.

**Default in `configs/rover_m2020.yaml`**: `sigma_lin_acc: 0.05`,
`sigma_ang_vel: 0.005` — `/rover/imu_noisy` is published. Set both to `0.0` to
disable the noisy publisher.

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

Terrain authoring, scene composition, and URDF conversion are deliberately
outside the runtime path. MarsLab consumes the supplied Scene USDZ and Rover
assets without generating replacements at startup.

---

## 7. Citation, License, Roadmap

### License

The repository's release and third-party notices are finalized separately from
this runtime documentation pass. Do not infer redistribution rights for the
Scene or Rover assets from this README.

### Third-Party Assets

The Perseverance (M2020) rover URDF and glTF meshes are supplied by the
`assets/m2020-urdf-models/` submodule. Preserve the submodule and the rover
USD's layers, materials, and meshes; S13 owns formal attribution and notices.

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
  bridge, SLAM, dynamic atmosphere, and supplied Scene USDZ packages.
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
simulation against a supplied Scene USDZ + the default scenario YAML and confirming spawn
/ cmd_vel / sensor topics in RViz:

```bash
marslab/isaac_python.sh marslab/main.py \
    --usda assets/scene/jezero_plain/jezero_plain.usdz \
    --scenario configs/default.yaml \
    --rover-yaml configs/rover_m2020.yaml \
    --no-ros2
```

---

## Where to Read Next

* [Camera point-cloud notes](docs/colored_pointcloud.md)
* [Odometry and ground-truth notes](docs/odometry_ground_truth.md)
* [Frame conventions](docs/frame_conventions.md)
* [Project contribution guidance](AGENTS.md)
