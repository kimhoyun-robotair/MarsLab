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
- `dust_optical_depth` (`tau`) starts at **0.05**. YAML accepts `0 < tau <= 6`,
  including values below 0.05; the GUI slider covers **0.05–6**.
- `solar_constant` is top-of-atmosphere broadband irradiance in W/m²; the default
  589 is a mean Mars value, without automatic seasonal or orbital scaling.
- `sun_azimuth_deg` and `sun_elevation_deg` set the manual sun, with elevation
  allowed from 0° through 90°.
- `sol_duration_seconds` defines the sweep's simulated duration.

### Lighting model and limits

With zenith angle `z`, direct normal irradiance is `B = I0 exp(-tau/cos(z))`.
This uses the plane-parallel approximation documented in
[NASA's 1990 update, equations 6–7](https://ntrs.nasa.gov/api/citations/19910005804/downloads/19910005804.pdf).
The source supports the secant approximation up to about `z=80°` (elevation 10°).
The same expression is extended toward the horizon for continuity, with no
accuracy guarantee there. At elevation 0° or below, direct irradiance is zero,
as specified in MarsLab.pdf Eq. 3. The tau-indexed sky remains independent of
sun elevation; no additional night or twilight model is imposed.

The retained tau-only table is an **uncalibrated heuristic**, not a reproduced
[COMIMART calculation](https://doi.org/10.1051/swsc/2015035). Its reference zenith,
cloud/albedo conditions, spectral band, extraction data, and error bounds are
unavailable. Linear interpolation is used between the existing points, with
endpoint clamping outside 0–6 in the pure function. The tau=5/6 points and
`f(0)=0.10` have no established physical calibration; the latter must not be
interpreted as a verified molecular-scattering floor. At tau=0.05, `f=0.14`.

MarsLab.pdf III-E specifies a tau-indexed COMIMART reduction but does not give
its table values or a DomeLight conversion. The runtime preserves the existing
table and renderer scale without deriving absolute diffuse irradiance from the
direct beam. Reproducing COMIMART requires traceable input data and calibration.

### Dynamic atmosphere

`mars_env.dynamic_atmosphere.enabled` selects the **initial** sun mode; the
supplied configuration uses `false` for a fixed manual sun. The GUI can select
Auto Sweep or Manual afterward, regardless of this initial flag. Dust changes
update the sky and fog in either mode, every `update_interval_frames`.

Both modes start at `sun_azimuth_deg` and `sun_elevation_deg`. Selecting Auto Sweep
anchors the sweep at the latest angles, including manual edits, before advancing.
Manual pauses motion; returning to auto preserves the current position and the
previous rising/setting direction. Rapid mode changes also preserve manual edits.

`initial_sol_fraction` is retained for configuration compatibility. Values up to
0.5 select the initial rising branch and values above 0.5 select the setting
branch; it does not override the configured angles. The actual phase is derived
from the current elevation on the half-sine envelope. If the current elevation
exceeds `sun_sweep.max_elevation_deg`, that elevation becomes the peak for this
auto run so entering auto never clamps the sun to a lower angle.

The difference `end_azimuth_deg - start_azimuth_deg` sets azimuth travel per sol,
starting at the current azimuth and wrapping at 360°. These values do not force
a reset to the start azimuth at a sol boundary. `time_scale` controls the motion
rate. This is an interactive sweep, not an astronomical day/night model.

GUI overrides only affect the current run. For dust-only comparisons, keep the
manual sun, rover/camera pose, renderer, exposure, and texture inputs fixed, then
vary tau. Record these settings alongside the sensor seed.

## Rendering modes

`rendering.mode` applies even when `runtime.atmosphere_enabled: false` and accepts two modes:

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

Sun intensity is `B * sun_intensity_scale`, with no second `(1-f)` reduction.
Dome intensity retains `f(tau) * brightness * dome_brightness_scale`, with the
original gain of **5000**. Here `brightness` is computed from
`sky_dome.brightness_min`, `brightness_decay`, and `tau_saturation`.
This is the existing renderer mapping, not an equation specified by the PDF.
No isotropic-sky conversion or absolute diffuse irradiance is computed.
Colors, texture pixels, and brightness modifiers affect appearance; USD light
intensity values must not be interpreted or added as measured W/m².

Keep the three HDRI filenames inside `sky_dome_hdri_dir`. Startup and live updates
select the same texture: clear below tau=0.5, moderate below 1.5, dusty otherwise.
A missing or empty texture clears the previous texture and uses the color dome;
a missing file emits a warning. Texture changes therefore follow tau in both
directions instead of retaining the initial image.

### Simple fog

Fog uses the [RTX simple exponential appearance approximation](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_common.html#simple-fog).
It is not a multiple-scattering dust model. `fog_density_scale * tau` sets the
renderer density at the end distance, without a physical m⁻¹ or visibility
calibration. The following keys were checked against Isaac Sim 5.1:

| Configuration | Meaning |
| --- | --- |
| `fog.enabled` | Enable simple fog when the atmosphere is active. |
| `fog.start_distance_m` / `fog.end_distance_m` | Camera distance interval, defaults 0 / 5000; end must exceed start. |
| `fog.start_height` | Height plane in meters, using the stage's +Z axis. |
| `fog.height_falloff` | Renderer height falloff parameter. |
| `fog.height_density_ratio` | Height density relative to the tau-scaled distance density. |
| `fog.color_amount` | Existing 0–1 control, now mapped to the supported `fogColorIntensity` setting. |

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
applies the optional renderer depth schema to camera acquisition, including when
`runtime.ros2_enabled: false`. Raw depth and the retained PointCloud2 path remain
part of the camera pipeline. The independent depth reader consumes its attached
`distance_to_image_plane` annotator, returning an empty array until data arrives.
Attaching this schema does not establish that the raw depth AOV contains its
noise; the renderer's dedicated depth-effect output is a separate interface.
If the optional schema is unavailable, a warning reports the raw-depth fallback.
The shared render product explicitly selects LDR color (`rgbDepthOutputMode=0`)
to preserve RGB when the optional effect is enabled. Isaac Sim 5.1 emitted
repeated missing-depth-buffer errors with this effect in Path Tracing during
validation. MarsLab therefore applies it in `ray_tracing` mode;
`path_tracing` warns and retains raw depth.

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

An integer `rover.sensors.seed` derives separate NumPy seeds for wheel odometry
and noisy IMU output. `null` leaves both nondeterministic; wheel odometry no
longer silently falls back to seed 0. This setting does not seed the RTX depth
effect or guarantee deterministic GPU rendering.

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
