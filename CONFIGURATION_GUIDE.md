# Configuration and Tuning Guide

MarsLab uses one runtime configuration file:
[`configs/config.yaml`](configs/config.yaml). Relative asset paths are
resolved from the directory containing that file, so the repository can be
cloned anywhere without changing paths for a particular computer.

Offline scene generation is a separate configuration domain. Recipes under
`configs/scene/*.yaml` are consumed by `marslab_scene` before runtime; their
terrain, placement, compatibility-profile, and output settings must never be
added to `configs/config.yaml`. Runtime consumes only the resulting USDZ path.

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

The values written in `configs/config.yaml` are the active values for the
supplied scenario. Additional optional fields use defaults declared in
`marslab/config/schema/`. When a field is omitted, inspect its schema before
assuming that the feature is disabled; omission normally selects a validated
default rather than removing the subsystem.

## Top-level sections

| Section | What it controls | Good first adjustment |
| --- | --- | --- |
| `scene` | Terrain USDZ input | Select a supplied scene. |
| `runtime` | GUI/headless, ROS 2, atmosphere | Disable optional systems while diagnosing startup. |
| `mars_env` | Gravity, dust, sunlight, sol timing | Adjust dust and solar position for a scenario. |
| `rendering` | Renderer, sky, sun, fog | Choose speed or image quality. |
| `rover` | Spawn, physics, sensors, control, ROS | Tune only the relevant subsection. |
| `wheel_odom` | Dynamic odometry TF ownership | Decide whether MarsLab or an external estimator owns TF. |

## Scene selection and rover spawn

### Offline build versus runtime selection

Build a scene with the scene project and a versioned recipe, then point a
temporary or committed runtime config at the validated package:

```bash
python3.11 -m pip install -e './scene[standalone-usd,test]'
scene_build_root="$(mktemp -d)"
python3.11 scripts/scene/build_scene.py \
  --config configs/scene/smoke.yaml \
  --output-dir "${scene_build_root}/scene"
python3.11 scripts/scene/validate_scene.py \
  --scene "${scene_build_root}/scene/scene.usdz"
```

For the supported authoring/runtime surface, run the same scripts with
`marslab/isaac_python.sh`. `configs/scene/smoke.yaml` explicitly selects the
`canonical` compatibility profile and a synthetic artifact. The
`marslab_utils_6f30d67` profile exists only for locked legacy parity.
`configs/scene/paper.example.yaml` is not runnable until every paper input and
canonical asset has an authoritative digest and license; do not rename it to
`paper.yaml` or guess its paths.

The builder refuses an existing output by default. `--force` preserves the
previous output as a recoverable sibling backup after the new output has passed
validation. The final `scene.usdz` is relocatable and the adjacent manifest
records relative paths, resolved profile, provenance and SHA-256 digests.

Actual runtime smoke uses a temporary copy of `configs/config.yaml` and changes
only `scene.usdz_path` in that copy:

```bash
marslab/isaac_python.sh scripts/scene/smoke_isaac.py \
  --scene "${scene_build_root}/scene/scene.usdz" \
  --base-runtime-config configs/config.yaml \
  --report "${scene_build_root}/isaac-smoke.json"
```

Standalone `usd-core` validation is not Isaac validation. See
[`scene/README.md`](scene/README.md) for manifest fields, output layout, test
tiers, provenance, asset-license status, and the currently blocked Release
Gates.

### `scene.usdz_path`

Selects the supplied Mars scene. A relative path is resolved from `configs/`.
The path must point to an existing USDZ file before Isaac starts.

### `rover.spawn.mode`

| Mode | Meaning | When to use it |
| --- | --- | --- |
| `dem_center` | Place the rover at the sampled terrain center. | Recommended starting mode for a new scene. |
| `dem_relative` | Offset the rover from the terrain-derived reference. | Repeatable tests near a known terrain feature. |
| `absolute` | Use the configured world-space position directly. | Precisely surveyed or externally defined poses. |

`xy` provides the horizontal position or offset. `z_offset` adds clearance above
the sampled surface, and `orientation_rpy` sets roll, pitch, and yaw in radians.
Start with a small positive `z_offset` to avoid initial terrain intersection.

## Runtime modes

| Key | Recommended use |
| --- | --- |
| `runtime.headless: false` | Interactive GUI development and AtmospherePanel inspection. |
| `runtime.headless: true` | Unattended or remote runs where no GUI is required. |
| `runtime.ros2_enabled: true` | Publish retained ROS interfaces and accept `/cmd_vel`. |
| `runtime.ros2_enabled: false` | Isolate Isaac scene, physics, or rendering issues. |
| `runtime.atmosphere_enabled: true` | Enable Mars sky, sun, fog, and optional GUI control. |
| `runtime.atmosphere_enabled: false` | Use the fallback scene light and reduce atmosphere complexity. |

Headless mode prevents the GUI panel from being created. It does not redefine
sensor, physics, or ROS ownership.

## Mars environment and atmosphere

- `gravity` controls world gravity and the IMU diagnostic reference. Keep it
  within the validated Mars range unless the schema and physics contract change.
- `dust_optical_depth` (`tau`) controls sky color, brightness, direct light, and
  diffuse light. Lower values produce clearer skies; higher values produce a
  darker, dustier atmosphere.
- `solar_constant`, `sun_azimuth_deg`, and `sun_elevation_deg` define the initial
  illumination state.
- `sol_duration_seconds` defines the modeled Martian day length.

### Dynamic atmosphere

Set `mars_env.dynamic_atmosphere.enabled` to animate the sun during the run.
`time_scale` controls how quickly simulated solar time advances, while
`sun_sweep` defines the azimuth interval and maximum elevation.
`update_interval_frames` trades responsiveness for update cost.

The GUI dust slider is an in-memory override for the current run. It does not
write values back to `configs/config.yaml`.

## Rendering modes

`rendering.mode` accepts two modes:

| Mode | Trade-off | Recommended use |
| --- | --- | --- |
| `ray_tracing` | Faster interactive rendering | Default development and sensor iteration. |
| `path_tracing` | Higher image quality at greater cost | Offline visual studies and final captures. |

For path tracing, increase `spp`, `total_spp`, and `max_bounces` carefully.
Higher values improve convergence but increase render time. Ray-tracing quality
is controlled separately through anti-aliasing, DLSS, and denoiser settings.

Sky-dome tuning is split between:

- `sky_dome_hdri_dir` and the clear/moderate/dusty filenames
- `sky_dome.clear_rgb` and `sky_dome.dusty_rgb`
- brightness limits and dust-response parameters
- sun intensity, color, and angular diameter
- fog density, color, height, and falloff

Keep the three HDRI filenames inside `sky_dome_hdri_dir`. If an image is
intentionally unavailable, MarsLab can fall back to a color dome.

## Rover physics

The rover USD owns geometry, collision shapes, and articulation structure.
Configuration values override selected live-stage physics without rewriting the
source asset.

Tune in this order:

1. Confirm `chassis.rigid_body_prim_name`, wheel link names, and joint names.
2. Set chassis and wheel mass/inertia values.
3. Set wheel static/dynamic friction and restitution.
4. Tune passive rocker and bogie damping.
5. Tune active drive and steering gains.

Static friction must not be lower than dynamic friction. Joint and link lists
must match the USD exactly; startup fails when a configured target is absent.

## Rover control

`rover.control` defines rover geometry, velocity limits, joint ownership, and
command ramping.

`drive_type` supports:

| Mode | Meaning |
| --- | --- |
| `acceleration` | Drive commands behave as acceleration targets. This is the supplied default. |
| `force` | Drive commands behave as force targets. Re-tune damping and maximum force when selecting it. |

Important tuning groups:

- Geometry: `wheel_radius`, `wheelbase`, `track_steer`, `track_middle`
- Limits: `max_linear_velocity`, `max_angular_velocity`, `max_steer_angle`
- Drive: damping, maximum force, and wheel acceleration rate
- Steering: stiffness, damping, maximum force, and ramp rate
- Braking feel: `decel_multiplier`

Drive and steering joint lists must be nonempty, unique, and disjoint.

## Sensors

### Camera and depth

Camera resolution, focal length, clipping range, and local pose configure the
single shared Camera render product used by RGB, raw depth, depth PointCloud2,
and CameraInfo.

`depth_sensor.enabled` does **not** turn depth publishing on or off. It only
enables the optional depth schema/noise/post-processing model. Raw depth and the
retained PointCloud2 path remain part of the camera pipeline.

### 3-D LiDAR

Tune range, horizontal/vertical field of view, rotation rate, and local pose.
Choose exactly one profile source:

- `profile_name` for a built-in profile, or
- `profile_json_path` for a custom JSON profile.

Do not set both. Custom profile paths are resolved relative to the configuration
file and checked during preflight.

### IMU

`sampling_frequency_hz` controls PhysX IMU sampling. Noise standard deviations
control the separate noisy ROS stream. A configured sampling frequency does not
guarantee the final observed ROS publication rate; verify it in the live system.

`rover.sensors.seed` makes supported noisy outputs repeatable across runs.

## ROS 2 topics, frames, and QoS

`rover.ros2.namespace` is normalized without outer slashes. Topic entries are
relative names and must not start or end with `/`.

Keep these ownership rules intact:

- The companion owns identity `base_link` to `Body_Chassis` and the URDF
  articulation chain.
- MarsLab owns static sensor frames below `Body_Chassis`.
- Ground truth uses `map` / `base_link_gt` and publishes no TF.
- Wheel odometry uses `odom` / `base_link`.
- `wheel_odom.publish_tf` is the only MarsLab switch for dynamic odometry TF.

Ground-truth and wheel-odometry topics must be different.

QoS profiles support:

- Reliability: `reliable` or `best_effort`
- Durability: `volatile` or `transient_local`
- History: `keep_last` or `keep_all`
- Queue depth: a positive value within the validated range

Use best-effort/volatile QoS for high-rate sensors unless a consumer requires
reliable delivery. Keep static and latched data transient-local where supported.

## Wheel odometry

Wheel odometry uses left/right drive-joint groups, track width, slip factors,
angular-rate uncertainty, and optional covariance diagonals.

- Increase `slip_left` or `slip_right` only to model systematic wheel slip.
- Keep `track_width` consistent with rover geometry.
- Use six nonnegative covariance values in the documented component order.
- Set `rover.wheel_odometry.enabled: false` to disable the wheel estimate.
- Set `wheel_odom.publish_tf: false` when an external localization system owns
  dynamic `odom` to `base_link` TF.

## Safe validation boundary

Configuration and pure calculations can be checked without Isaac. Final rover
physics, renderer appearance, sensor output, ROS topic/QoS compatibility, TF
ownership, AtmospherePanel behavior, and cleanup must be observed in the user's
Isaac Sim and ROS environments.
