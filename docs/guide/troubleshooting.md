---
title: Troubleshooting
description: Diagnose startup, camera, ROS discovery, transform and rendering issues.
permalink: /guide/troubleshooting/
---

## Startup stops before the Isaac window opens

Read the first configuration or asset error. MarsLab validates the composed scenario and rover profile before creating Kit.

- Confirm `scene.usdz_path` points to a downloaded USDZ. It resolves relative to the YAML that declares it.
- Keep each rover's USD, URDF, meshes, materials and configuration layers together.
- Check spelling and types: unknown configuration keys are rejected.
- Use one of the four supported robot names. Ingenuity is not a selectable `main` profile.

See [configuration composition]({{ "/reference/configuration/" | relative_url }}) and [installation]({{ "/guide/installation/" | relative_url }}).

## Python packages or ROS bridge libraries cannot be found

The Isaac terminal and system ROS terminal use different Python environments. Install `requirements.txt` in each environment you use. Start Isaac through `marslab/isaac_python.sh`, and do not source system ROS in that terminal.

The companion commands use the system `.venv` created with `--system-site-packages`. Its packages do not install into Isaac's Python.

## RViz does not show camera images

Check that the simulation is playing, `runtime.ros2_enabled` is true and the selected camera exists. Use the same `ROS_DOMAIN_ID` across terminals. Supplied camera publishers use best-effort reliability, so a reliable subscriber will not match them. Set RViz Image reliability to **Best Effort**.

```bash
ros2 topic echo /rover/rgb/image_raw --qos-reliability best_effort --once --no-arr
```

## A depth or LiDAR topic is absent

Spirit, Opportunity and Curiosity omit LiDAR and disable synthetic depth in their supplied profiles. This is expected. The default Perseverance research profile enables those modalities. See [robot comparison]({{ "/robots/" | relative_url }}) and [sensors]({{ "/reference/sensors/" | relative_url }}).

`depth_sensor.enabled` enables depth **noise**; `depth_output` controls whether depth and point clouds are published.

## The robot description or TF tree looks wrong

Pass the same scenario and robot to Isaac and the ROS companion. Keep the companion helper beside its launch file so relative meshes are resolved correctly.

The companion owns the articulation tree. MarsLab owns retained sensor static transforms. Ground truth publishes no TF. When an external localization system owns `odom → base_link`, set `wheel_odom.publish_tf: false`. See [frame ownership]({{ "/reference/ros2/#ownership-and-qos" | relative_url }}).

## The rover stops despite a previous velocity command

The default command timeout is 0.5 simulated seconds. Send commands continuously while driving. A steering change can also brake the rover while its wheels align. See [rover control]({{ "/reference/control/" | relative_url }}).

## Viewport edges shimmer or flicker

The supplied configuration uses DLAA (`antialiasing_op: 4`). DLSS uses `3`. Change the existing `rendering.ray_tracing` block and restart. DLAA can cost more GPU memory; the observed improvement was tested with Isaac Sim 5.1 and an RTX 5090. See [rendering]({{ "/reference/rendering/#choosing-dlss-or-dlaa" | relative_url }}).

## Time moves backwards after Stop and Play

Stop resets the simulation clock, sensor freshness and episode state. ROS consumers must handle the next episode starting from zero. Pause preserves the existing episode. A fixed sensor seed does not guarantee deterministic GPU rendering or physics.
