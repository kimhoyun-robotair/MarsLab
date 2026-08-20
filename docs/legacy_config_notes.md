# Legacy configuration comment notes (reference only)

> **Reference-only / non-runtime documentation.** This page preserves the
> human-authored comments from the deleted files
> `configs/default.yaml` and `configs/rover_m2020.yaml` at source commit
> `3b83742a352468d675fa0dc9441ac1a25ba19208`. Neither legacy YAML file is an
> active input, and none of the examples below is a supported launch recipe.
> Use `configs/config.yaml` and the canonical command in `README.md` for runs.

The headings below retain the original file and nearby YAML key so a former
comment can be located without reviving the split configuration surface.

## `configs/default.yaml` (deleted)

### File header (lines 1–13; historical scenario/usage context)

> Canonical MarsLab scenario config.
>
> Experiment variants use CLI overrides (`--sun-azimuth-deg`,
> `--sun-elevation-deg`).
>
> This file replaces the six ship-with scenario YAMLs (`jezero_flat`,
> `jezero_crater`, `jezero_rocks`, `cerberus_canyon`,
> `cerberus_canyon_easy`, `spacecraft_landing`) and their shared `_base.yaml`
> include fragment.
>
> Terrain and scene blocks are absent because MarsLab consumes a supplied
> Scene USDZ package; scene authoring is not part of this configuration.

The deleted file introduced these lines with a `Usage:` label. The two old
`--usda` command lines were executable comments; they are retained here only
as historical provenance (not as supported commands):

```text
marslab/isaac_python.sh marslab/main.py --usda assets/scene/jezero_plain/jezero_plain.usdz
marslab/isaac_python.sh marslab/main.py --usda assets/scene/jezero_plain/jezero_plain.usdz \
    --sun-azimuth-deg 135 --sun-elevation-deg 40
```

## `configs/rover_m2020.yaml` (deleted)

### `spawn` and rover frame convention (lines 4–13)

> URDF link frame is REP-103 aligned (+X forward, +Y left, +Z up) since the
> 2026-05-04 FRD->REP-103 rewrite (rc1b_urdf_rep103). No X-roll spawn
> compensation is required; identity rpy spawns the rover upright.
>
> Spawn modes (consumed by `marslab.main._resolve_spawn`):
>
> - `dem_center` — spawn at DEM bbox centre. `xy` ignored.
> - `dem_relative` — spawn at `(dem_center_x + xy[0], dem_center_y + xy[1])`.
> - `absolute` — spawn at `(xy[0], xy[1])` in the world frame.
>
> In every mode, ground Z is sampled from the DEM at the resolved XY and the
> rover Z is set to `surface_z + z_offset`. `z_offset` here overrides the CLI
> `--z-offset` flag if present.

### `com_offset` (lines 20–30)

> Chassis CoM offset (m). Empirically determined +0.2 m forward shift.
>
> Even after the JPL URDF arm/turret/drill (~74 kg) was stripped, the chassis
> bbox-derived inertia tensor (computed about the geometric centre) does not
> match the real M2020 mass distribution — the electronics box / MMRTG /
> cabling sit forward of the wheelbase midpoint. Empirical evidence
> (`delete_later/imu_diagnostic/imu_stat.py`, 2026-05-04 run):
> `com_offset = [0, 0, 0]` yields stationary lin_x mean = +1.27 m/s² (~20 deg
> forward pitch); `com_offset = [0.2, 0, 0]` brings it down to +0.43 m/s² (~6.6
> deg). Keep the +0.2 value; further refinement is a v1.5 task (IMU
> diagnostic + chassis inertia re-tune).

### `chassis`, `wheels`, and `suspension` physics notes (lines 35–88)

> **M2020 ballpark physics override.** Values below are M2020 Perseverance
> order-of-magnitude correct (NOT exact). Speed/control limits stay user-
> tunable (see `control:` block); these blocks pin chassis mass / wheel mass /
> friction / inertia so the URDF auto-computed placeholders never reach PhysX.
> Sources cited inline.

Under `chassis.mass`:

> Total dry mass of M2020 Perseverance per NASA fact sheet (1025 kg).
> `mars.nasa.gov/mars2020/spacecraft/rover/` (M2020 actual).

Under `chassis.inertia_xx`, `inertia_yy`, and `inertia_zz`:

> Bounding-box inertia tensor from chassis envelope 3.0 m x 2.7 m x 2.2 m at
> M = 1025 kg. Solid uniform rectangular cuboid:
>
> ```text
> ixx = M/12 * (W^2 + H^2)
> iyy = M/12 * (L^2 + H^2)
> izz = M/12 * (L^2 + W^2)
> ```
>
> Computed offline (see `test_rover_physics_inject.py::test_chassis_inertia_matches_bbox`).
> Replaces URDF auto-computed placeholder so PhysX sees a deterministic tensor.
> M2020 ballpark — NOT a calibrated CAD-derived inertia.
>
> Inline units: `inertia_xx` is `kg*m^2 (W=2.7, H=2.2)`, `inertia_yy` is
> `kg*m^2 (L=3.0, H=2.2)`, and `inertia_zz` is `kg*m^2 (L=3.0, W=2.7)`.

Under `wheels.mass` and the wheel radius relationship:

> The current `control.wheel_radius` of 0.2667 m corresponds to a 0.5334 m
> diameter (URDF-derived); we keep that value for kinematic IK consistency and
> document the 1.6 % gap below.
>
> Per-wheel mass estimate (M2020 ballpark). Public M2020 papers do not publish
> a per-wheel mass; 9.0 kg is a literature-aligned estimate for an
> aluminum-machined, spoked rover wheel of this diameter. 6 wheels x 9 kg =
> 54 kg total — leaves the 1025 kg chassis dominating articulation inertia,
> which matches the M2020 mass distribution.
>
> Inline unit: `mass` is `kg per wheel — M2020 estimate.`

Under `wheels.inertia_spin` and `inertia_transverse`:

> Cylinder inertia about the spin axis (X) and the two transverse axes:
>
> ```text
> I_spin       = m * r^2 / 2
> I_transverse = m * (3 r^2 + h^2) / 12   with h = wheel width
> ```
>
> Wheel width assumed h = 0.40 m (M2020 ballpark). Inertia values are
> offline-computed in the unit test for evidence.
>
> Inline units: `inertia_spin` is `kg*m^2 (about spin axis)` and
> `inertia_transverse` is `kg*m^2 (radial axes)`.

Under wheel material fields:

> PhysX material friction. Mars regolith literature (Sullivan et al. 2017,
> JGR; Heverly et al. 2013) places effective wheel-soil friction in the 0.4–0.7
> range; we adopt the midpoint as a starting point. Static > dynamic so the
> rover does not creep on slope hold.
>
> Inline notes: `friction_static` is `mu_s — Mars regolith literature`,
> `friction_dynamic` is `mu_d — Mars regolith literature`, and `restitution` is
> `No bounce on regolith (literature consensus)`.

Under `suspension.rocker_damping` and `bogie_damping`:

> Rocker-bogie joint damping (passive viscous resistance). The pre-existing
> `control.suspension_damping = 50` covered every rocker/bogie joint with one
> number; we now distinguish rocker vs bogie so future tuning can target the
> differential beam without touching the bogie pivot.
>
> Inline units: `rocker_damping` is `N*m*s/rad — primary rocker arms`; and
> `bogie_damping` is `N*m*s/rad — bogie sub-arms (matches legacy)`.

### `ros2.topics` (lines 95–104)

The inline topic comments were:

> `imu`: OmniGraph PubIMU — raw PhysX readings, no noise.
>
> `imu_noisy`: Python `imu_noise_publisher` — seeded Gaussian noise injected;
> only active when `imu.sigma_* > 0`.
>
> `odom`: wheel-encoder dead-reckoning estimate (SLAM input).
>
> `gt_trajectory`: PhysX articulation pose verbatim (ATE ground truth).
>
> `points`: RGB-D PointCloud2 (RealSense-style).
>
> `camera_info`: CameraInfo (intrinsics K/P/R/D).
>
> `joint_states`: `sensor_msgs/JointState` for robot_state_publisher.

### `ros2.rates` (lines 106–118)

> IMU is locked to 30 Hz to match the effective PhysX physics tick observed
> under GPU-bound rendering (`delete_later/imu_diagnostic/imu_stat.py` reported
> ~31 Hz publish rate even when this value was set to 60). Matching the rates
> avoids 60-vs-30 sampling aliasing in the `linear_acceleration` topic.
>
> `points`: depth-derived PointCloud2 matches the depth rate.
>
> `camera_info`: CameraInfo published in lock-step with rgb/depth.
>
> `lidar`: For ROS2 Point Cloud Topic Publishing Rate, not the same as the RTX
> LiDAR rotation rate (see `lidar_3d.rotation_rate_hz` below).
>
> `joint_states`: OG ROS2PublishJointState tick rate (matches odom).

### `ros2.odom_publisher` (lines 119–129)

> Frame names threaded through `create_odometry_publisher` so the SLAM stack
> YAML shares one source of truth.
>
> Since the URDF is REP-103 aligned (post rc1b_urdf_rep103), the URDF root link
> `Body_Chassis` already publishes in REP-103, so `base_link` and
> `Body_Chassis` resolve to the same frame (no X-roll wrapper needed). SLAM
> launch params should set `base_frame: base_link` to match.

### `ros2.sensor_parent_frame_id` (lines 130–135)

> Parent frame for the static sensor TFs broadcast by
> `marslab.ros2_bridge.tf_broadcaster.publish_static_sensor_tfs`.
> Default `Body_Chassis` matches the URDF root link name so the rclpy-published
> sensor offsets attach to the robot_state_publisher-published articulation
> chain.

### `ros2.publish_odom_tf` (lines 136–147)

> Enable rclpy-side TF broadcast of `odom -> base_link` using the PhysX
> articulation root pose as ground-truth odometry.
>
> Replaces the dependency on an external visual SLAM stack (RTAB-Map
> `rgbd_odometry`, ORB-SLAM3, etc.) for the odom transform. The `init_quat_world`
> is forced to identity in the runtime entry point (`marslab/main.py`) so the
> odom frame equals world REP-103. Since the URDF is REP-103 aligned (post
> `rc1b_urdf_rep103`), `spawn.orientation_rpy` is identity and no X-roll
> compensation is applied. Set `false` to delegate `odom -> base_link` to a
> downstream visual SLAM stack; never run two publishers on the same transform.

### `sensors.seed` and sensor frame convention (lines 150–161)

> Master RNG seed for all Python-side sensor noise models.
>
> Same seed → identical noise sequence on rerun (wheel odom, IMU, depth camera).
> Omit or set to null for nondeterministic behaviour (original default).
> Per-sensor RNGs are derived independently via `np.random.SeedSequence` so
> changing one sensor's parameters does not shift another's sequence.

> Sensor frames are authored in the URDF body frame, which is REP-103 aligned
> (+X forward, +Y left, +Z up) since the 2026-05-04 rc1b URDF rewrite. A sensor
> 2.1 m above the chassis is at `z = +2.1`.
> `tf_broadcaster.py` broadcasts these values identity; no X-roll compensation
> is applied anywhere in the chain.

### `sensors.camera` and `depth_sensor` (lines 166–193)

> URDF body frame is REP-103 (Z-up) post rc1b rewrite, so the camera parent
> Xform inherits an upright frame. The image is broadcast with identity rpy; no
> X-roll compensation is needed. An earlier iteration kept `[180, 0, 0]` under
> the assumption that the camera prim required an Isaac-Sim-convention
> image-plane flip, but empirical verification (2026-05-04) showed the
> resulting RGB image was inverted — the `[180, 0, 0]` was a Z-down URDF
> compensation, not an Isaac-Sim convention requirement.

> Optional stereo-disparity depth simulation (`OmniSensorDepthSensorSingleViewAPI`
> schema). `enabled: false` keeps the v0.7 / v1.0 behaviour where depth comes
> from the renderer's noiseless `DistanceToImagePlane` AOV. Flip `enabled` to
> `true` for RealSense-style simulated depth with disparity noise, occlusion
> holes, and a confidence map. Defaults are RealSense D455 ballpark; adjust
> `baseline_mm` per scenario (M2020 Navcam baseline ~ 420 mm).

### `sensors.lidar_3d` (lines 195–219)

> 3D rotary RTX LiDAR. Every numeric parameter that used to hide inside Isaac
> Sim's `Example_Rotary.json` profile is declared here so the YAML is the single
> source of truth. Values mirror the bundled JSON: 16-beam Velodyne-style
> scanner, 30 deg vertical FOV, 360 deg horizontal at 0.4 deg horizontal step,
> 10 Hz rotation, 0.5–100 m range.

> URDF body frame is REP-103 (Z-up) post rc1b rewrite, so the `lidar_link` ROS
> frame inherits the canonical axis directly with identity rpy. No X-roll
> compensation needed.

> Inline `profile_name` note: Isaac Sim Bundled RTX LiDAR asset key (Ouster OS1
> USD carries variant set).
>
> Swap the LiDAR USD model by changing this key (for example,
> `Velodyne_VLP16`). `null` falls back to `profile_name`.
>
> Variant inside the OS1.usd asset (128-channel @ 10 Hz, 1024 horizontal
> samples).

### `sensors.imu` (lines 226–229)

> Python-side Gaussian noise (seeded from `sensors.seed`).
> Zero disables noise injection (preserves raw PhysX readings via OmniGraph).
>
> Inline units: `sigma_lin_acc` is `m/s^2 per axis — MEMS IMU ballpark` and
> `sigma_ang_vel` is `rad/s per axis — MEMS gyro ballpark`.

### `control` (line 232)

> Geometry derived from URDF kinematic chain (`m2020.urdf`).

### `wheel_odometry` (lines 274–289)

> Wheel-encoder dead-reckoning odometry publisher (skid-steer FK).
> Subscribes to wheel joint angular velocities, injects slip + Gaussian noise,
> integrates pose, and publishes `nav_msgs/Odometry` on `/<ns>/odom`. This is
> the SLAM input — the PhysX GT pose lives on `/<ns>/GT_Trajectory` for ATE
> comparison. See `GT_Trajectory.md`.

> Inline units: `track_width` is `m — matches control.track_middle (rear-axle)`;
> `slip_left` is `fractional rotational slip (0 = no slip)`; and `sigma_omega`
> is `rad/s -- Gaussian noise on each wheel bank`.

> `seed` is intentionally omitted here; it is injected at runtime from
> `sensors.seed` (via `main.py` child[0] `SeedSequence`). When `sensors.seed` is
> `None` the wheel odom RNG uses a nondeterministic seed.

## Runtime boundary reminder

These notes are historical comment recovery only. They do not restore either
legacy YAML, any split loader, `--usda`/`--z-offset` flag, or a second runtime
configuration path.
