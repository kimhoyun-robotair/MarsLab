---
title: Robot profiles
description: Compare the supported rover models and the future aerial integration.
permalink: /robots/
---

Four rover profiles share the same scenario loader, controller and ROS companion. Choose one per run with `--robot <name>` or the scenario's `robot` field.

## Supplied profiles

| Robot | Selector | Camera models | Synthetic depth | LiDAR |
| --- | --- | --- | --- | --- |
| [Perseverance]({{ "/robots/perseverance/" | relative_url }}) | `perseverance` | 1 | Enabled | 2-D + 3-D |
| [Spirit]({{ "/robots/spirit/" | relative_url }}) | `spirit` | 9 | Disabled | None |
| [Opportunity]({{ "/robots/opportunity/" | relative_url }}) | `opportunity` | 9 | Disabled | None |
| [Curiosity]({{ "/robots/curiosity/" | relative_url }}) | `curiosity` | 17 | Disabled | None |

All four provide an IMU, wheel odometry and ground-truth output. The camera count includes the primary camera and the named additional cameras. These are simulation-profile inventories, not complete flight payload specifications.

## Keep the experiment consistent

Pass the same robot selection to Isaac and the ROS companion. Profile geometry, joints, drive settings and sensor mounts belong in `configs/robots/`; scenario overrides are for the experiment. See [first run]({{ "/guide/quickstart/" | relative_url }}) and [configuration]({{ "/reference/configuration/" | relative_url }}).

The default 4.0 m/s linear command cap is shared simulation tuning. It is not a real mission speed specification. Read each profile's assumptions before comparing experiments.

## Aerial robotics

[Ingenuity]({{ "/robots/ingenuity/" | relative_url }}) is under development on a separate branch. It is not selectable in the documented `main` runtime. Its eventual flight stack will have a dedicated setup and reference.
