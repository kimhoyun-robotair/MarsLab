---
title: Roadmap
description: Delivered capabilities and planned development directions for MarsLab.
permalink: /development/roadmap/
---

The list below records the repository roadmap. Unchecked items are planned or under development; they are not current `main` features.

## Capabilities and directions


- [x] Add 2D LiDAR.
- [x] Support four heterogeneous Mars rovers: Perseverance, Curiosity, Opportunity, and Spirit.
- [x] Mitigate DLSS-related viewport edge flickering by defaulting to DLAA.
- [ ] Support Aerial Robots like Ingenuity.
- [ ] Support Simultaneous Simulation of Multiple Robots.
- [ ] Support Rock Distribution for customizable Mars Scene.
- [ ] Integrate evaluation workflows for TUM, path planning, and SLAM.
- [ ] Extend the existing Gaussian noise with sensor bias and time-varying drift models.
- [ ] Improve the realism of sky and light rendering.
- [ ] Add photorealistic scene generation.
- [ ] Add wheel traces (more sophisticated wheel-soil interaction).
- [ ] Dockerize MarsLab.

## Scene generation

Scene Generation v2.0 is in development. The current runtime consumes prebuilt USDZ scenes; terrain generation and conversion tools are not part of this distribution.

## Aerial integration

See [Ingenuity]({{ "/robots/ingenuity/" | relative_url }}) for the documentation boundary around ongoing aerial work. A new flight runtime should have its own setup, interface and model-limit pages rather than sharing rover-specific instructions.
