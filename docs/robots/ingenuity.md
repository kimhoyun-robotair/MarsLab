---
title: Ingenuity
description: Development status and the intended documentation scope for aerial simulation.
permalink: /robots/ingenuity/
---

> **In development**
>
> Ingenuity is not available in the documented `main` runtime. The supported robot selector currently accepts the four rover names only.

## Development scope

The `dev/ingenuity` branch contains work toward an Ingenuity-like aerial runtime, including ArduPilot SITL, a dedicated ROS flight package, actuator modeling and camera/IMU sensing. These additions have a different setup and control workflow from the rover companion.

This page records the intended scope; it is not an installation or flight tutorial. Supported commands and model limits will be documented when the integration is ready for use.

## What belongs in the aerial guide?

- Asset setup and the supported flight backend.
- Flight-stack startup, ROS interfaces and command ownership.
- Frames, simulation timing and sensor acquisition.
- Actuator assumptions, navigation inputs and flight-model limitations.
- Takeoff, landing and reproducible experiment setup.

The rover installation and `robot_state_publisher` companion should not be assumed to configure this flight stack.

## Available today

Use [Perseverance]({{ "/robots/perseverance/" | relative_url }}), [Spirit]({{ "/robots/spirit/" | relative_url }}), [Opportunity]({{ "/robots/opportunity/" | relative_url }}) or [Curiosity]({{ "/robots/curiosity/" | relative_url }}) for the current simulation workflow. Follow the [roadmap]({{ "/development/roadmap/" | relative_url }}) for the broader development direction.
