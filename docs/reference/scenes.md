---
title: Scenes and spawning
description: Select a terrain and place the rover with the intended clearance.
permalink: /reference/scenes/
---

## `scene.usdz_path`

Selects the supplied Mars scene. A relative path resolves from the declaring
scenario's directory (`configs/` for the supplied scenario).
The path must point to an existing USDZ file before Isaac starts.

Download the scene assets as described in the [README]({{ "/guide/installation/#download-the-mars-scenes" | relative_url }}).
The reference scenes use these paths:

| Scene | Value in `configs/config.yaml` |
| --- | --- |
| Jezero Plain (supplied default) | `../assets/scene/jezero_plain/jezero_plain.usdz` |
| Main Crater | `../assets/scene/main_crater/main_crater.usdz` |
| Grand Canyon | `../assets/scene/grand_canyon/grand_canyon.usdz` |
| Mars Base | `../assets/scene/mars_base/mars_base.usdz` |

For example, to select Main Crater, change the existing field:

```yaml
scene:
  usdz_path: ../assets/scene/main_crater/main_crater.usdz
```

Then run the canonical launcher with `configs/config.yaml`. Runtime reads the
scene's meshes and collision data from USD; it does not require a neighboring
DEM, generation recipe, or `metadata.json`. Recheck rover spawn and contact
when selecting another terrain.

## `rover.spawn.mode`

| Mode | Meaning | When to use it |
| --- | --- | --- |
| `dem_center` | Place the rover at the sampled terrain center. | Recommended starting mode for a new scene. |
| `dem_relative` | Offset the rover from the terrain-derived reference. | Repeatable tests near a known terrain feature. |
| `absolute` | Use the configured world-space position directly. | Precisely surveyed or externally defined poses. |

`xy` provides the horizontal position or offset. `z_offset` adds clearance above
the sampled surface, and `orientation_rpy` sets roll, pitch, and yaw in radians.
Before the first physics step, runtime sweeps bounds of the actual rover
colliders against the scene and raises the initial height where needed to
preserve that clearance over the whole footprint. This includes slopes and
scene obstacles. A position with no scene support below the footprint fails
startup. Use a small positive `z_offset` for initial settling under gravity.

Hidden rock-library prototypes outside a PointInstancer are referenced beneath
that instancer in the session layer. Their standalone originals are disabled,
preserving the placed rocks without invisible colliders at the library origin.
The source scene package is unchanged.
