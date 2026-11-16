---
title: Configuration
description: Compose a scenario with a rover profile and understand overrides and validation.
permalink: /reference/configuration/
---

MarsLab combines a scenario such as [`configs/config.yaml`](https://github.com/kimhoyun-robotair/MarsLab/blob/main/configs/config.yaml)
with the rover profile selected by its `robot` field. Profiles live in
[`configs/robots/`](https://github.com/kimhoyun-robotair/MarsLab/blob/main/configs/robots/). Relative asset paths resolve from the
directory containing the YAML that declares them, so the repository can be
cloned anywhere without changing paths for a particular computer.

Runtime loads a prebuilt scene through `scene.usdz_path`. Terrain generation,
asset conversion, and experiment/evaluation tools are outside this distribution.
The configuration controls loading, rover dynamics, sensing, lighting, and ROS
interfaces.

The configuration is validated with strict Pydantic schemas before Isaac Sim
starts. Unknown keys, invalid types, out-of-range values, missing required
assets, and incompatible option combinations stop the launch early.


## Recommended tuning workflow

1. Start from the supplied `configs/config.yaml`.
2. Change one subsystem at a time.
3. Keep units and frame ownership unchanged unless every consumer is updated.
4. Run the canonical command after each meaningful change.
5. Use source/config checks for early validation, then verify Isaac and ROS
   behavior in the real runtime.

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```

The supplied scenario selects `robot: perseverance`; its existing M2020 values
are preserved in [`configs/robots/perseverance.yaml`](https://github.com/kimhoyun-robotair/MarsLab/blob/main/configs/robots/perseverance.yaml).
Additional optional fields use defaults declared in
`marslab/config/schema/`. When a field is omitted, inspect its schema before
assuming that the feature is disabled; omission normally selects a validated
default rather than removing the subsystem.


## Rover selection and overrides

Use `--robot` to override the scenario's selector for one run:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml --robot perseverance
```

The accepted names are `perseverance`, `spirit`, `opportunity`, and `curiosity`.
The selected `configs/robots/<name>.yaml` and its USD/URDF inputs must exist;
missing files fail before Isaac starts. Each profile contains one `rover`
mapping with a matching `name`. The controller, differential setup, and wheel
odometry consume that profile's geometry and joint names.

For example, run Curiosity with:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml --robot curiosity
```

| Profile | USD / companion URDF | Camera acquisition |
| --- | --- | --- |
| [perseverance.yaml](https://github.com/kimhoyun-robotair/MarsLab/blob/main/configs/robots/perseverance.yaml) | `assets/robots/perseverance/m2020_lidar.usda` / `m2020_lidar.urdf` | Existing single research camera, synthetic depth and LiDAR |
| [spirit.yaml](https://github.com/kimhoyun-robotair/MarsLab/blob/main/configs/robots/spirit.yaml) | `assets/robots/spirit/spirit.usda` / `spirit.urdf` | 9 camera models with NASA-derived intrinsics; primary left Navcam |
| [opportunity.yaml](https://github.com/kimhoyun-robotair/MarsLab/blob/main/configs/robots/opportunity.yaml) | `assets/robots/opportunity/opportunity.usda` / `opportunity.urdf` | 9 camera models with NASA-derived intrinsics; primary left Navcam |
| [curiosity.yaml](https://github.com/kimhoyun-robotair/MarsLab/blob/main/configs/robots/curiosity.yaml) | `assets/robots/curiosity/curiosity.usda` / `curiosity.urdf` | 17 camera models with NASA-derived intrinsics; primary left Navcam A |

These mission models use pinhole rendering of the retained calibration data.
Their camera positions and intrinsics differ by mission; Spirit and Opportunity
share a mobility geometry model. All four profiles default to
`control.max_linear_velocity: 4.0` m/s as a shared simulation command cap.

To override a profile value for a scenario, add only the relevant values to the
scenario's `rover` mapping:

```yaml
robot: perseverance
rover:
  spawn:
    z_offset: 0.15
  control:
    max_linear_velocity: 0.2
```

Mappings merge recursively; lists and scalar values replace the corresponding
profile value. Scenario overrides still apply when `--robot` selects another
profile, so keep robot-specific geometry in the profile. A relative path in a
profile is anchored to `configs/robots/`; a relative path in the scenario is
anchored to the scenario's own directory. The current working directory does
not change these asset paths.

Legacy configurations containing the complete `rover` mapping and no `robot`
selector remain supported. If `--robot` is supplied for such a file, the selected
profile replaces that old rover mapping in full, preventing dimensions or asset
paths from the legacy model from carrying into the selected rover.


## Top-level sections

| Section | What it controls | Good first adjustment |
| --- | --- | --- |
| `robot` | Rover profile selector | Choose the profile whose assets are installed. |
| `scene` | Terrain USDZ input | Select a supplied scene. |
| `runtime` | GUI/headless, ROS 2, atmosphere | Disable optional systems while diagnosing startup. |
| `mars_env` | Gravity, dust, sunlight, sol timing | Adjust dust and solar position for a scenario. |
| `rendering` | Renderer, sky, sun, fog | Choose speed or image quality. |
| `rover` | Optional profile overrides in a scenario | Tune only the relevant subsection. |
| `wheel_odom` | Dynamic odometry TF ownership | Decide whether MarsLab or an external estimator owns TF. |


## Validation boundary

Configuration and pure calculations can be checked without Isaac. Final rover
physics, renderer appearance, sensor output, ROS topic/QoS compatibility, TF
ownership, AtmospherePanel behavior, and cleanup must be observed in the user's
Isaac Sim and ROS environments.
