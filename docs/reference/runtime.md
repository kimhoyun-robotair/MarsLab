---
title: Runtime modes
description: Configure headless operation, ROS 2, atmosphere and motion tracking.
permalink: /reference/runtime/
---

| Key | Recommended use |
| --- | --- |
| `runtime.headless: false` | Interactive GUI development and AtmospherePanel inspection. |
| `runtime.headless: true` | Unattended or remote runs where no GUI is required. |
| `runtime.ros2_enabled: true` | Publish retained ROS interfaces and accept `/cmd_vel`. |
| `runtime.ros2_enabled: false` | Isolate Isaac scene, physics, or rendering issues. |
| `runtime.atmosphere_enabled: true` | Enable Mars sky, sun, fog, and optional GUI control. |
| `runtime.atmosphere_enabled: false` | Use the fallback scene light and reduce atmosphere complexity. |
| `runtime.enable_motion_bvh: true` | Enable RTX geometry-motion tracking for moving LiDAR; defaults to `true`. |

Headless mode prevents the GUI panel from being created. It does not redefine
sensor, physics, or ROS ownership.

`enable_motion_bvh` enables the renderer's motion acceleration structure. Keep
it enabled when the rover or scene objects move. It does not enable scan
deskewing or change the LiDAR output to motion-compensated coordinates.
