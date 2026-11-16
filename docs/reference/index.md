---
title: Technical reference
description: Configuration, physics, sensing and interface contracts for repeatable MarsLab experiments.
permalink: /reference/
---

Start with [configuration composition]({{ "/reference/configuration/" | relative_url }}) to understand how scenario settings and robot profiles combine. Numeric sensor examples describe the default Perseverance research profile unless stated otherwise.

| Area | Read this when you need to… |
| --- | --- |
| [Configuration]({{ "/reference/configuration/" | relative_url }}) | Select a profile, override values or diagnose validation. |
| [Scenes and spawning]({{ "/reference/scenes/" | relative_url }}) | Load terrain and place the rover with surface clearance. |
| [Runtime modes]({{ "/reference/runtime/" | relative_url }}) | Choose GUI/headless, ROS and atmosphere behavior. |
| [Atmosphere]({{ "/reference/atmosphere/" | relative_url }}) | Set dust, sunlight and dynamic atmosphere controls. |
| [Rendering]({{ "/reference/rendering/" | relative_url }}) | Choose ray/path tracing, DLAA/DLSS and fog settings. |
| [Rover physics]({{ "/reference/physics/" | relative_url }}) | Understand mass properties, friction, contact and suspension. |
| [Rover control]({{ "/reference/control/" | relative_url }}) | Tune steering, wheel drives, command limits and pivot turns. |
| [Sensors]({{ "/reference/sensors/" | relative_url }}) | Configure cameras, depth, LiDAR and IMU output. |
| [ROS 2 and TF]({{ "/reference/ros2/" | relative_url }}) | Connect consumers with compatible topics, QoS and frames. |
| [Wheel odometry]({{ "/reference/odometry/" | relative_url }}) | Configure the encoder-derived estimate and TF ownership. |
| [Model assumptions]({{ "/reference/model-assumptions/" | relative_url }}) | Distinguish source data, approximations and simulation tuning. |

The checked-in [scenario](https://github.com/kimhoyun-robotair/MarsLab/blob/main/configs/config.yaml), [profiles](https://github.com/kimhoyun-robotair/MarsLab/tree/main/configs/robots) and [strict schemas](https://github.com/kimhoyun-robotair/MarsLab/tree/main/marslab/config/schema) define runtime settings. Examples show edits to existing YAML blocks; do not append duplicate top-level keys.
