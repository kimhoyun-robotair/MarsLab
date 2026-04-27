# MarsLab — TF Frame Conventions

**Status:** v1.0 published behaviour.  Future releases may align fully with REP-103 once a USD-level rotation pass replaces the spawn-time X-roll.

This page documents the coordinate-frame conventions every MarsLab user
needs when authoring sensor extrinsics, integrating SLAM/Nav2, or
attaching new payloads.

---

## TL;DR

* The rover **spawns with a 180° X-roll** applied to `/World/Rover`.
  This is **intentional** — it compensates for the NASA JPL m2020 URDF's
  non-standard link frame author convention.
* As a result, the published `base_link` frame has
  `RPY ≈ (180°, 0°, 0°)` relative to `odom`, **not** `RPY ≈ (0, 0, 0)`.
* Sensor mount values in `configs/robots/rover_m2020.yaml` and
  `configs/sensors/*.yaml` are authored in the **X-rolled body frame**:
  * `+Z_yaml` corresponds to `-Z_world` (i.e. **Z_yaml is "down"**).
  * `+Y_yaml` corresponds to `-Y_world` (i.e. **Y_yaml is "right"**).
  * `+X_yaml` corresponds to `+X_world` (forward, unchanged).
* `tf_broadcaster.py` broadcasts these YAML values **identity** (no
  flip).  The X-roll on the spawn root is the single canonical
  rotation.
* RViz `RobotModel` mesh visualisation is **correct** despite the
  X-roll because the URDF kinematic chain is consistent with the
  X-rolled `base_link`.
* SLAM (slam_toolbox) and Nav2 stacks tested against MarsLab v1.0 work
  correctly with this convention.

---

## Why is `base_link` X-rolled?

Two layers explain the convention.

### NASA JPL m2020 URDF link frame author style

`assets/m2020-urdf-models/rover/m2020.urdf` is the NASA JPL
public-release URDF (commit `47e8686b`, 2021-08-16).  Its link frames
were authored in a non-standard convention:

* `Body_Chassis` link's `<inertial origin xyz="0.09002 0 -1.13338"/>`
  declares the chassis CoM at `z = -1.13` relative to the link frame.
* All wheel link origins are at the chassis-frame `-Z` direction
  (e.g. `Body_WheelLeftFront` is at chassis-frame
  `(1.185, -1.062, -0.263)`).
* USD inspection (`pxr.UsdGeom.Xformable.GetOrderedXformOps`)
  confirms every chassis prim has identity rotation (`xformOp:orient
  = (1, 0, 0, 0)`) -- so the offset comes from the URDF link frame
  author, not from any baked rotation in the converted USD.

Read together, the URDF author treats the **chassis link's `+Z` axis as
"into the rover's underside"** -- i.e. *down* relative to the world
when the rover sits upright.  This is the opposite of REP-103
(`+Z = up`).  Empirical TF evidence (`odom → base_link RPY ≈
[-179.488°, ...]`) is consistent with this reading.

### Why not "fix" the URDF or the USD?

The URDF is upstream-frozen NASA / JPL public release; modifying it
breaks reproducibility and round-tripping with future JPL updates.  A
USD-level axis rotation would require modifying every link prim in
the converted USD, which is fragile across Isaac Sim importer
changes.  The simplest, most localised compensation is a single
`spawn_orientation_rpy = [π, 0, 0]` on `/World/Rover` that flips the
whole chain in one place.

This is documented in `configs/robots/rover_m2020.yaml`'s spawn block.

### Where the X-roll is applied

| Site | What it does | File |
|---|---|---|
| `rover_m2020.yaml` `spawn_orientation_rpy: [3.14159, 0, 0]` | Stage-1 default | `configs/robots/rover_m2020.yaml` |
| `rover_m2020.yaml` `spawn.orientation_rpy: [3.14159, 0, 0]` | Default scenario spawn | `configs/robots/rover_m2020.yaml` |
| Scenario YAML `spawn.orientation_rpy: [3.14159, 0, …yaw]` | Per-scenario spawn pose | `configs/scenarios/*.yaml` |
| `apply_spawn_pose(stage, /World/Rover, spawn_xyz, rpy)` | Writes the X-roll quat to the USD root Xform | `marslab/robots/rover.py` |
| `articulation.set_world_poses(positions=[spawn_xyz], orientations=[wxyz from spawn_rpy])` | Pins the PhysX articulation root pose to the same X-roll | `scripts/phase1/main.py` |

The two writes are kept consistent by sourcing both from the same YAML
`spawn_orientation_rpy` -- a single source of truth.

---

## Sensor extrinsic authoring rules

When authoring `local_translation` for a new sensor in
`configs/robots/rover_m2020.yaml` or a `configs/sensors/<preset>.yaml`:

* Author the value in the **X-rolled body frame** (matches
  `apply_spawn_pose`).
* Mast-top sensors take **negative Z** (e.g. NavCam at `z = -2.1` for
  ~2.1 m above the chassis).
* Chassis-roof sensors take **negative Z** of smaller magnitude
  (e.g. lidar_3d at `z = -0.5`).
* Left-side sensors take **negative Y** (e.g. left NavCam at
  `y = -0.21`).
* Right-side sensors take **positive Y** (mirror of left).
* Forward-mounted sensors take **positive X** (forward of chassis
  origin).
* `tf_broadcaster.publish_static_sensor_tfs` broadcasts these values
  **identity** (no flip) -- the X-roll on the spawn root applies once
  across the whole frame chain.

A common mistake (which produces a `ΔZ = 2|z|` symptom) is to apply a
Y/Z flip both at the spawn root *and* in `tf_broadcaster.py`.  Don't.
Use `spawn_orientation_rpy` only.

---

## ROS REP-103 / REP-105 compliance

* **`/odom` and `/odom_anchor` (= "odom" frame_id):**  REP-105
  compliant.  Identity orientation, located at the rover's spawn
  pose.
* **`base_link`:**  intentionally **X-rolled** as documented above.
  Downstream consumers that assume strict REP-103 (`+Z_base_link`
  pointing up in the world) need to apply an inverse 180° X-roll
  before consuming `base_link`-anchored data.  The MarsLab v1.0
  SLAM/Nav2 reference stack does this implicitly via the URDF
  kinematic chain.
* **`camera_optical_frame`:**  REP-105 optical frame
  (Z forward / X right / Y down) published by
  `tf_broadcaster.build_camera_optical_frame_transform`.  Use this
  frame_id in image / depth / pointcloud messages, not
  `camera_link`.
* **`/tf_raw` vs `/tf`:**  the OmniGraph `ROS2PublishTransformTree`
  publishes the kinematic chain on `/tf_raw`; the rclpy
  `TransformBroadcaster` (when enabled) publishes
  `odom → base_link` on `/tf`.  These two streams are kept separate
  by design -- never merge them in code.  Users wanting a single `/tf`
  topic can run `ros2 run topic_tools relay /tf_raw /tf` externally.

---

## Worked example: adding a new mast-mounted sensor

Suppose you want to add a high-resolution science camera at 2.4 m
above the chassis, slightly to the left (-0.15 m), pointing forward
(+X) at the same yaw as the rover.

In `configs/robots/rover_m2020.yaml` `sensors:` block, add:

```yaml
sensors:
  ...
  science_cam:
    parent_link: "Body_Chassis"
    # X-rolled body frame: -Z = up, -Y = left.  See
    # docs/frame_conventions.md.
    local_translation: [0.3, -0.15, -2.4]
    local_orientation_rpy_deg: [180.0, 0.0, 0.0]   # match camera convention
    resolution: [1920, 1080]
    focal_length: 35.0
    clipping_range: [0.5, 1500.0]
```

Then add a `sensor_spawner` hook (or extend the existing camera path)
to spawn the new prim and a TF entry.  The single source of truth is
the YAML.

---

## Future polish backlog

TF-frame-related items deferred to future releases:

* Replace the spawn-time X-roll with a USD-level chassis prim
  rotation, so `base_link` lands at REP-103 identity.  Removes the
  X-rolled body frame mental tax for new contributors and re-aligns
  with external ROS packages that hard-code REP-103 expectations.
* Calibrate sensor `local_translation` to NASA / JPL flight-pose
  values once a credible source is found (current values are
  empirical-working ballparks).
* Strip the unresolved-reference cosmetic warnings in
  `m2020_physics.usd` `/visuals/Frame_*` references.

---

## References

* `configs/robots/rover_m2020.yaml` spawn block comments.
* `marslab/ros2_bridge/tf_broadcaster.py` docstring.
* USD inspection script: `python3 -c "from pxr import Usd, UsdGeom;
  s = Usd.Stage.Open('assets/robots/rover/m2020.usd'); ..."` --
  reproduces the chassis prim identity orient finding.
* ROS REP-103: <https://www.ros.org/reps/rep-0103.html>
* ROS REP-105: <https://www.ros.org/reps/rep-0105.html>
