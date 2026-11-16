---
title: Spirit
description: Spirit profile selection, sensor inventory, mobility settings and simulation assumptions.
permalink: /robots/spirit/
---

**Available in main · Mars Exploration Rover · MER-2**

Spirit uses the shared MER mobility geometry with its own retained camera calibration. The supplied profile provides nine rendered camera models and an idealized IMU.

## Select this rover

After [installation]({{ "/guide/installation/" | relative_url }}), run from the repository root in the Isaac terminal:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml --robot spirit
```

In the separate ROS terminal, pass `robot:=spirit` and the same `config:=configs/config.yaml` to the [companion launch command]({{ "/guide/quickstart/#3-select-another-rover" | relative_url }}). Keep system ROS out of the Isaac terminal.

The profile is [spirit.yaml](https://github.com/kimhoyun-robotair/MarsLab/blob/main/configs/robots/spirit.yaml). It selects:

- USD: `assets/robots/spirit/spirit.usda`
- URDF: `assets/robots/spirit/spirit.urdf`
- Namespace: `/rover`

## Sensor inventory

**RGB cameras, IMU; no LiDAR or synthetic depth.** The primary camera uses `/rover/rgb/image_raw` and `/rover/rgb/camera_info`. Additional cameras use `/rover/cameras/<name>/image_raw` and `/rover/cameras/<name>/camera_info`.

| Camera | Mount link | Resolution |
| --- | --- | --- |
| navcam_left (primary) | `Body_Chassis` | 1024 × 1024 |
| navcam_right | `Body_Chassis` | 1024 × 1024 |
| pancam_left | `Body_Chassis` | 1024 × 1024 |
| pancam_right | `Body_Chassis` | 1024 × 1024 |
| hazcam_front_left | `Body_Chassis` | 1024 × 1024 |
| hazcam_front_right | `Body_Chassis` | 1024 × 1024 |
| hazcam_rear_left | `Body_Chassis` | 1024 × 1024 |
| hazcam_rear_right | `Body_Chassis` | 1024 × 1024 |
| microscopic_imager | `Body_Chassis` | 1024 × 1024 |


IMU sampling is configured at **8 Hz**. This is an acquisition setting, not a guarantee of the observed ROS publication rate. Camera topics use best-effort QoS in the supplied profile.

## Mobility settings

These values describe the checked-in simulation profile, not measured flight performance. Geometry is shown to at most six decimal places; the profile retains the exact values.

| Setting | Profile value |
| --- | --- |
| Wheel radius | 0.13 m |
| Wheelbase | 1.212032 m |
| Corner-wheel track | 1.060973 m |
| Middle-wheel track | 0.950000 m |
| Maximum linear command | 4.0 m/s |
| Maximum angular command | 0.7 rad/s |
| Drive mode | `acceleration` |

The controller uses six driven wheels and four steerable corners. It supports curved driving and pivot turns. Wheel odometry uses the same geometry. See [control]({{ "/reference/control/" | relative_url }}) and [physics]({{ "/reference/physics/" | relative_url }}) before tuning.

## Model assumptions and provenance

The profile records NASA/JPL NAIF instrument-kernel URLs for its camera calibration. MarsLab authored the articulated simulation using source visual and engineering data. Rendering uses pinhole cameras; CAHVOR/E lens distortion and detector physics are omitted.

The chassis-reference IMU and zero sensor/encoder noise are idealizations. Drive gains, contact parameters, command caps and near clips are simulation tuning. LiDAR acquisition and synthetic depth are disabled in this profile.

The Microscopic Imager mount uses a fixed stowed-arm geometry approximation. Calibration data supplies the optical model, not a flight-validated mount survey.

See [model assumptions]({{ "/reference/model-assumptions/" | relative_url }}) for the distinction between source data, estimates and numerical choices.

## Related reference

- [Camera, LiDAR and IMU output]({{ "/reference/sensors/" | relative_url }})
- [ROS topics and frame ownership]({{ "/reference/ros2/" | relative_url }})
- [Scenario overrides and path resolution]({{ "/reference/configuration/" | relative_url }})
