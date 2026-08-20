# Ground truth and wheel odometry

MarsLab publishes two independent `nav_msgs/Odometry` streams when the ROS 2
bridge is enabled:

| Stream | Default topic | Frames | Role |
| --- | --- | --- | --- |
| Evaluation ground truth | `/rover/GT_Trajectory` | `map` to `base_link_gt` | Absolute Isaac-world reference; topic-only. |
| Wheel odometry | `/rover/odom` | `odom` to `base_link` | Encoder estimate with configured slip and seeded speed noise. |

The names are configured by `rover.ros2.topics` and the frame fields by
`rover.ros2.odom_publisher`. The schema rejects a namespace-resolved topic
collision between the two streams.

## Evaluation ground truth

The GT publisher reports the articulation pose in the Isaac Scene/world frame:
the world origin, axes, and metre scale are unchanged. It publishes no TF and
does not supply the operational `odom` to `base_link` edge. Record it as an
absolute reference for offline trajectory metrics.

## Wheel odometry

Wheel odometry integrates the configured left and right wheel joints using the
wheel radius, track width, slip, and seeded Gaussian speed noise. It always
publishes `/rover/odom` when wheel odometry is enabled. The top-level
`wheel_odom.publish_tf` setting controls dynamic TF ownership:

- `true`: Wheel odometry is the sole MarsLab publisher of `odom` to `base_link`.
- `false`: the topic remains available, but an external estimator owns that
  dynamic edge.

Keep `map`/`base_link_gt` and `odom`/`base_link` distinct in consumers and
recording pipelines.
