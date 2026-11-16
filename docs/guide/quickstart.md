---
title: First run
description: Start a rover scenario and connect the ROS companion in a separate terminal.
permalink: /guide/quickstart/
---

Complete [installation]({{ "/guide/installation/" | relative_url }}) first, including the scene download. Run all commands below from the repository root.

## 1. Start Isaac Sim

Use a terminal where system ROS has **not** been sourced:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```

The supplied scenario selects Perseverance and Jezero Plain. The launcher uses Isaac Sim's bundled Python and its bundled Jazzy bridge libraries. It defaults to `$HOME/isaacsim`; set `ISAAC_SIM_PATH` when your installation is elsewhere.

The runtime validates configuration and required assets before Isaac starts, then creates the world, loads terrain and rover assets, and initializes control and sensing. See [architecture]({{ "/development/" | relative_url }}) for the complete startup sequence.

## 2. Start the ROS companion

With `runtime.ros2_enabled: true`, open a **separate terminal**:

```bash
source /opt/ros/jazzy/setup.bash
.venv/bin/python /opt/ros/jazzy/bin/ros2 launch \
  launch/rover_state_publisher.launch.py
```

The companion reads the same scenario and selected profile to load the URDF and publish the articulation TF chain. Keep both `launch/rover_state_publisher.launch.py` and `launch/companion_urdf.py` together.

Use the same `ROS_DOMAIN_ID` in the simulator, companion and viewers. Sensor data is published by Isaac; `robot_state_publisher` supplies robot description and transforms.

## 3. Select another rover

For example, select Curiosity in the Isaac terminal:

```bash
marslab/isaac_python.sh marslab/main.py \
  --config configs/config.yaml --robot curiosity
```

Pass the matching selection to the ROS companion:

```bash
source /opt/ros/jazzy/setup.bash
.venv/bin/python /opt/ros/jazzy/bin/ros2 launch \
  launch/rover_state_publisher.launch.py \
  config:=configs/config.yaml robot:=curiosity
```

Accepted names are `perseverance`, `spirit`, `opportunity` and `curiosity`. With no override, both processes follow the scenario's `robot` field. Compare their [sensor profiles]({{ "/robots/" | relative_url }}) before configuring downstream consumers.

## 4. Inspect the primary camera

The primary navigation image is `/rover/rgb/image_raw`, with calibration at `/rover/rgb/camera_info`. Additional cameras use `/rover/cameras/<name>/image_raw` and `/rover/cameras/<name>/camera_info`.

In RViz, set the Image display's reliability to **Best Effort**. To inspect a primary image header from a ROS-sourced terminal without printing the pixel array:

```bash
ros2 topic echo /rover/rgb/image_raw --qos-reliability best_effort --once --no-arr
```

## Next steps

- [Choose another scene]({{ "/reference/scenes/" | relative_url }}) and check initial contact and clearance.
- Connect a controller to `/rover/cmd_vel`; [command timeout and steering behavior]({{ "/reference/control/" | relative_url }}) determine how the rover responds.
- Read the [ROS 2 and TF contract]({{ "/reference/ros2/" | relative_url }}) before integrating localization.
- Use [troubleshooting]({{ "/guide/troubleshooting/" | relative_url }}) for startup, image and transform issues.
