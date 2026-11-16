---
title: ROS 2 and TF
description: ROS companion setup, topic contracts, QoS and transform ownership.
permalink: /reference/ros2/
---

## Topic reference

These topics describe the default Perseverance profile with ROS 2 enabled. Mission profiles omit LiDAR and depth; see the [robot comparison]({{ "/robots/" | relative_url }}).


| Interface | Default topic | Notes |
|:---|:---|:---|
| Command input | `/rover/cmd_vel` | `geometry_msgs/Twist` |
| RGB image | `/rover/rgb/image_raw` | Shared Camera render product |
| Depth image | `/rover/depth/image_raw` | Shared Camera render product |
| Camera point cloud | `/rover/depth/points` | XYZ `sensor_msgs/PointCloud2` |
| Camera calibration | `/rover/rgb/camera_info` | `sensor_msgs/CameraInfo` |
| Raw IMU | `/rover/imu` | `imu_link` |
| Noisy IMU | `/rover/imu_noisy` | Seeded noise stream |
| 2-D LiDAR | `/rover/scan` | `sensor_msgs/LaserScan`, `lidar_2d_link` |
| 3-D LiDAR | `/rover/lidar/points` | `lidar_link` |
| Joint states | `/rover/joint_states` | Consumed by the companion |
| Robot description | `/rover/robot_description` | Companion-owned latched URDF text |
| Ground truth | `/rover/GT_Trajectory` | `map → base_link_gt`, topic only |
| Wheel odometry | `/rover/odom` | `odom → base_link` |
| Simulation clock | `/clock` | Isaac simulation time |

Ground truth never publishes TF. `wheel_odom.publish_tf` is the only MarsLab
switch for dynamic `odom → base_link` TF ownership.


## Namespace


`rover.ros2.namespace` is normalized without outer slashes. Topic entries are
relative names and must not start or end with `/`.

## Companion launch

For the robot description and articulation TF chain, first prepare the `.venv`
environment described in [the installation guide]({{ "/guide/installation/#install-python-dependencies" | relative_url }}).
Run the companion from the repository root in a separate ROS terminal:

```bash
source /opt/ros/jazzy/setup.bash
.venv/bin/python /opt/ros/jazzy/bin/ros2 launch launch/rover_state_publisher.launch.py \
  config:=configs/config.yaml robot:=curiosity
```

The launch file reads its sibling [companion_urdf.py](https://github.com/kimhoyun-robotair/MarsLab/blob/main/launch/companion_urdf.py).
This helper discovers the selected URDF's root link, handles source floating
joints, and resolves relative mesh filenames to absolute file
URIs. It leaves the source URDF unchanged. Keep both Python files in `launch/`.

Pass the same `config` and `robot` used by the simulator. The companion uses
MarsLab's pure configuration loader, including profile merging and YAML-relative
asset paths, without importing Isaac. Its defaults are the repository's
`configs/config.yaml` and that scenario's robot selector. The selected profile
supplies `rover.urdf_source_path`, `rover.ros2.namespace`, and
`rover.ros2.topics.joint_states`. PyYAML and Pydantic 2 are declared in
[requirements.txt](https://github.com/kimhoyun-robotair/MarsLab/blob/main/requirements.txt) and must be installed into the Python
environment used for this command.

Optional `urdf_path:=<path>`, `namespace:=<name>`, and
`joint_states_topic:=<topic>` launch arguments override the selected settings.
Its `publish_frequency` argument controls robot_state_publisher cadence, not the
Isaac physics or sensor sampling rate. This is one shared launch file for all
rovers, not a separate launch file per model.

## Ownership and QoS

Keep these ownership rules intact:

- The companion owns identity `base_link` to the selected URDF root (`Body_Chassis`
  by default), the URDF
  articulation chain and the retained `/rover/robot_description` topic.
- MarsLab owns static sensor frames below `rover.ros2.sensor_parent_frame_id`
  (`Body_Chassis` by default).
- Ground truth uses `map` / `base_link_gt` and publishes no TF.
- Wheel odometry uses `odom` / `base_link`.
- `wheel_odom.publish_tf` is the only MarsLab switch for dynamic odometry TF.

Ground-truth and wheel-odometry topics must be different.

QoS profiles support:

- Reliability: `reliable` or `best_effort`
- Durability: `volatile` or `transient_local`
- History: `keep_last` (the common rclpy/OmniGraph supported policy)
- Queue depth: a positive value within the validated range

Use best-effort/volatile QoS for high-rate sensors unless a consumer requires
reliable delivery. Keep static and latched data transient-local where supported.
The supplied camera publishers are best-effort, so a subscriber requesting
reliable delivery will not match them. In RViz, set the Image display's
Reliability Policy to **Best Effort**. To inspect a live primary image header
without printing its pixel array:

```bash
ros2 topic echo /rover/rgb/image_raw --qos-reliability best_effort --once --no-arr
```

The simulator, companion, and viewers must share `ROS_DOMAIN_ID` and compatible
DDS discovery settings. `robot_state_publisher` publishes description and TF;
camera messages are published by the Isaac bridge and do not require that node.
