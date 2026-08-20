# MarsLab GT Pose and Wheel Odometry

MarsLab exposes two deliberately separate `nav_msgs/Odometry` streams:

| Stream | Topic | Frames | Meaning | Transform authority |
| --- | --- | --- | --- | --- |
| Evaluation GT Pose | `/<namespace>/GT_Trajectory` (`gt_trajectory`) | `map` → `base_link_gt` | Absolute articulation pose in Isaac world coordinates | None; topic-only |
| Operational Wheel Odom | `/<namespace>/odom` (`odom`) | `odom` → `base_link` | Encoder dead-reckoning with configured slip and Gaussian wheel-speed noise | `wheel_odom.publish_tf` only |

The streams are not merged, rebased, or interchangeable. A namespace-resolved
`odom`/`gt_trajectory` collision is rejected by the ROS configuration schema.

## Evaluation GT Pose

`marslab/ros2_bridge/odometry_publisher.py` reads the PhysX articulation root
pose and publishes it directly on the configured `gt_trajectory` topic. ROS
`map` is defined here as identical to the Isaac Scene/world origin, axes, and
meter scale. The message position and scalar-first quaternion therefore equal
the current world position and orientation; the rover's spawn pose or a reset
never becomes an offset. The message timestamp comes from the simulation node
clock, and the velocity fields retain the existing world-to-body conversion.

GT is evaluation data. It does not publish a transform, feed navigation, or
claim the `odom` → `base_link` edge. Consumers should record it as the absolute
reference trajectory for ATE/RPE and compare an estimator against it offline.

## Operational Wheel Odom

`marslab/ros2_bridge/wheel_odometry_publisher.py` integrates left/right wheel
joint velocities using the configured wheel radius and track width. Slip and
seeded Gaussian wheel-speed noise are applied before the existing skid-steer
forward-kinematics and timestamp-based integration. The resulting estimate is
published on `odom` with `odom`/`base_link` labels and the existing covariance
diagonals.

When `wheel_odom.publish_tf` is `true`, Wheel Odom is the sole MarsLab
candidate allowed to publish `odom` → `base_link`. When it is `false`, Wheel
Odom still publishes the topic but emits no transform so an external odometry
or SLAM stack can own that edge. In both modes the topic message, noise math,
and simulation timestamps are unchanged.

## Usage guidance

- Use `GT_Trajectory` only as an offline evaluation reference; do not feed it
  into a SLAM or navigation estimator.
- Use `odom` as the operational wheel-odometry input when a noisy prior is
  wanted.
- Select exactly one owner for `odom` → `base_link`: Wheel Odom when its gate
  is enabled, otherwise the external stack.
- Keep `map`/`base_link_gt` and `odom`/`base_link` as distinct frame pairs; do
  not rename or combine them to make the streams appear equivalent.
