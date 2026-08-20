# ROS 2 bridge guide

`marslab.ros2_bridge` is the runtime-only boundary between Isaac/OmniGraph
outputs and optional rclpy publishers. The supported user launch is:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```

Start `launch/rover_state_publisher.launch.py` separately when the companion
articulation publisher is required; keep it in a ROS environment separate from
the Isaac Python process.

## Ownership contract

- Isaac-side graph publishing carries `/clock`, command input, Camera outputs,
  raw IMU, 3-D LiDAR, and joint states when ROS is enabled.
- rclpy publishers carry robot description, noisy IMU, evaluation ground truth,
  and wheel odometry.
- Ground truth is topic-only `map`/`base_link_gt` on the configured trajectory
  topic. Wheel odometry is `odom`/`base_link`; only
  `wheel_odom.publish_tf=true` makes it the MarsLab dynamic TF owner.
- The companion launch owns exactly one identity static TF
  `base_link`→`Body_Chassis`. Its articulation publisher owns the chain below
  `Body_Chassis`; MarsLab's static sensor broadcaster owns only Camera, IMU,
  and 3-D LiDAR children below that root.

## Where to look

| Task | Location | Notes |
|---|---|---|
| OmniGraph construction | `sensor_graph.py`, `sensor_graph_builder.py` | Keep retained acquisition handles and graph paths aligned. |
| QoS mapping | `qos.py`, `../config/schema/rover_ros2.py` | One validated config maps to runtime profiles. |
| rclpy setup | `rclpy_integration.py`, `rclpy_publishers.py` | Open only after Isaac startup and close in reverse order. |
| TF and odometry | `tf_broadcaster.py`, `odometry_publisher.py`, `wheel_odometry_publisher.py` | Preserve one owner per edge and distinct GT/Wheel topics. |
| Description companion | `robot_description_publisher.py`, `../../launch/` | Keep URDF publication with the external articulation publisher. |

## Rules

- Defer Isaac, Omni, and live rclpy imports; keep pure bridge math importable
  without runtime bindings.
- Preserve shared Camera timing, seeded noise, configured prim paths, frame IDs,
  and QoS settings.
- Keep comments concise and state producer, consumer, or ownership only.
- Agent checks are static/offline. User-only Isaac/ROS runtime validation must
  use the canonical command above, and no agent claims topics, TF, QoS, clock,
  or cleanup behavior without a user observation.
