---
title: Rendering
description: Ray tracing, path tracing, DLAA, DLSS, sky textures and fog.
permalink: /reference/rendering/
---

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

## Simple fog

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


## Choosing DLSS or DLAA

MarsLab defaults to **DLAA**. DLSS prioritizes a balance between performance and
image quality by reconstructing a higher-resolution image from a lower-resolution
render, but may cause viewport-edge shimmering or flickering in some setups.
DLAA renders at native resolution and eliminated the observed edge flicker in
our Isaac Sim 5.1 / RTX 5090 tests. It may increase GPU resource usage, including
VRAM consumption, compared with DLSS; the actual cost depends on the scene,
resolution, and hardware.

To switch modes, edit `rendering.ray_tracing.antialiasing_op` in the scenario YAML
passed to `--config`, normally [`configs/config.yaml`](https://github.com/kimhoyun-robotair/MarsLab/blob/main/configs/config.yaml).
Update these fields within its existing `rendering` block, then restart MarsLab:

```yaml
rendering:
  mode: ray_tracing
  ray_tracing:
    antialiasing_op: 4  # 4 = DLAA (default), 3 = DLSS
    dlss_exec_mode: 1  # DLSS only: 1 = Balanced
```

Use `3` for DLSS or `4` for DLAA. `dlss_exec_mode` selects the DLSS quality mode
and does not select DLAA. If `antialiasing_op` is omitted, `RayTracingConfig` in
[`marslab/config/schema/scenario.py`](https://github.com/kimhoyun-robotair/MarsLab/blob/main/marslab/config/schema/scenario.py) supplies
the default value `4`; an explicit YAML value takes precedence.
