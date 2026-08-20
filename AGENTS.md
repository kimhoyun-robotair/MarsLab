# MarsLab workspace guide

MarsLab is an Isaac Sim 5.x Mars-rover simulator with an optional ROS 2 Jazzy
bridge. The supported runtime has one integrated configuration document and one
Isaac-Python shell launcher. CPU-safe configuration and computation stay
separate from the Isaac scene boundary.

## Runtime contract

The canonical user launch is:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```

`configs/config.yaml` is the only active runtime input. Relative paths are
resolved from that file's directory. Preflight loads and validates the document
before Kit creation, then the lifecycle proceeds through atmosphere snapshot,
SimulationApp, world, rover, sensors, optional ROS 2, loop context, loop, and
reverse-order cleanup.

The retained runtime outputs are Camera RGB/depth/PointCloud2/CameraInfo, IMU
raw and noisy streams, 3-D LiDAR point clouds, joint states, robot description,
evaluation ground truth, wheel odometry, and the GUI AtmospherePanel when GUI
and atmosphere are enabled. Ground truth and wheel odometry are separate:
ground truth is the topic-only `map`/`base_link_gt` evaluation stream, while
wheel odometry is the operational `odom`/`base_link` stream. The
`wheel_odom.publish_tf` setting is the sole MarsLab switch for dynamic
`odom`→`base_link` TF ownership.

The ROS companion launch owns exactly one identity static transform
`base_link`→`Body_Chassis`. `robot_state_publisher` owns the articulation chain
below `Body_Chassis`; MarsLab owns retained sensor static frames below that
root. Keep these frame owners distinct.

## Structure and ownership

```text
MarsLab/
├── marslab/config/       # integrated YAML loading and Pydantic v2 schemas
├── marslab/environment/  # offline Mars/environment calculations
├── marslab/gui/          # AtmospherePanel
├── marslab/rendering/    # sky, sun, fog, render settings
├── marslab/robots/       # rover USD spawning and drive/physics setup
├── marslab/ros2_bridge/  # OmniGraph/rclpy publishers, TF, QoS
├── marslab/runtime/      # preflight, lifecycle context, simulation loop
├── marslab/sensors/      # Camera, IMU, and 3-D LiDAR creation
├── marslab/sim/          # SimulationApp and world bootstrapping
├── configs/config.yaml   # canonical runtime configuration
├── assets/               # rover and scene assets
└── launch/               # separate ROS companion launch
```

| Task | Location | Notes |
|---|---|---|
| Run the simulator | `marslab/isaac_python.sh`, `marslab/main.py` | User-run Isaac boundary; use the canonical command above. |
| Change config/schema | `marslab/config/` | Preserve one-file loading and offline imports. |
| Change lifecycle | `marslab/sim/`, `marslab/runtime/` | Keep Isaac imports deferred until SimulationApp exists. |
| Change sensors | `marslab/sensors/` | Preserve the retained sensor set and shared Camera product. |
| Change ROS, TF, or QoS | `marslab/ros2_bridge/` | Preserve explicit frame and publisher ownership. |
| Change rover physics | `marslab/robots/` | Keep USD spawning separate from pure control math. |

## Conventions

- Keep the dependency direction: configuration → pure computation → Isaac
  scene → runtime loop.
- Keep configuration, environment calculations, and control math importable
  without Isaac or a GPU.
- Defer `omni`, `isaacsim`, `pxr`, and live `rclpy` imports until their runtime
  boundary.
- Keep module and function comments concise: state role and ownership, not
  review history or duplicated type information.
- Agent-side verification is limited to source/config/launch reconciliation and
  offline static checks. Isaac GUI, physics, sensor, ROS, TF, AtmospherePanel,
  and cleanup observations are user-only runtime validation; do not claim them
  without a user's observation.

## Boundaries

- Scene USDZ and rover assets are explicit inputs; do not author terrain or
  convert rover source assets during runtime.
- `assets/m2020-urdf-models` is a git submodule and must be present for the
  companion launch.
- Keep the companion ROS process in its own environment; do not mix a system
  ROS environment into the Isaac Python process.
