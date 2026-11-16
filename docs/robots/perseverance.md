---
title: Perseverance
description: Perseverance profile selection, sensor inventory, mobility settings and simulation assumptions.
permalink: /robots/perseverance/
---

**Available in main · Default research profile**

The default M2020-based research rover combines a primary RGB camera, synthetic depth, 2-D and 3-D LiDAR, IMU and wheel odometry. The added sensing supports navigation experiments; it is not a reproduction of the flight sensor suite.

## Select this rover

After [installation]({{ "/guide/installation/" | relative_url }}), run from the repository root in the Isaac terminal:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml --robot perseverance
```

In the separate ROS terminal, pass `robot:=perseverance` and the same `config:=configs/config.yaml` to the [companion launch command]({{ "/guide/quickstart/#3-select-another-rover" | relative_url }}). Keep system ROS out of the Isaac terminal.

The profile is [perseverance.yaml](https://github.com/kimhoyun-robotair/MarsLab/blob/main/configs/robots/perseverance.yaml). It selects:

- USD: `assets/robots/perseverance/m2020_lidar.usda`
- URDF: `assets/robots/perseverance/m2020_lidar.urdf`
- Namespace: `/rover`

## Sensor inventory

**RGB, synthetic depth, 2-D/3-D LiDAR, IMU.** The primary camera uses `/rover/rgb/image_raw` and `/rover/rgb/camera_info`. Additional cameras use `/rover/cameras/<name>/image_raw` and `/rover/cameras/<name>/camera_info`.

| Camera | Mount link | Resolution |
| --- | --- | --- |
| Primary research camera (primary) | `Body_Chassis` | 640 × 480 |


IMU sampling is configured at **30 Hz**. This is an acquisition setting, not a guarantee of the observed ROS publication rate. Camera topics use best-effort QoS in the supplied profile.

## Mobility settings

These values describe the checked-in simulation profile, not measured flight performance. Geometry is shown to at most six decimal places; the profile retains the exact values.

| Setting | Profile value |
| --- | --- |
| Wheel radius | 0.2667 m |
| Wheelbase | 2.26 m |
| Corner-wheel track | 2.125 m |
| Middle-wheel track | 2.369 m |
| Maximum linear command | 4.0 m/s |
| Maximum angular command | 0.7 rad/s |
| Drive mode | `acceleration` |

The controller uses six driven wheels and four steerable corners. It supports curved driving and pivot turns. Wheel odometry uses the same geometry. See [control]({{ "/reference/control/" | relative_url }}) and [physics]({{ "/reference/physics/" | relative_url }}) before tuning.

## Model assumptions and provenance

The M2020 source attribution is recorded in the [asset notice](https://github.com/kimhoyun-robotair/MarsLab/blob/main/assets/robots/perseverance/LICENSE.md). LiDAR attachments and synthetic depth are simulation additions. The research camera uses a 135° horizontal pinhole field of view with a 0.3–200 m clipping interval; its position is anchored at the source Navcam mast reference.

Authored masses are retained, with geometry-based center-of-mass and inertia estimates. Those estimates and added LiDAR masses are detailed in [rover physics]({{ "/reference/physics/" | relative_url }}).

See [model assumptions]({{ "/reference/model-assumptions/" | relative_url }}) for the distinction between source data, estimates and numerical choices.

## Related reference

- [Camera, LiDAR and IMU output]({{ "/reference/sensors/" | relative_url }})
- [ROS topics and frame ownership]({{ "/reference/ros2/" | relative_url }})
- [Scenario overrides and path resolution]({{ "/reference/configuration/" | relative_url }})
