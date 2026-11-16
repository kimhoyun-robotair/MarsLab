---
title: Sensors
description: Camera, depth, LiDAR and IMU acquisition, output and limitations.
permalink: /reference/sensors/
---

The numeric examples below describe the default Perseverance research profile.
Its LiDAR attachments and synthetic depth are simulation additions. Historical
mission profiles can set `lidar_2d: null` and `lidar_3d: null` to omit LiDAR
acquisition and publication.

Science instrument metadata does not imply that the simulator reproduces spectra,
radiation, chemistry, detector response, or a complete flight engineering telemetry
system.

## Camera and depth

Camera resolution, focal length, clipping range, and local pose configure the
primary `rover.sensors.camera` render product used by RGB, raw depth, depth
PointCloud2, and CameraInfo. `rover.sensors.cameras` accepts additional named
camera definitions. An optional `parent_link` selects the camera's USD/URDF
mounting link; omitting it uses the chassis. Local translation and orientation
are relative to that link. An optional `prim_path` attaches acquisition to an
existing USD camera; relative prim paths resolve below the mounting link.
The existing camera's authored pose must agree with the YAML pose. Startup
rejects a mismatch so the rendered view and ROS TF cannot silently diverge.
To reposition an existing camera, update its USD transform and matching YAML
pose together. These settings are loaded at startup, not reloaded live.

When ROS is enabled, the primary camera publishes to the configured `topics.rgb`
and `topics.camera_info` (normally `/rover/rgb/image_raw` and
`/rover/rgb/camera_info`). Every additional named camera publishes RGB and
CameraInfo at `/<namespace>/cameras/<name>/image_raw` and
`/<namespace>/cameras/<name>/camera_info`, with
`<name>_camera_optical_frame` matching its static TF. All consumers share each
camera's existing render product. Additional camera publication does not create
a second renderer or invent mission depth measurements.

Set `depth_output: false` on mission cameras to disable synthetic depth and
point-cloud outputs. This is distinct from `depth_sensor.enabled`, which only
controls added noise. The default profile retains `depth_output: true`.

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
product. When noise is disabled and `depth_output: true`, native raw
depth/point-cloud helpers remain active.
The old stereo baseline/confidence/disparity keys are rejected because those
renderer-only settings did not affect the retained ROS measurements.

Both cloud paths publish XYZ fields. Native raw clouds can be unorganized
(`height=1`), while the noisy path preserves the depth image's row/column layout.
Use the PointCloud2 dimensions and fields when decoding it. Shared intrinsics
and matching depth/Z values alone do not establish full XYZ-to-surface accuracy;
pixel-center conventions also matter when comparing against projected targets.

## 2-D LiDAR

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

## 3-D LiDAR

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

## IMU

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
