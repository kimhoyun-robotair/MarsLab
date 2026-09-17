# Configuration and Tuning Guide

MarsLab uses one runtime configuration file:
[`configs/config.yaml`](configs/config.yaml). Relative asset paths are
resolved from the directory containing that file, so the repository can be
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

### `scene.usdz_path`

Selects the supplied Mars scene. A relative path is resolved from `configs/`.
The path must point to an existing USDZ file before Isaac starts.

Download the scene assets as described in the [README](README.md#2-download-the-mars-scene-assets).
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

### `rover.spawn.mode`

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

## Runtime modes

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

The tau-only diffuse fraction now evaluates the published delta-Eddington
[COMIMART equations 10–23](https://doi.org/10.1051/swsc/2015035) at fixed NIR
reference conditions: solar cosine 0.7, single-scattering albedo 0.97,
asymmetry 0.70 and ground albedo 0.25. Clouds and gases are omitted in this
reduction. Published Table 3 values, numerical differences and assumptions are
recorded in [assets/atmosphere/](assets/atmosphere/README.md). This is a
traceable reference reduction; the DomeLight gain is still a renderer scale,
not a full-spectrum or absolute diffuse irradiance calibration.

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

The rover USD owns geometry, collision shapes, articulation structure, mass,
inertia, and center of mass. Configuration owns chassis damping, wheel contact
materials, and joint drives without rewriting the source asset. Mass, inertia,
and center-of-mass override keys are not accepted in the configuration.

The source rover's rigid-body masses total 951.64 kg. The 20 links with visual meshes
use uniform-density solid convex hulls to estimate their link-local centers of
mass and full inertia tensors. These are geometry-based approximations, not
measured flight-rover mass distributions. The supplied URDF and USD physics
layers contain the authored mass properties. The active rover also includes
the LiDAR attachment masses described below.

The passive rocker differential constrains `LEFT_DIFFERENTIAL +
RIGHT_DIFFERENTIAL = 0` through PhysX mimic coupling. Both rocker position
stiffnesses remain zero; damping is configurable. Startup validates this
coupling before physics begins.

### Supplied rover and LiDAR assets

`rover.usd_path` selects `assets/robots/rover/m2020_lidar.usda`, which composes
the base `m2020.usd` and both sensor USD assets. Preserve the base rover's
configuration layers and textures alongside it. `rover.urdf_source_path` selects
`assets/robots/rover/m2020_lidar.urdf`; its mesh references use the rover
submodule and the sensor OBJ/MTL files.

The attachments add **5.688155 kg**, bringing the authored rover mass to
**957.328155 kg**. Their mass is merged into the chassis rigid body.
The [sensor asset guide](assets/robots/sensors/README.md) and
[mass-property record](assets/robots/sensors/mass_properties.json) describe the
construction assumptions and resulting COM/inertia. Retained Blender sources,
JSON records, and previews document the supplied assets; runtime reads the
authored USD/URDF. Asset generation and rebuild commands are outside this
distribution.

### Physics tuning

Tune in this order:

1. Confirm `chassis.rigid_body_prim_name`, wheel link names, and joint names.
2. Confirm the source USD mass properties and tune chassis damping.
3. Set wheel static/dynamic friction and restitution.
4. Tune passive rocker and bogie damping.
5. Tune active drive and steering gains.

Static friction must not be lower than dynamic friction. Wheel links name the
six `Body_Wheel*` rigid bodies, each with enabled collision shapes. Startup
checks each collider's effective physics material, including instance proxies,
before reset. Joint and link lists must match the USD exactly; missing bodies,
colliders, or ineffective overrides stop startup. Physics material bindings do
not change the visual materials. Runtime logs separate requested settings from
the values read back from USD.

## Rover control

`rover.control` defines rover geometry, velocity limits, joint ownership, and
command ramping.

`drive_type` supports:

| Mode | Meaning |
| --- | --- |
| `acceleration` | Selects the PhysX DriveAPI acceleration mode. This is the supplied default. |
| `force` | Selects the PhysX DriveAPI force mode. Re-tune damping and maximum force when selecting it. |

In both modes the controller sends wheel angular-velocity targets and steering
angle targets. `drive_type` selects how PhysX applies the drive response.

Important tuning groups:

- Geometry: `wheel_radius`, `wheelbase`, `steering_axle_offset`, `track_steer`, `track_middle`
- Limits: `max_linear_velocity`, `max_angular_velocity`, `max_steer_angle`
- Drive: damping, maximum force, and wheel acceleration rate
- Steering: stiffness, damping, maximum force, ramp rate, and alignment tolerance
- Braking feel: `decel_multiplier`
- Parking hold: `brake_stiffness` (default `50000.0`; `0` disables it)

The parking brake latches measured wheel angles when all commanded wheel rates
finish ramping to zero, then holds those targets with the configured position
stiffness. A nonzero drive target releases the hold; Stop clears the latch.
Tune this gain together with the drive mode, damping and maximum force.

Drive and steering lists require six and four unique, disjoint joints in their
documented wheel order. `command_timeout` defaults to 0.5 simulated seconds;
publish commands continuously while driving. Stale or nonfinite commands
request a controlled stop using the configured deceleration ramp. Pause freezes
expiry; Stop clears the command. A zero Twist or timeout retains the current
steering orientation while braking, rather than straightening moving wheels.

Ordinary driving reduces excessive yaw rate before computing both steering and
wheel rates, so they describe the same feasible arc. A command with zero linear
speed and nonzero yaw rate selects a pivot turn: the four corner wheels point
along tangents around the middle axle, and the two wheel banks counter-rotate.
The canonical `max_steer_angle` is `0.9` rad (51.57 degrees). Configuration must
allow the pivot angles required by its geometry; insufficient steering travel
fails preflight. Before physics reset, startup also checks this configured
travel against each steering joint's USD limits without changing those limits.

`steering_axle_offset` is the forward displacement of the front/rear axle
midpoint from the nonsteering middle axle, in meters. It defaults to zero; the
supplied rover uses `0.05502`, matching its USD wheel centers. Front and rear
wheel positions are therefore `wheelbase/2 + offset` and `-wheelbase/2 + offset`,
with middle wheels at zero. The canonical pivot angles are approximately
48.12 degrees at the front and 45.33 degrees at the rear. Control and wheel
odometry use this same geometry.

For a material steering change, the controller brakes first, steers after measured
wheel-angle excursion divided by elapsed time over a 0.20 s simulation-time
window falls below `steering_stop_speed` (default `0.05` rad/s), and resumes driving
only after measured steering is within `steering_alignment_tolerance` (default
`0.02` rad) of the target. Wheel-rate ramping uses a common proportional change
so acceleration and braking preserve the commanded wheel-speed ratios.

## Sensors

### Camera and depth

Camera resolution, focal length, clipping range, and local pose configure the
single shared Camera render product used by RGB, raw depth, depth PointCloud2,
and CameraInfo.

`horizontal_fov_deg` optionally sets the pinhole horizontal field of view and
overrides `focal_length_mm`; null preserves the focal-length setting. The
default is 135 degrees, with square pixels and about 122.18 degrees vertically
at 640×480. CameraInfo and depth-cloud projection use the same intrinsics.
The camera is placed at the source rover's left Navcam mast reference point,
`[0.752094567, -0.774359584, 1.837690473]` metres relative to `Body_Chassis`.
It keeps the forward, 6.6-degree downward orientation and chassis-owned static
TF; it does not track an independently actuated mast. No camera mesh is added.
The 0.3 m near clip excludes the surrounding mast head. The far clip and
optional depth-noise maximum are 200 m. Camera depth is distance along the
optical axis, rather than radial distance at the image edges.

`depth_sensor.enabled` selects optional additive Gaussian noise on measured
depth. `noise_mean` and `noise_sigma` are in metres; min/max distance mask
unusable pixels. Noise uses a child of the configured sensor seed and the
acquisition timestamp. The depth image and organized XYZ cloud use the same
noisy sample, frame and timestamp. RGB and CameraInfo keep the shared Camera
product. When disabled, native raw depth/point-cloud helpers remain active.
The old stereo baseline/confidence/disparity keys are rejected because those
renderer-only settings did not affect the retained ROS measurements.

Both cloud paths publish XYZ fields. Native raw clouds can be unorganized
(`height=1`), while the noisy path preserves the depth image's row/column layout.
Use the PointCloud2 dimensions and fields when decoding it. Shared intrinsics
and matching depth/Z values alone do not establish full XYZ-to-surface accuracy;
pixel-center conventions also matter when comparing against projected targets.

### 2-D LiDAR

The horizontal RTX sensor publishes `/rover/scan` in `lidar_2d_link`. The default
forward field of view is 135 degrees, centred on +X, with a 0.2–200 m range.
The native sensor completes 360-degree rotations; partial native emission gates
produced irregular scan completion intervals in the installed Isaac version.
Acquisition crops ranges, intensities and angular metadata together, so the
supported local reader and ROS expose only the configured forward sector.
The underlying native annotator still contains the full turn. Tune range,
horizontal FOV, scan rate and local pose.

The current settings produce 1,201 output beams at a nominal 10 Hz. Native
no-return values can be `-1`; consumers should reject nonfinite values and
values outside the advertised range limits.

`LaserScan.header.stamp` is the nominal first-ray time, computed as the native
FlatScan completion timestamp minus `scan_time = 1 / rotationRate`, plus the
time to reach the sector's first ray. `time_increment` retains the full-turn
angular resolution: `scan_time * horizontal_resolution_deg / 360`. Cropping
does not stretch the remaining beams across a whole rotation. Completion time is sampled
at render-step resolution; this interface does not provide exact individual-ray
timestamps. Startup scans without valid timing and scans whose nominal start
precedes the episode are skipped.

### 3-D LiDAR

Tune range, horizontal/vertical field of view, rotation rate, and local pose.
The default range is 3.5–200 m. The ray-origin offset also uses the near range,
so rays begin beyond the mounted rover geometry instead of being blocked by it.
The inspected rover's furthest visual vertex is about 3.087 m from the 3-D
scanner in its authored pose; 3.5 m includes clearance. Reassess this bound if
the rover geometry, sensor mount or articulation envelope changes. Returns
inside 3.5 m are intentionally unavailable. Maximum range is a configured cap;
native material reflectance and scene occlusion still affect actual returns.
`profile_name` selects an installed Isaac USD sensor model; `variant` selects
its supported variant. Preflight checks the installed catalog. Keep
`profile_json_path` and `usd_profile` null: Isaac 5.1's OmniLidar constructor
does not load arbitrary legacy JSON through those arguments. Unsupported
values now fail before Kit starts instead of silently using another sensor.

### IMU

`sampling_frequency_hz` controls PhysX IMU sampling. Noise standard deviations
control the separate noisy ROS stream. A configured sampling frequency does not
guarantee the final observed ROS publication rate; verify it in the live system.

Raw and noisy IMU output share one sensor-period measurement and its acquisition
timestamp. Noise is sampled once per fresh measurement. Ground truth and wheel
odometry use the simulation time of the completed physics state; wheel odometry
and its optional TF share the same timestamp.

An integer `rover.sensors.seed` derives separate streams for wheel odometry,
noisy IMU and optional depth noise. `null` selects nondeterministic noise.
This does not guarantee deterministic GPU rendering or physics.

Pause preserves the current episode, including control ramps, odometry, noise
generators, and atmosphere progression. Stop resets those states and sensor
freshness; Play restores the rover articulation for a new episode. Simulation
clock and sensor helper timestamps reset on Stop, so ROS consumers must handle
time moving backwards between episodes. A fixed seed reinitializes the custom
noise generators; depth noise also depends on acquisition timestamps.
Reproducibility across complete runs must be checked with the same inputs and
acquisition conditions.

## ROS 2 topics, frames, and QoS

`rover.ros2.namespace` is normalized without outer slashes. Topic entries are
relative names and must not start or end with `/`.

### Companion launch

For the robot description and articulation TF chain, run the companion from the
repository root in a separate ROS terminal:

```bash
source /opt/ros/jazzy/setup.bash
ros2 launch launch/rover_state_publisher.launch.py
```

The launch file reads its sibling [companion_urdf.py](launch/companion_urdf.py).
This helper prepares the URDF text with `Body_Chassis` as its root, handles the
source floating joints, and resolves relative mesh filenames to absolute file
URIs. It leaves the source URDF unchanged. Keep both Python files in `launch/`.

The companion does not read `configs/config.yaml`. Its default `urdf_path` is
`assets/robots/rover/m2020_lidar.urdf` and its default namespace is `rover`.
When changing `rover.urdf_source_path` or `rover.ros2.namespace`, supply matching
`urdf_path:=<absolute-path>` or `namespace:=<name>` launch arguments. Its
`publish_frequency` argument controls robot_state_publisher cadence, not the
Isaac physics or sensor sampling rate.

### Ownership and QoS

Keep these ownership rules intact:

- The companion owns identity `base_link` to `Body_Chassis`, the URDF
  articulation chain and the retained `/rover/robot_description` topic.
- MarsLab owns static sensor frames below `Body_Chassis`.
- Ground truth uses `map` / `base_link_gt` and publishes no TF.
- Wheel odometry uses `odom` / `base_link`.
- `wheel_odom.publish_tf` is the only MarsLab switch for dynamic odometry TF.

Ground-truth and wheel-odometry topics must be different.

QoS profiles support:

- Reliability: `reliable` or `best_effort`
- Durability: `volatile` or `transient_local`
- History: `keep_last` (the common rclpy/OmniGraph supported policy)
- Queue depth: a positive value within the validated range

Use best-effort/volatile QoS for high-rate sensors unless a consumer requires
reliable delivery. Keep static and latched data transient-local where supported.

## Wheel odometry

Wheel odometry solves planar velocity from six wheel encoders and the four
measured steering angles. It shares wheelbase, steering-axle offset, track, and
radius geometry with the drive controller, applies configured slip and
angular-rate noise, and integrates planar arcs. It never reads ground truth.

- Increase `slip_left` or `slip_right` only to model systematic wheel slip.
- Tune geometry in `rover.control`; the separate `track_width` key is removed.
- Use six nonnegative covariance values in the documented component order.
- Set `rover.wheel_odometry.enabled: false` to disable the wheel estimate.
- Set `wheel_odom.publish_tf: false` when an external localization system owns
  dynamic `odom` to `base_link` TF.

## Safe validation boundary

Configuration and pure calculations can be checked without Isaac. Final rover
physics, renderer appearance, sensor output, ROS topic/QoS compatibility, TF
ownership, AtmospherePanel behavior, and cleanup must be observed in the user's
Isaac Sim and ROS environments.
