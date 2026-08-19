# MarsLab TF Frame Conventions

MarsLab uses REP-103 body axes: +X forward, +Y left, +Z up. The rover spawns
with the identity orientation from `configs/rover_m2020.yaml`; sensor mount
translations and RPY values are authored directly in `Body_Chassis` coordinates.

## Frame tree and authorities

- The companion launch publishes the sole identity `base_link -> Body_Chassis`
  static transform.
- Isaac publishes joint states. The external `robot_state_publisher` owns the
  articulation chain below `Body_Chassis`.
- MarsLab publishes static `Body_Chassis -> camera_link`, `lidar_link`, and
  `imu_link` offsets, plus `camera_link -> camera_optical_frame`.
- Wheel odometry may own `odom -> base_link`; set its configured TF gate false
  when an external odometry stack owns that transform.

`camera_optical_frame` follows REP-105 optical axes: Z forward, X right, and Y
down. Image, depth, and camera point-cloud messages use that frame ID.

## Sensor extrinsics

Use `parent_link: "Body_Chassis"` and REP-103 offsets in the canonical rover
configuration. For example, a mast sensor 2.4 m above and 0.15 m left of the
chassis has `local_translation: [0.3, -0.15, 2.4]`. Its orientation is the
configured mount RPY; no frame-axis compensation is applied by MarsLab.

Actual Isaac and ROS TF-tree verification is user-run at G5.
