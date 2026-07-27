# ROS 2 BRIDGE GUIDE

## OVERVIEW

This package connects Isaac/OmniGraph sensor output and optional `rclpy` nodes
to ROS 2. It is a runtime-only boundary, not an import requirement for CPU tests.

## WHERE TO LOOK

| Task | Location | Notes |
|---|---|---|
| Build OmniGraph sensor graphs | `sensor_graph.py`, `sensor_graph_builder.py` | Keep graph/schema paths aligned. |
| Translate QoS | `qos.py` | One validated config maps to rclpy profiles and Isaac JSON. |
| Initialize optional rclpy | `rclpy_integration.py` | Called only after Isaac startup. |
| Publish TF/odometry | `tf_broadcaster.py`, `odometry_publisher.py` | Respect single-owner transform rule. |
| Pure bridge math/naming | `odometry_math.py`, `tf_nameoverrides.py` | Keep these CPU-testable. |
| Publish description | `robot_description_publisher.py` | Companion to the external state publisher launch. |
| Configure QoS | `../config/schema/ros2_bridge.py` | Source of bridge config shape. |

## CONVENTIONS

- Keep Isaac/Omni/rclpy imports deferred; use mocks or skips for bindings in unit
  tests.
- Maintain the split between Isaac-side graph publishing and the rclpy side.
- Keep `sensor_graph_builder.py` pure; its shared camera render product keeps
  RGB, depth, point cloud, and camera-info timestamps aligned.
- Preserve seeded noise determinism and bridge validation for prim paths and
  wheel geometry.
- The separate ROS terminal runs `launch/rover_state_publisher.launch.py`; Isaac
  itself uses the environment isolated by `marslab/isaac_python.sh`.

## ANTI-PATTERNS

- Default TF authority is JointState plus external `robot_state_publisher`.
  Legacy `PubTF` requires explicit opt-in and publishes `/tf_raw`; never combine
  these authorities.
- Do not source system ROS into the Isaac Python process.
- Do not revive deprecated sensor Path A imports (`camera`, `imu`, `lidar`).

## CHECKS

```bash
pytest tests/unit/test_ros2_bridge_structure.py tests/unit/test_sensor_graph.py -q
pytest tests/unit/test_tf_extrinsic_consistency.py tests/unit/test_odometry_publisher.py -q
pytest tests/unit/test_sensor_graph_builder.py tests/unit/test_ros2_qos_config.py -q
pytest tests/unit/test_ros2_bridge_lazy_import.py tests/unit/test_tf_nameoverrides.py -q
```
