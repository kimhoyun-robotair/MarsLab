---
title: Architecture
description: Configuration, startup, ownership and source layout in the MarsLab runtime.
permalink: /development/
---

MarsLab separates configuration, simulation setup and runtime ownership. The web documentation is built independently; browsing these pages does not run Isaac Sim or ROS.

## Runtime flow

```text
Scenario YAML + selected robot profile
                  ↓
Configuration composition and strict validation
                  ↓
Asset checks → Isaac Sim → World and terrain
                  ↓
Rover physics → sensing → optional ROS bridge
                  ↓
Simulation / control / publication loop
                  ↓
Reverse-order cleanup
```

## Startup sequence

1. Compose the scenario and selected robot profile, then strictly validate them.
2. Resolve asset paths relative to each declaring YAML and check required files.
3. Start Isaac Sim and create the Mars world.
4. Reference the selected terrain and rover USD assets.
5. Apply YAML-owned rover physics and create the configured camera, IMU, and optional LiDAR sensors.
6. Initialize optional atmosphere GUI and ROS 2 interfaces.
7. Enter the simulation, control, sensing, and publication loop.

The World owns one PhysicsScene with the configured Mars gravity. PhysicsScenes
inside the referenced terrain are disabled in the runtime session layer, and
their effective simulation owners are redirected to the World scene.
The input assets remain unchanged.


## Ownership boundaries

| Owner | Responsibility |
| --- | --- |
| Scenario | Environment, runtime switches and experiment overrides. |
| Rover profile | Geometry, joint names, drives, sensors and ROS settings. |
| Authored USD | Visuals, collision geometry, articulation and mass properties. |
| Runtime | Compose the world, apply settings, step simulation and release resources. |
| ROS companion | Robot description, articulation TF and root-to-base identity transform. |
| MarsLab ROS bridge | Sensor output, static sensor frames, ground truth and optional odometry TF. |

Ground truth owns no TF. `wheel_odom.publish_tf` gates the dynamic `odom → base_link` transform. Read the [complete ROS ownership contract]({{ "/reference/ros2/" | relative_url }}) when integrating an external estimator.

## Source layout

```text
MarsLab/
├── README.md
├── configs/
│   ├── config.yaml                 # Scenario and robot selector
│   └── robots/                     # Rover geometry, dynamics, and sensor profiles
├── assets/
│   ├── scene/                      # Downloaded Mars terrain USDZ inputs
│   ├── robots/                     # Rover USD, URDF, meshes, and physics layers
│   ├── mars_sky/                   # Sky-dome image assets
│   └── atmosphere/                 # Model references and scope
├── launch/
│   ├── rover_state_publisher.launch.py
│   └── companion_urdf.py           # Companion URDF preparation
├── docs/                           # GitHub Pages site, Markdown docs and browser demo
├── marslab/
│   ├── main.py                     # Runtime entry point
│   ├── isaac_python.sh             # Isaac Python launcher
│   ├── config/                     # YAML loading and strict schemas
│   ├── environment/                # Isaac-free Mars calculations
│   ├── gui/                        # AtmospherePanel
│   ├── rendering/                  # Sky, sun, fog, and render settings
│   ├── robots/                     # Rover physics and control
│   ├── ros2_bridge/                # Topics, QoS, TF, and odometry
│   ├── runtime/                    # Assembly, loop, and cleanup lifecycle
│   ├── sensors/                    # Camera, IMU, and 2-D/3-D LiDAR
│   └── sim/                        # SimulationApp and world bootstrapping
└── requirements.txt                # Python dependencies for runtime and companion tools
```

## Extending MarsLab

Start with [adding a rover]({{ "/development/adding-a-rover/" | relative_url }}) for a compatible six-wheel platform. The [roadmap]({{ "/development/roadmap/" | relative_url }}) tracks broader directions.

Configuration and pure calculations can be checked without Isaac. Physics, rendering, sensing, ROS timing and cleanup must also be observed in the real runtime.
