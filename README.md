# MarsLab

MarsLab is an Isaac Sim 5.x Mars-rover runtime with an optional ROS 2 Jazzy
companion. A run is defined by one integrated configuration document:
`configs/config.yaml`. Paths inside that document are resolved relative to the
document itself, and the document is loaded and checked before Isaac Sim starts.

## Install

Isaac Sim 5.x and (for ROS output) ROS 2 Jazzy are installed separately from
this repository. The rover URDF and meshes are a required git submodule.

For a fresh checkout:

```bash
git clone --recursive <repository-url>
cd MarsLab
```

For an existing checkout:

```bash
git submodule update --init --recursive
```

Install the Python package in the environment used for offline configuration
work:

```bash
pip install -e .
```

The Isaac launcher supplies the Isaac Python interpreter at runtime.

## Run

The supported MarsLab runtime invocation is:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```

The launcher keeps a system ROS environment out of the Isaac Python process.
Do not source ROS in the terminal that runs this command. If ROS output is
enabled, start the companion in a separate ROS 2 terminal:

```bash
source /opt/ros/jazzy/setup.bash
ros2 launch launch/rover_state_publisher.launch.py
```

The companion defaults to the URDF in the repository submodule and the
`rover` namespace. Set `urdf_path:=...` or `namespace:=...` only when the
corresponding paths or namespace in `configs/config.yaml` are changed.

## Integrated configuration

`configs/config.yaml` is the sole runtime input. Its top-level sections are:

| Section | Purpose |
| --- | --- |
| `scene` | Supplied Scene USDZ path (`usdz_path`). |
| `runtime` | `headless`, `ros2_enabled`, and `atmosphere_enabled` switches. |
| `mars_env` | Gravity, dust, solar position, sol timing, and dynamic atmosphere. |
| `rendering` | Render mode, sky-dome assets, resolution, sun, fog, and path tracing. |
| `rover` | Rover USD/URDF paths, spawn and physics values, control, sensors, and ROS names/rates/QoS. |
| `wheel_odom` | The dynamic `odom` to `base_link` TF gate (`publish_tf`). |

The retained sensor settings are under `rover.sensors`:
`seed`, `camera`, `imu`, and `lidar_3d`. Camera, IMU, and 3-D LiDAR acquisition
is always created by the simulator, regardless of ROS transport. `rover.ros2`
selects the namespace, topic names, rates, frame IDs, and QoS when the ROS
bridge is enabled. `rover.control` and `rover.wheel_odometry` hold the drive
and wheel-estimation parameters.

## Runtime outputs

With `runtime.ros2_enabled: true` (the supplied configuration enables it), the
default namespace is `/rover` and the following outputs are retained:

| Output | Topic | Frames / notes |
| --- | --- | --- |
| Command input | `/rover/cmd_vel` | `geometry_msgs/Twist`. |
| Camera RGB | `/rover/rgb/image_raw` | One Camera render product. |
| Camera depth | `/rover/depth/image_raw` | Same Camera render product. |
| Camera point cloud | `/rover/depth/points` | `sensor_msgs/PointCloud2`, XYZ data. |
| Camera calibration | `/rover/rgb/camera_info` | `sensor_msgs/CameraInfo`. |
| Raw IMU | `/rover/imu` | `sensor_msgs/Imu`, `imu_link`. |
| Noisy IMU | `/rover/imu_noisy` | Seeded noise; emitted when either IMU sigma is positive. |
| 3-D LiDAR | `/rover/lidar/points` | `sensor_msgs/PointCloud2`, `lidar_link`. |
| Joint states | `/rover/joint_states` | Consumed by the companion `robot_state_publisher`. |
| Robot description | `/rover/robot_description` | Latched M2020 URDF text. |
| Evaluation ground truth | `/rover/GT_Trajectory` | `nav_msgs/Odometry`, `map` to `base_link_gt`, topic-only. |
| Wheel odometry | `/rover/odom` | `nav_msgs/Odometry`, `odom` to `base_link`. |
| Simulation clock | `/clock` | Isaac simulation time. |

Ground truth and wheel odometry are independent streams. Ground truth is the
absolute evaluation pose and never publishes TF. Wheel odometry is the
operational encoder estimate; `wheel_odom.publish_tf: true` makes it the sole
MarsLab publisher of dynamic `odom` to `base_link` TF, while `false` leaves
that edge for an external estimator. The two topic/frame pairs must not be
merged.

## TF ownership

The companion launch owns exactly one static identity transform:
`base_link` to `Body_Chassis`. The external `robot_state_publisher` owns the
articulation chain below `Body_Chassis` using `/rover/joint_states` and
`/rover/robot_description`. MarsLab owns static sensor offsets below
`Body_Chassis` (`camera_link`, `camera_optical_frame`, `lidar_link`, and
`imu_link`). Ground truth owns no TF; the wheel odometry setting above is the
only MarsLab switch for dynamic `odom` to `base_link` ownership.

## AtmospherePanel

When `runtime.atmosphere_enabled: true` and `runtime.headless: false`, the
Isaac GUI includes `AtmospherePanel`. It displays the precomputed atmosphere
state and follows the dynamic atmosphere settings in `mars_env`. Headless
runs keep the same configuration and runtime outputs but do not create the
GUI panel.

## User-run Isaac checklist

The following checks require the user's Isaac Sim and ROS installations; they
are not substitutes for the canonical command above.

1. Confirm Isaac Sim 5.x, the Scene USDZ, rover USD, and the initialized URDF
   submodule are present.
2. In a terminal without a sourced ROS environment, run the canonical command
   and wait for the configured world and rover to appear.
3. Confirm the Camera RGB/depth/point-cloud products, raw and noisy IMU
   streams, and 3-D LiDAR point cloud are present when ROS is enabled.
4. In the separate ROS terminal, confirm `/clock`, joint states, robot
   description, sensor topics, `/rover/GT_Trajectory`, and `/rover/odom`.
5. Confirm TF ownership: one identity `base_link` to `Body_Chassis`, the
   articulation descendants from `robot_state_publisher`, sensor frames below
   `Body_Chassis`, no ground-truth TF, and the wheel TF gate's selected owner.
6. With GUI and atmosphere enabled, confirm `AtmospherePanel` is visible and
   updates with the atmosphere state.
7. Stop the run with `Ctrl-C`, then confirm the Isaac and companion processes
   have exited.

## RGB-D color point clouds

The retained Camera point cloud is XYZ. To add color, use the standard ROS 2
`depth_image_proc` fusion node with `/rover/rgb/image_raw`,
`/rover/rgb/camera_info`, and `/rover/depth/image_raw`; publish the fused
result on a separate topic such as `/rover/depth/points_xyzrgb`.

## Repository boundaries

MarsLab consumes supplied Scene USDZ and rover assets. Scene authoring, terrain
generation, and asset conversion are outside the runtime path. CPU-safe config,
environment calculations, and control math remain importable without Isaac;
Isaac, ROS, sensors, GUI, and cleanup observations belong to the user-run
checklist above.
