<div align="center">

# 🚀 MarsLab

### A Martian Rover Simulator for Planetary Rover Autonomous Navigation

**Hoyun Kim · Beomsu Kim · Giseop Kim**<br />
*Department of Robotics and Mechatronics Engineering, DGIST*

<p>
  <a href="https://kimhoyun-robotair.github.io/MarsLab/">
    <img src="https://img.shields.io/badge/Project_Page-C1440E?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Project Page" />
  </a>
  &nbsp;
  <a href="https://kimhoyun-robotair.github.io/MarsLab/MarsLab.pdf">
    <img src="https://img.shields.io/badge/Paper-DC2626?style=for-the-badge&logo=adobeacrobatreader&logoColor=white" alt="Paper" />
  </a>
  &nbsp;
  <a href="https://drive.google.com/drive/folders/1evy98zVN0zn-F4Ga3ATRxnYj0xcarkEK?usp=drive_link">
    <img src="https://img.shields.io/badge/Scene_Assets-2563EB?style=for-the-badge&logo=googledrive&logoColor=white" alt="Scene Assets" />
  </a>
</p>

<p>
  <img src="https://img.shields.io/badge/NVIDIA_Isaac_Sim-5.x-76B900?style=flat-square&logo=nvidia&logoColor=white" alt="NVIDIA Isaac Sim 5.x" />
  <img src="https://img.shields.io/badge/ROS_2-Jazzy-22314E?style=flat-square&logo=ros&logoColor=white" alt="ROS 2 Jazzy" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/Config-YAML-CB171E?style=flat-square&logo=yaml&logoColor=white" alt="YAML configuration" />
</p>

<br />

<a href="https://www.youtube.com/watch?v=gkr9NTTGlTw">
  <img src="https://img.youtube.com/vi/gkr9NTTGlTw/maxresdefault.jpg" width="960" alt="Watch the MarsLab video on YouTube" />
</a>
<br />
<a href="https://www.youtube.com/watch?v=gkr9NTTGlTw">▶ Watch the MarsLab video on YouTube</a>

</div>

<br />

> **MarsLab** is a configuration-driven NVIDIA Isaac Sim 5.x platform for
> controlled planetary-rover autonomy and navigation research. It combines
> Martian terrain, selectable Mars rovers, physically grounded sensors, atmospheric
> rendering, vehicle control, evaluation ground truth, wheel odometry, and an
> optional ROS 2 Jazzy bridge in one runtime.

---

> [!IMPORTANT]
> **🚧 Scene Generation v2.0 — In Development**
>
> We are preparing Version 2.0 of MarsLab's scene-generation pipeline,
> with improved photorealism and more detailed modeling of the Martian
> environment and its physical properties.
>
> Scene-generation tools are currently not included in this repository.
> Please stay tuned for future updates.

## 🧭 Overview

Each run combines a scenario such as [`configs/config.yaml`](configs/config.yaml)
with its selected rover profile from [`configs/robots/`](configs/robots/).
The supplied scenario selects `perseverance` and preserves the existing M2020
behavior. MarsLab validates the composed configuration and required assets
before Isaac Sim starts, loads the selected scene, spawns
the rover, runs the simulation loop, and releases runtime resources in reverse
order at shutdown.

This repository provides the rover runtime for prebuilt USDZ environments.
Scene generation, trajectory followers, and experiment/evaluation pipelines
are outside the current distribution. External applications can use the ROS
interfaces below.

```mermaid
flowchart LR
    CFG["⚙️ Scenario YAML"] --> CORE["🚀 MarsLab Runtime"]
    PROFILE["🛞 configs/robots/ profile"] --> CORE
    CORE --> ISAAC["NVIDIA Isaac Sim 5.x"]

    ISAAC --> ENV["🏜️ Mars Environment"]
    ISAAC --> ROVER["🛞 Selected Rover"]

    ROVER --> SENSOR["📡 RGB / Depth / LiDAR / IMU"]
    ROVER --> ODOM["🧭 Wheel Odometry"]
    ISAAC --> GT["📍 Ground Truth"]

    SENSOR --> ROS["ROS 2 Jazzy"]
    ODOM --> ROS
    GT --> ROS
    ROS --> AUTONOMY["External SLAM / Navigation / VPR"]
```

### ✨ Highlights

- 🏜️ **Configurable Martian environments** — select supplied USDZ scenes and tune
  gravity, sunlight, atmospheric dust, fog, and sky-dome appearance.
- 🛞 **Rover dynamics** — retain authored link masses with geometry-based CoM/inertia
  estimates and a passive rocker differential; configure chassis damping, wheel
  contact, rocker-bogie damping, steering, drive gains, control limits, and spawn
  behavior. The controller supports curved driving and pivot turns.
- 📷 **Multi-modal sensing** — RGB, depth, camera PointCloud2, CameraInfo, 2-D
  LaserScan, 3-D LiDAR, raw/noisy IMU, and configurable wheel-odometry and optional
  depth noise derived from the sensor seed.
- 🤖 **ROS 2 integration** — standard topics, simulation clock, joint states,
  robot description, QoS profiles, static sensor frames, and odometry TF control.
- 🧭 **Evaluation-ready motion outputs** — independent ground-truth and wheel
  odometry streams with distinct frames and ownership.
- 🔁 **Scenario and rover profiles** — reuse scenes, rocker-bogie control, and
  odometry with profile-specific geometry and joint names. The composed settings
  are strictly validated before Kit creation.
- 🖥️ **GUI and headless modes** — use the same configuration for interactive
  atmosphere studies or unattended simulation.

---

## Atmosphere defaults

Runs start at **tau=0.05** with a fixed manual sun. The GUI supports tau=0.05–6
and sun elevation 0–90°; Auto Sweep continues from the latest sun angles. The sun
uses Beer-law direct irradiance. Diffuse light evaluates a tau-indexed NIR
COMIMART reduction at fixed reference conditions and applies a configurable
sky-dome gain; simple fog remains an appearance approximation. See the
[model conditions](assets/atmosphere/README.md).
See the [model limits and atmosphere settings](CONFIGURATION_GUIDE.md#mars-environment-and-atmosphere)
before interpreting lighting values as physical measurements.

## 🏜️ Research Environments

The supplied configuration selects Jezero Plain. Other prebuilt environments
include Main Crater, Grand Canyon, and Mars Base. Select a USDZ and adjust its
runtime illumination and atmospheric appearance.

<table>
<tr>
<td width="33%" align="center" valign="top">

<img src="https://kimhoyun-robotair.github.io/MarsLab/asset/fig03_marsbase1.png" width="100%" alt="Mars Base scene" />

**Mars Base**<br />
Landmark-rich structured terrain.

</td>
<td width="33%" align="center" valign="top">

<img src="https://kimhoyun-robotair.github.io/MarsLab/asset/showcase/crater.jpg" width="100%" alt="Main Crater scene" />

**Main Crater**<br />
Open crater terrain with sparse structure.

</td>
<td width="33%" align="center" valign="top">

<img src="https://kimhoyun-robotair.github.io/MarsLab/asset/showcase/canyon.jpg" width="100%" alt="Mars Canyon scene" />

**Mars Canyon**<br />
Long-range terrain with challenging geometry.

</td>
</tr>
</table>

Paper benchmark results and recorded demonstrations of environments,
illumination changes, and dust are available on the
[**MarsLab Project Page**](https://kimhoyun-robotair.github.io/MarsLab/).

---

## 📋 Requirements

| Component | Requirement |
|:---|:---|
| **Operating system** | Linux supported by Isaac Sim 5.x |
| **NVIDIA Isaac Sim** | 5.x |
| **ROS 2** | Jazzy, optional and required only for ROS interfaces |
| **Python** | 3.11+ for offline configuration and utility work |
| **GPU** | NVIDIA GPU supported by the selected Isaac Sim renderer |
| **Rover assets** | Runtime USD, URDF, meshes, and textures included in this repository |
| **Scene asset** | A downloaded Mars scene referenced by `scene.usdz_path` |

> [!IMPORTANT]
> Isaac Sim and system ROS 2 are separate environments. Do not source the
> system ROS setup script in the terminal used to launch MarsLab.

---

## ⚙️ Installation

### 1. Clone MarsLab

```bash
git clone https://github.com/kimhoyun-robotair/MarsLab.git
cd MarsLab
```

The Perseverance USD and companion URDF are included under
`assets/robots/perseverance/`, alongside the URDF's meshes and textures in
`meshes/`. Their source and rights are recorded in
[the M2020 notice](assets/robots/perseverance/LICENSE.md).

### 2. Download the Mars scene assets

Download the scene package from
[**Google Drive — MarsLab Scene Assets**](https://drive.google.com/drive/folders/1evy98zVN0zn-F4Ga3ATRxnYj0xcarkEK?usp=drive_link),
then extract or copy the scene directories into `assets/scene/`.

The supplied configuration expects this default file:

```text
assets/scene/
└── jezero_plain/
    └── jezero_plain.usdz
```

Other downloaded environments can be stored beside `jezero_plain`. Select one
by changing `scene.usdz_path` in `configs/config.yaml`. MarsLab consumes these
assets as inputs; it does not generate or convert terrain during startup.

### 3. Install the Python dependencies

Run MarsLab from this checkout. [requirements.txt](requirements.txt) declares
the Python dependencies for the simulator, configuration tools, and ROS
companion. Install them into each Python environment you use.

By default, the launcher looks for Isaac Sim at `$HOME/isaacsim`. If Isaac Sim
is installed elsewhere, set its installation directory for the current shell:

```bash
export ISAAC_SIM_PATH=/path/to/isaacsim
```

In the Isaac terminal, install the dependencies using its bundled Python:

```bash
marslab/isaac_python.sh -m pip install -r requirements.txt
```

For the ROS companion or offline configuration tools, create a separate virtual
environment using the system Python. The `python3-venv` OS package is required.
System packages remain visible so the environment can use the installed ROS 2
Jazzy packages:

```bash
/usr/bin/python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
```

The ROS commands below explicitly use this environment's Python. Installing
dependencies there does not install them into Isaac Sim's bundled Python.

---

## 🚀 Quick Start

MarsLab and its ROS 2 companion run in **separate terminals**.

<table>
<tr>
<td width="50%" valign="top">

### 🖥️ Terminal 1 — Isaac Sim

Do **not** source system ROS in this terminal.

```bash
marslab/isaac_python.sh \
  marslab/main.py \
  --config configs/config.yaml
```

The wrapper starts Isaac Sim's bundled Python and supplies its bundled Jazzy
bridge libraries to the child process.
An explicit `--robot perseverance` selects the same default profile. Select
another supplied profile with `--robot spirit`, `--robot opportunity`, or
`--robot curiosity`.

</td>
<td width="50%" valign="top">

### 🤖 Terminal 2 — ROS 2

Use with `runtime.ros2_enabled: true`.

```bash
source /opt/ros/jazzy/setup.bash
.venv/bin/python /opt/ros/jazzy/bin/ros2 launch \
  launch/rover_state_publisher.launch.py
```

The companion reads the same scenario and rover profile to select the URDF,
namespace, and joint-state topic. The supplied profiles use the `rover` namespace.

</td>
</tr>
</table>

> [!TIP]
> Pass the same configuration and robot selection to both terminals. For example,
> `--config configs/config.yaml --robot curiosity` in Isaac corresponds to
> `config:=configs/config.yaml robot:=curiosity` in the ROS launch command.
> With no robot argument, both follow the scenario's `robot` selector.

Keep both files in `launch/`. The launch file loads
[`companion_urdf.py`](launch/companion_urdf.py) to prepare the selected URDF and
resolve relative mesh paths for ROS. It then starts `robot_state_publisher`
and connects `base_link` to the URDF root when they differ (`Body_Chassis` for
the default profile).

For Curiosity, the ROS terminal command is:

```bash
source /opt/ros/jazzy/setup.bash
.venv/bin/python /opt/ros/jazzy/bin/ros2 launch launch/rover_state_publisher.launch.py \
  config:=configs/config.yaml robot:=curiosity
```

The primary navigation image remains `/rover/rgb/image_raw`, with CameraInfo at
`/rover/rgb/camera_info`. Every additional configured camera publishes
`/rover/cameras/<name>/image_raw` and `/rover/cameras/<name>/camera_info`;
for example, `/rover/cameras/mastcam_left/image_raw`. These are best-effort
sensor topics in the supplied profiles; set RViz Image reliability to
**Best Effort**. All ROS processes must use the same `ROS_DOMAIN_ID`.

### Startup sequence

1. Compose the scenario and selected robot profile, then strictly validate them.
2. Resolve asset paths relative to each declaring YAML and check required files.
3. Start Isaac Sim and create the Mars world.
4. Reference the selected terrain and rover USD assets.
5. Apply YAML-owned rover physics and create the configured camera, IMU, and optional LiDAR sensors.
6. Initialize optional atmosphere GUI and ROS 2 interfaces.
7. Enter the simulation, control, sensing, and publication loop.

The World owns one PhysicsScene with the configured Mars gravity. PhysicsScenes
inside the referenced terrain are disabled in the runtime session layer, and
their effective simulation owners are redirected to the World scene.
The input assets remain unchanged.

---

## 🔧 Configuration

[`configs/config.yaml`](configs/config.yaml) holds the scenario. Its `robot`
selector loads [`configs/robots/perseverance.yaml`](configs/robots/perseverance.yaml)
by default. `--robot <name>` overrides that selector without changing the file.
Rover dimensions, joint and link names, drive gains, and sensor settings belong
to the rover profile, so the same controller and wheel-odometry code can be
reused across models.

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml --robot curiosity
```

| Robot | Profile | Model and source notes |
|:---|:---|:---|
| Perseverance (default) | [perseverance.yaml](configs/robots/perseverance.yaml) | [Technical report](techreport/perseverance_like.md) |
| Spirit | [spirit.yaml](configs/robots/spirit.yaml) | [Technical report](techreport/spirit.md) |
| Opportunity | [opportunity.yaml](configs/robots/opportunity.yaml) | [Technical report](techreport/opportunity.md) |
| Curiosity | [curiosity.yaml](configs/robots/curiosity.yaml) | [Technical report](techreport/curiosity.md) |

All four profiles use a **4 m/s linear command cap**. This is a shared MarsLab
simulation setting; the reports retain the much lower flight-speed references
separately. Scenario overrides can change this cap.

| Section | Purpose |
|:---|:---|
| `robot` | Select `configs/robots/<name>.yaml` |
| `scene` | Downloaded Scene USDZ path |
| `runtime` | GUI/headless, ROS 2, and atmosphere switches |
| `mars_env` | Gravity, dust, sunlight, sol timing, and dynamic atmosphere |
| `rendering` | Ray/path tracing, sky dome, sun, and fog |
| `rover` | Optional scenario overrides for the selected profile |
| `wheel_odom` | Dynamic `odom → base_link` TF ownership gate |

Selected settings from the supplied configuration:

```yaml
robot: perseverance

scene:
  usdz_path: ../assets/scene/jezero_plain/jezero_plain.usdz

runtime:
  headless: false
  ros2_enabled: true
  atmosphere_enabled: true

rendering:
  mode: ray_tracing

wheel_odom:
  publish_tf: true
```

Inline `rover` overrides merge nested mappings and replace whole lists. Each
relative asset path is resolved from the YAML that declares it: `../assets/`
in the scenario, `../../assets/` in the supplied rover profiles. Complete legacy
one-file configurations still load without a selector. Selecting `--robot` for
such a legacy file replaces its original rover settings with the chosen profile.

NASA visual-source provenance and rights information are recorded in
[LICENSE-NASA-3D-RESOURCES.txt](LICENSE-NASA-3D-RESOURCES.txt), with sensor-data
sources in [LICENSE-NAIF.txt](LICENSE-NAIF.txt). These visual models do not
constitute NASA-issued URDFs or measured flight mass/inertia distributions.

The mission models acquire 17 Curiosity cameras and 9 cameras on each MER rover,
plus an ideal IMU. Cameras use pinhole projections from published calibration;
the source coefficients are preserved. Science instruments and their subcomponents
are represented by sourced USD inventory and interface metadata: spectra, chemistry,
weather, and radiation measurements are not simulated. Per-link mass allocation,
collision shapes, and controller gains are documented simulation approximations.

Spirit and Opportunity's Microscopic Imager is mounted at the visible stowed
arm's optics housing. Its original NASA calibration reference pose is retained
separately; the stowed mounting pose is derived from the NASA visualization
geometry, not a flight calibration. USD cameras and their ROS TF use the same
mounting pose. Startup rejects a camera configuration that disagrees with its
authored USD pose; see the corresponding technical report for the source and limits.

Curiosity has 22 rigid links and 21 movable joints, including five arm joints and
mast pan/tilt. Its seven mast cameras follow `Body_MastTilt`; MAHLI follows
`Body_ArmTurret` with a visualization-derived mounting pose. The common
`robot_state_publisher` launch loads the corresponding URDF and publishes these
links from the simulator's joint states. The added drives hold their neutral
pose by default; `cmd_vel` still controls mobility, and no arm trajectory
controller is supplied. Space ROS was consulted for comparison, while the
runtime geometry and joint derivation use the documented NASA sources. The
articulated model uses estimated link inertias rather than forcing the older
NASA landing-test aggregate onto the deployed arm configuration; numerical
values and source distinctions are in [Curiosity's technical report](techreport/curiosity.md).

On 2026-10-23, the current mission assets each passed a separate 600-second
wall-clock run in Isaac Sim 5.1 on an RTX 5090, with the full Jezero plain,
atmosphere, ROS and all cameras at native resolution. Physics advanced 262.617
seconds for Spirit, 261.733 for Opportunity and 125.050 for Curiosity. The runs
covered forward/reverse, both turning and pivot directions, and stops. Separate
ROS 2 Jazzy subscribers verified all 35 Image/CameraInfo streams, selected
robot descriptions, joint states, clock, IMU and complete link/camera TF chains.
Final native error counts were zero; physics states and memory remained stable.

Curiosity additionally exercised all seven added joints while comparing actual
PhysX body and rendered-camera poses with URDF forward kinematics and external
TF. Small test excursions were ±0.10 rad for the mast and ±0.05 rad for the arm;
this does not certify full-range manipulation. An isolated actual Stop/Play
test invoking the production reset owner verified target preservation and
restoration. A short Perseverance regression also passed. The installed RViz
mesh loader decoded all 52 mission DAE files and 187 texture bindings without
errors. Generation tools, test code, raw logs and execution-hash reports stay
under the ignored `tmp/` directory, including `tmp/stress_articulation/` and
`tmp/texture_fix/`.

For renderer modes, scene and spawn selection, atmosphere tuning, rover physics,
sensor profiles, ROS QoS, frame ownership, and odometry parameters, read the
**[Configuration and Tuning Guide](CONFIGURATION_GUIDE.md)** before editing the
YAML.

---

## 📡 Runtime Interfaces

With ROS 2 enabled, the supplied configuration exposes:

| Interface | Default topic | Notes |
|:---|:---|:---|
| Command input | `/rover/cmd_vel` | `geometry_msgs/Twist` |
| RGB image | `/rover/rgb/image_raw` | Shared Camera render product |
| Depth image | `/rover/depth/image_raw` | Shared Camera render product |
| Camera point cloud | `/rover/depth/points` | XYZ `sensor_msgs/PointCloud2` |
| Camera calibration | `/rover/rgb/camera_info` | `sensor_msgs/CameraInfo` |
| Raw IMU | `/rover/imu` | `imu_link` |
| Noisy IMU | `/rover/imu_noisy` | Seeded noise stream |
| 2-D LiDAR | `/rover/scan` | `sensor_msgs/LaserScan`, `lidar_2d_link` |
| 3-D LiDAR | `/rover/lidar/points` | `lidar_link` |
| Joint states | `/rover/joint_states` | Consumed by the companion |
| Robot description | `/rover/robot_description` | Companion-owned latched URDF text |
| Ground truth | `/rover/GT_Trajectory` | `map → base_link_gt`, topic only |
| Wheel odometry | `/rover/odom` | `odom → base_link` |
| Simulation clock | `/clock` | Isaac simulation time |

Ground truth never publishes TF. `wheel_odom.publish_tf` is the only MarsLab
switch for dynamic `odom → base_link` TF ownership.

The supplied sensor settings are:

| Sensor | Field of view | Configured distance limits |
|:---|:---|:---|
| Camera at the left Navcam mast reference | 135° horizontal, about 122.18° vertical | 0.3–200 m along the optical axis |
| 2-D LiDAR | Forward 135° output sector | 0.2–200 m |
| 3-D LiDAR | 220° horizontal, 45° vertical | 3.5–200 m |

Depth noise is disabled by default. Camera PointCloud2 contains XYZ fields.
The 2-D sensor acquires a full rotation internally and crops its output to the
forward sector. Range settings are limits; actual returns depend on visibility,
surface response, and scene geometry. See the sensor sections in the
[configuration guide](CONFIGURATION_GUIDE.md#sensors).

---

## 🧩 System Ownership

```mermaid
flowchart TD
    MAP["map"] -. "ground-truth topic only" .-> GT["base_link_gt"]
    ODOM["odom"] -->|"wheel_odom.publish_tf"| BASE["base_link"]
    BASE -->|"companion: identity TF"| BODY["Selected URDF root"]
    BODY -->|"robot_state_publisher"| JOINTS["Rover articulation"]
    BODY -->|"MarsLab static TF"| CAMERA["camera_link / optical"]
    BODY -->|"MarsLab static TF"| LIDAR["lidar_link / lidar_2d_link"]
    BODY -->|"MarsLab static TF"| IMU["imu_link"]
```

- The ROS companion owns identity `base_link` to the selected URDF root and the URDF
  articulation chain.
- MarsLab owns retained sensor static frames below `rover.ros2.sensor_parent_frame_id`
  (`Body_Chassis` in the default profile).
- Ground truth is an evaluation stream and owns no TF.
- Wheel odometry is the operational estimate and may own dynamic odometry TF.

The default rover references `m2020_lidar.usda`; its companion uses
`m2020_lidar.urdf`. Both add modeled sensor housings and mounts to the preserved
rover asset, with merged chassis mass, COM and inertia. These are research
attachments, not flight Perseverance instruments. See
[mount assumptions and mass properties in the Perseverance-like report](techreport/perseverance_like.md).

---

## 📂 Project Structure

<details open>
<summary><b>Repository layout</b></summary>

```text
MarsLab/
├── README.md
├── CONFIGURATION_GUIDE.md
├── configs/
│   ├── config.yaml                 # Scenario and robot selector
│   └── robots/                     # Rover geometry, dynamics, and sensor profiles
├── assets/
│   ├── scene/                      # Downloaded Mars terrain USDZ inputs
│   ├── robots/                     # Rover USD, URDF, meshes, and physics layers
│   ├── mars_sky/                   # Sky-dome image assets
│   └── atmosphere/                 # Model references and scope
├── launch/
│   ├── rover_state_publisher.launch.py
│   └── companion_urdf.py           # Companion URDF preparation
├── docs/                           # Project page and recorded browser demo
├── marslab/
│   ├── main.py                     # Runtime entry point
│   ├── isaac_python.sh             # Isaac Python launcher
│   ├── config/                     # YAML loading and strict schemas
│   ├── environment/                # Isaac-free Mars calculations
│   ├── gui/                        # AtmospherePanel
│   ├── rendering/                  # Sky, sun, fog, and render settings
│   ├── robots/                     # Rover physics and control
│   ├── ros2_bridge/                # Topics, QoS, TF, and odometry
│   ├── runtime/                    # Assembly, loop, and cleanup lifecycle
│   ├── sensors/                    # Camera, IMU, and 2-D/3-D LiDAR
│   └── sim/                        # SimulationApp and world bootstrapping
└── requirements.txt                # Python dependencies for runtime and companion tools
```

</details>

---

## Third-party assets and notices

The root notices record each source, its credits, MarsLab's adaptations, and
the available rights information. They do not relicense third-party material.

| Asset or source | Notice |
| --- | --- |
| M2020 / Perseverance geometry and textures | [LICENSE-M2020.txt](LICENSE-M2020.txt) |
| NASA-3D-Resources Curiosity and MER visualization sources | [LICENSE-NASA-3D-RESOURCES.txt](LICENSE-NASA-3D-RESOURCES.txt) |
| NASA NAIF sensor and coordinate data | [LICENSE-NAIF.txt](LICENSE-NAIF.txt) |
| Three.js and browser-demo addons | [LICENSE-THREEJS.txt](LICENSE-THREEJS.txt) |
| COMIMART atmospheric reference | [LICENSE-COMIMART.txt](LICENSE-COMIMART.txt) |
| Mars Rocks visualization asset | [LICENSE-MARS-ROCKS.txt](LICENSE-MARS-ROCKS.txt) |
| HiRISE terrain and imagery sources | [LICENSE-HIRISE.txt](LICENSE-HIRISE.txt) |
| NOSA 1.3 reference agreement cited by NASA-3D-Resources metadata | [NASA-Open-Source-Agreement-1.3.pdf](NASA-Open-Source-Agreement-1.3.pdf) |

The browser demo also retains [its Three.js MIT notice](docs/demo/vendor/THREE-LICENSE.txt)
inside `docs/` for deployments of that directory alone. The NASA-3D-Resources
notice explains the scope and unresolved applicability of the NOSA reference.

---

## ✅ Validation Boundary

Offline checks can validate YAML structure, asset paths, schemas, and pure
computation. Isaac GUI appearance, rover physics, live sensor data, ROS topics,
QoS and TF, AtmospherePanel behavior, and shutdown cleanup must be verified in
the user's Isaac Sim and ROS installation.

For a chosen configuration, observe sensor messages, frame ownership, actual
rover steering, and Pause/Stop/Play behavior. Record the configuration, input
assets, and actual observations when reporting runtime results. A shared seed
controls MarsLab's custom noise streams; repeatability of complete physics and
rendered outputs requires separate verification.

---

# 🔭 Future Work

Planned improvements include:

- [x] Add 2D LiDAR.
- [ ] Integrate evaluation workflows for TUM, path planning, and SLAM.
- [ ] Integrate Nav2.
- [ ] Extend the existing Gaussian noise with sensor bias and time-varying drift models.
- [ ] Resolve vibration issues during runtime rendering.
- [ ] Improve the realism of sky and light rendering.
- [ ] Add photorealistic scene generation.
- [ ] Add wheel traces.
- [ ] Add support for multiple and heterogeneous robots.
- [ ] Dockerize MarsLab.
