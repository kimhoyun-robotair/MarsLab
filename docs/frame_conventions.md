# MarsLab frame conventions

MarsLab uses REP-103 body axes: +X forward, +Y left, and +Z up. The rover
configuration supplies sensor translations and RPY values in the
`Body_Chassis` frame.

## Ownership

- The companion launch publishes the one identity static transform
  `base_link` to `Body_Chassis`.
- The external `robot_state_publisher` publishes the articulation descendants
  below `Body_Chassis` from `/rover/joint_states` and the rover URDF.
- MarsLab publishes static `Body_Chassis` offsets for `camera_link`,
  `camera_optical_frame`, `lidar_link`, and `imu_link`.
- Ground-truth odometry is topic-only (`map` to `base_link_gt`). Wheel
  odometry uses `odom` to `base_link`; `wheel_odom.publish_tf` is the sole
  switch for that dynamic transform.

The identity connector is all zero translation and rotation. No other process
should publish a second `base_link` to `Body_Chassis` edge.

## Sensor frames

Camera images, depth, and Camera point clouds use `camera_optical_frame`,
whose axes are Z forward, X right, and Y down. The 3-D LiDAR and IMU messages
use `lidar_link` and `imu_link`. Set `local_translation` and
`local_orientation_rpy_deg` under each sensor block in `configs/config.yaml`;
these values are applied directly without axis compensation.

Runtime TF-tree observation is part of the user-run Isaac/ROS checklist in the
root README.
