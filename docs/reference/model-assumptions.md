---
title: Model assumptions
description: Distinguish source-derived robot properties from geometry estimates and simulation settings.
permalink: /reference/model-assumptions/
---

MarsLab is a research simulator. A recognizable spacecraft model or a mission-derived camera calibration does not establish flight-system fidelity.

## Three kinds of model information

| Category | Examples | Interpretation |
| --- | --- | --- |
| Source-derived information | Visual asset provenance, retained NASA/JPL camera calibration records | Traceable to the source identified in the asset notice or profile. |
| Geometry estimates | Mesh-derived mass distribution, some camera mounting approximations | Construction assumptions for the supplied model. |
| Simulation tuning | Drive gains, command caps, contact damping, near clips, noise | Values chosen for this runtime, not measured flight performance. |

## Rover models and mobility

The shared controller uses six driven wheels and four steerable corner wheels. USD assets own articulation and mass properties; profiles select geometry, contact and drive parameters. The default maximum linear command is 4.0 m/s across all four supplied profiles. **This is a simulation cap, not a spacecraft driving-speed specification.**

Perseverance's source body masses total 951.64 kg; simulated LiDAR attachments add mass as described in [rover physics]({{ "/reference/physics/" | relative_url }}). Link centers of mass and inertias use geometry-based approximations. Spirit, Opportunity and Curiosity are MarsLab-authored articulated models derived from source visualization and engineering references.

## Sensors

- The default Perseverance profile adds synthetic depth and LiDAR for research. These are not a reproduction of its flight sensor suite.
- Spirit, Opportunity and Curiosity use retained mission calibration data in pinhole camera rendering. CAHVOR/E distortion and detector physics are not reproduced.
- Camera near clips can exclude opaque visualization housing. This is a rendering workaround, not a flight near-plane specification.
- Some instrument mounts are approximated from visual geometry. Science-camera imagery does not simulate spectra, chemistry or detector response.
- The chassis-reference IMU and zero noise in the historical mission profiles are idealizations.

The [profile source files](https://github.com/kimhoyun-robotair/MarsLab/tree/main/configs/robots) carry calibration URLs and implementation notes. The [sensor reference]({{ "/reference/sensors/" | relative_url }}) explains acquisition and publication behavior.

## Environment and rendering

Direct sunlight uses a plane-parallel attenuation approximation; the tau-only diffuse reduction uses fixed reference conditions. Sky gain and fog are renderer mappings. Light intensity values must not be interpreted as absolute measured irradiance. Read the [atmosphere model limits]({{ "/reference/atmosphere/#lighting-model-and-limits" | relative_url }}).

## Evidence and validation

Documentation describes the supplied implementation. Runtime behavior still requires checks in Isaac Sim and ROS: contact, steering, image geometry, topic timing, frame ownership and renderer appearance cannot be established by reading configuration alone.

The [paper results]({{ "/research/" | relative_url }}) concern their original experimental setup. The [browser demo]({{ "/demo/" | relative_url }}) replays short recorded excerpts; it does not run physics or SLAM on the visitor's device. Its [data provenance]({{ "/demo/DATA.md" | relative_url }}) records the reductions and limitations.
