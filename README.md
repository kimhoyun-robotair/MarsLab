<div align="center">

# MarsLab

### A Martian Rover Simulator for Planetary Rover Autonomous Navigation

**Hoyun Kim · Beomsu Kim · Giseop Kim**<br />
Department of Robotics and Mechatronics Engineering, DGIST

[Project website](https://kimhoyun-robotair.github.io/MarsLab/) · [Documentation](https://kimhoyun-robotair.github.io/MarsLab/guide/) · [Interactive demo](https://kimhoyun-robotair.github.io/MarsLab/demo/) · [Paper](https://kimhoyun-robotair.github.io/MarsLab/MarsLab.pdf)

[![MarsLab simulation](https://kimhoyun-robotair.github.io/MarsLab/asset/showcase/drive-canyon.jpg)](https://www.youtube.com/watch?v=gkr9NTTGlTw)

**NVIDIA Isaac Sim 5.x · Optional ROS 2 Jazzy · YAML configuration**

</div>

MarsLab is a configuration-driven platform for planetary-rover autonomy and
navigation research. Combine a Martian scene with a rover profile, tune physics,
sensing and atmospheric appearance, and connect an external autonomy stack
through ROS 2.

## Supported robots

| Profile | Included sensing |
| --- | --- |
| **Perseverance** (default) | Research RGB-D camera, 2-D/3-D LiDAR, IMU |
| **Spirit** | 9 camera models, IMU |
| **Opportunity** | 9 camera models, IMU |
| **Curiosity** | 17 camera models, IMU |

All four share the rover-control and wheel-odometry workflow. Select one per run.
See the [robot guide](docs/robots/index.md) for profile differences
and simulation assumptions. Ingenuity and simultaneous multi-robot simulation
remain under development.

## Getting started

First follow the [installation guide](docs/guide/installation.md):
install Isaac Sim, clone this repository, download a prebuilt Mars scene into
`assets/scene/`, and install `requirements.txt` in the Python environments you use.
The default scene is `assets/scene/jezero_plain/jezero_plain.usdz`.

Run from the repository root. The launcher expects Isaac Sim at `$HOME/isaacsim`;
set `ISAAC_SIM_PATH` if your installation is elsewhere.

**Terminal 1 — Isaac Sim** (do not source system ROS here):

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```

**Terminal 2 — optional ROS companion**, with `runtime.ros2_enabled: true` and the
system `.venv` prepared as described in installation:

```bash
source /opt/ros/jazzy/setup.bash
.venv/bin/python /opt/ros/jazzy/bin/ros2 launch \
  launch/rover_state_publisher.launch.py
```

To use another rover, add `--robot curiosity` (or `spirit` / `opportunity`) to the
Isaac command and `robot:=curiosity` to the ROS launch command. Pass the same
scenario and robot selection to both processes. All ROS processes must share
`ROS_DOMAIN_ID`.

The [first-run guide](docs/guide/quickstart.md) covers selection,
camera inspection and next steps. The supplied camera topics use best-effort QoS.

## Documentation

The [documentation website](https://kimhoyun-robotair.github.io/MarsLab/guide/)
provides navigation, search and technical reference. Its Markdown sources are
kept in this repository:

| Topic | Source |
| --- | --- |
| Installation and first run | [User guide](docs/guide/index.md) |
| Rover selection and sensor differences | [Robot profiles](docs/robots/index.md) |
| Configuration, physics, sensing, ROS and TF | [Technical reference](docs/reference/index.md) |
| Source layout and startup ownership | [Architecture](docs/development/index.md) |
| Extending the rover set | [Adding a rover](docs/development/adding-a-rover.md) |
| Planned capabilities | [Roadmap](docs/development/roadmap.md) |
| Website development and local preview | [docs/README.md](docs/README.md) |

The scenario lives in [`configs/config.yaml`](configs/config.yaml); robot settings
live in [`configs/robots/`](configs/robots/). See
[configuration composition](docs/reference/configuration.md)
before adding overrides.

## Research and scope

The [paper and benchmarks](https://kimhoyun-robotair.github.io/MarsLab/research/)
describe the original Perseverance research setup. The browser demo replays
recorded simulation and SLAM output; it does not run Isaac Sim or SLAM in the browser.

The runtime consumes prebuilt USDZ environments. Scene generation, trajectory
followers and evaluation pipelines are outside the current distribution.
**Scene Generation v2.0 is in development.**

Robot dimensions, camera calibrations and visual sources have different levels
of fidelity. Read the [model assumptions](docs/reference/model-assumptions.md)
and [atmosphere limits](docs/reference/atmosphere.md) before
interpreting simulation settings as flight specifications or physical measurements.

## Citation

```bibtex
@inproceedings{kim2026marslab,
  title={MarsLab: A Martian Rover Simulator for Planetary Rover Autonomous Navigation},
  author={Kim, Hoyun and Kim, Beomsu and Kim, Giseop},
  booktitle={International Conference on Space Robotics (iSpaRo)},
  year={2026}
}
```
