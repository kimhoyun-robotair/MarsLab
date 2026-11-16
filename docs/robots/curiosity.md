---
title: Curiosity
description: Curiosity profile selection, sensor inventory, mobility settings and simulation assumptions.
permalink: /robots/curiosity/
---

**Available in main · Mars Science Laboratory**

Curiosity provides seventeen rendered camera models, including cameras on mast and arm mounting links. The profile retains mount-specific sensor poses and uses the shared six-wheel driving controller.

## Select this rover

After [installation]({{ "/guide/installation/" | relative_url }}), run from the repository root in the Isaac terminal:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml --robot curiosity
```

In the separate ROS terminal, pass `robot:=curiosity` and the same `config:=configs/config.yaml` to the [companion launch command]({{ "/guide/quickstart/#3-select-another-rover" | relative_url }}). Keep system ROS out of the Isaac terminal.

The profile is [curiosity.yaml](https://github.com/kimhoyun-robotair/MarsLab/blob/main/configs/robots/curiosity.yaml). It selects:

- USD: `assets/robots/curiosity/curiosity.usda`
- URDF: `assets/robots/curiosity/curiosity.urdf`
- Namespace: `/rover`

## Sensor inventory

**RGB cameras, IMU; no LiDAR or synthetic depth.** The primary camera uses `/rover/rgb/image_raw` and `/rover/rgb/camera_info`. Additional cameras use `/rover/cameras/<name>/image_raw` and `/rover/cameras/<name>/camera_info`.

| Camera | Mount link | Resolution |
| --- | --- | --- |
| navcam_left_a (primary) | `Body_MastTilt` | 1024 × 1024 |
| mastcam_left | `Body_MastTilt` | 1648 × 1200 |
| mastcam_right | `Body_MastTilt` | 1648 × 1200 |
| navcam_right_a | `Body_MastTilt` | 1024 × 1024 |
| navcam_left_b | `Body_MastTilt` | 1024 × 1024 |
| navcam_right_b | `Body_MastTilt` | 1024 × 1024 |
| hazcam_front_left_a | `Body_Chassis` | 1024 × 1024 |
| hazcam_front_right_a | `Body_Chassis` | 1024 × 1024 |
| hazcam_front_left_b | `Body_Chassis` | 1024 × 1024 |
| hazcam_front_right_b | `Body_Chassis` | 1024 × 1024 |
| hazcam_rear_left_a | `Body_Chassis` | 1024 × 1024 |
| hazcam_rear_right_a | `Body_Chassis` | 1024 × 1024 |
| hazcam_rear_left_b | `Body_Chassis` | 1024 × 1024 |
| hazcam_rear_right_b | `Body_Chassis` | 1024 × 1024 |
| chemcam_rmi | `Body_MastTilt` | 1024 × 1024 |
| mahli | `Body_ArmTurret` | 1648 × 1200 |
| mardi | `Body_Chassis` | 1648 × 1200 |


IMU sampling is configured at **8 Hz**. This is an acquisition setting, not a guarantee of the observed ROS publication rate. Camera topics use best-effort QoS in the supplied profile.

## Mobility settings

These values describe the checked-in simulation profile, not measured flight performance. Geometry is shown to at most six decimal places; the profile retains the exact values.

| Setting | Profile value |
| --- | --- |
| Wheel radius | 0.25 m |
| Wheelbase | 2.26 m |
| Corner-wheel track | 2.125 m |
| Middle-wheel track | 2.382506 m |
| Maximum linear command | 4.0 m/s |
| Maximum angular command | 0.7 rad/s |
| Drive mode | `acceleration` |

The controller uses six driven wheels and four steerable corners. It supports curved driving and pivot turns. Wheel odometry uses the same geometry. See [control]({{ "/reference/control/" | relative_url }}) and [physics]({{ "/reference/physics/" | relative_url }}) before tuning.

## Model assumptions and provenance

The profile records NASA/JPL NAIF instrument-kernel URLs for its camera calibration. MarsLab authored the articulated simulation using source visual and engineering data. Rendering uses pinhole cameras; CAHVOR/E lens distortion and detector physics are omitted.

The chassis-reference IMU and zero sensor/encoder noise are idealizations. Drive gains, contact parameters, command caps and near clips are simulation tuning. LiDAR acquisition and synthetic depth are disabled in this profile.

MAHLI placement includes a visual-geometry mounting approximation. Mast-camera poses are relative to `Body_MastTilt`, and MAHLI is relative to `Body_ArmTurret`; these links define sensor mounts, not a documented arm-teleoperation interface.

See [model assumptions]({{ "/reference/model-assumptions/" | relative_url }}) for the distinction between source data, estimates and numerical choices.

## Related reference

- [Camera, LiDAR and IMU output]({{ "/reference/sensors/" | relative_url }})
- [ROS topics and frame ownership]({{ "/reference/ros2/" | relative_url }})
- [Scenario overrides and path resolution]({{ "/reference/configuration/" | relative_url }})
