---
title: Welcome to MarsLab
description: Find your way from installation to your first planetary robotics experiment.
permalink: /guide/
---

MarsLab combines Martian terrain, selectable rover profiles, sensing, vehicle control and optional ROS 2 interfaces in NVIDIA Isaac Sim 5.x. A scenario selects the environment; a robot profile supplies the rover geometry, dynamics and sensors.

## Start a simulation

1. **[Install MarsLab]({{ "/guide/installation/" | relative_url }})** — prepare Isaac Sim, download a terrain and install dependencies.
2. **[Run your first scenario]({{ "/guide/quickstart/" | relative_url }})** — launch the simulator and its optional ROS companion in separate terminals.
3. **[Choose a robot]({{ "/robots/" | relative_url }})** — compare the four supplied rover profiles and their sensors.
4. **[Tune your experiment]({{ "/reference/configuration/" | relative_url }})** — understand configuration composition before changing settings.

## What is included?

| Available in `main` | Where to learn more |
| --- | --- |
| Perseverance, Spirit, Opportunity and Curiosity profiles | [Robot comparison]({{ "/robots/" | relative_url }}) |
| Loading prebuilt USDZ terrain and positioning a rover | [Scenes and spawning]({{ "/reference/scenes/" | relative_url }}) |
| Rover control, sensing, ground truth and wheel odometry | [Technical reference]({{ "/reference/" | relative_url }}) |
| GUI or headless operation, optional ROS 2 Jazzy | [Runtime modes]({{ "/reference/runtime/" | relative_url }}) |
| Configurable sunlight, dust appearance and rendering | [Atmosphere]({{ "/reference/atmosphere/" | relative_url }}) |

Scene generation, trajectory followers and experiment/evaluation tools are outside the current distribution. The paper describes experiments conducted with the platform; it does not imply those external tools ship in this repository.

One rover is selected per run. [Ingenuity]({{ "/robots/ingenuity/" | relative_url }}) and simultaneous multi-robot simulation are development directions, not supported `main` workflows.

## Explore before installing

The [interactive lab]({{ "/demo/" | relative_url }}) replays recorded MarsLab terrain, sensor observations and SLAM output in the browser. It needs no Isaac Sim installation. Moving the browser camera does not generate new observations.

Read the [paper and benchmarks]({{ "/research/" | relative_url }}) for the original research setup and results.

## About these docs

Usage and reference pages describe the checked-in `main` runtime and supplied profiles. Robot pages distinguish mission-derived data, geometry estimates and simulation settings. See [model assumptions]({{ "/reference/model-assumptions/" | relative_url }}) before using those values as real spacecraft specifications.
