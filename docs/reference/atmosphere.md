---
title: Mars atmosphere
description: Dust, solar illumination, atmosphere controls and physical model limits.
permalink: /reference/atmosphere/
---

- `gravity` controls world gravity and the IMU diagnostic reference. Keep it
  within the validated Mars range unless the schema and physics contract change.
- `dust_optical_depth` (`tau`) starts at **0.05**. YAML accepts `0 < tau <= 6`,
  including values below 0.05; the GUI slider covers **0.05–6**.
- `solar_constant` is top-of-atmosphere broadband irradiance in W/m²; the default
  589 is a mean Mars value, without automatic seasonal or orbital scaling.
- `sun_azimuth_deg` and `sun_elevation_deg` set the manual sun, with elevation
  allowed from 0° through 90°.
- `sol_duration_seconds` defines the sweep's simulated duration.

## Lighting model and limits

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
recorded in [assets/atmosphere/](https://github.com/kimhoyun-robotair/MarsLab/blob/main/assets/atmosphere/README.md). This is a
traceable reference reduction; the DomeLight gain is still a renderer scale,
not a full-spectrum or absolute diffuse irradiance calibration.

## Dynamic atmosphere

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
