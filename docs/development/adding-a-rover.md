---
title: Adding a rover
description: Integration points and validation responsibilities for another compatible rover profile.
permalink: /development/adding-a-rover/
---

The current rover controller assumes six wheel drives and four steerable corner wheels. A new compatible rover can reuse it through geometry and joint mappings. Other mobility types require runtime and schema changes.

## 1. Prepare coherent assets

Provide the USD articulation, companion URDF, meshes, textures and required layers under `assets/robots/<name>/`. Keep coordinate conventions, joint names, camera mounts, collision shapes and mass properties consistent across USD and URDF. Record source provenance and model assumptions.

Asset conversion and automatic rebuild tools are not part of the distributed runtime.

## 2. Add a profile

Create `configs/robots/<name>.yaml` containing exactly one `rover` mapping. Its `name` must match the selector. Declare asset paths relative to that profile, normally beginning with `../../assets/`.

Supply the geometry, wheel and steering joint order, chassis and suspension mapping, sensors, ROS settings and wheel-odometry settings. Follow a compatible existing profile; camera calibration is specific to the model.

## 3. Register the selector

The accepted names are explicit in [`ROBOT_NAMES`](https://github.com/kimhoyun-robotair/MarsLab/blob/main/marslab/config/yaml_loader.py). Merely creating a YAML file does not add a CLI choice. Inspect corresponding schema constraints and the companion's selection path when extending the accepted set.

Mappings merge recursively with scenario overrides; lists replace whole lists. Keep robot geometry in the profile rather than copying it into a common scenario.

## 4. Validate the integration

First check configuration loading, asset paths and joint ordering. Then use Isaac Sim and ROS to verify:

- Spawn clearance, contact, mass properties and passive suspension coupling.
- Drive response, pivot-turn feasibility, braking and command timeout.
- Camera mounting poses, intrinsics and rendered geometry.
- Optional sensor presence, topic publication and QoS.
- URDF articulation, static sensor frames and odometry TF ownership.
- Stop/Play resets and cleanup behavior.

See [rover physics]({{ "/reference/physics/" | relative_url }}), [control]({{ "/reference/control/" | relative_url }}) and [ROS 2 and TF]({{ "/reference/ros2/" | relative_url }}) for the relevant contracts.

## 5. Document the profile

Add a robot page using the existing structure: status and selection, sensor inventory, mobility settings, provenance and assumptions, then shared reference links. Update the comparison table and homepage summary. Describe implementation limits alongside the supported features.
