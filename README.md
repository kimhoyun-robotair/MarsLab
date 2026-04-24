# MarsLab

Photorealistic Mars simulation platform for heterogeneous planetary robotics research,
built on NVIDIA Isaac Sim 5.1.0.

**Target:** ICRA 2027 Seoul submission

**License:** Apache 2.0

## Overview

MarsLab generates photorealistic synthetic Mars imagery for perception tasks:
object detection, semantic segmentation, and sensor data generation. It supports
multiple robot types (rover, rotorcraft, quadruped) in physically accurate Mars
environments with configurable atmospheric conditions.

### Key Features

- **Mars terrain**: HiRISE DEM loading + procedural generation (flat, crater, hills)
- **Mars atmosphere**: Beer's Law irradiance, COMIMART diffuse model, butterscotch sky
- **Rock distribution**: Golombek & Rapp (1997) size-frequency distribution
- **Multi-robot**: Rover (URDF), rotorcraft (kinematic), quadruped (Go2 USD)
- **Rendering**: RTX path-tracing with Mars-calibrated fog, lighting, sky dome
- **Config-driven**: All parameters in YAML, zero hardcoded constants
- **Seed reproducibility**: Every randomized process accepts a seed parameter

## Requirements

- **NVIDIA Isaac Sim 5.1.0** (standalone installation)
- **Python 3.10+** (system Python for offline modules)
- **GPU**: NVIDIA RTX series (tested on RTX 5070 Ti)
- **OS**: Ubuntu 22.04+

### Python Dependencies

```
pydantic>=2.0    # Config schema validation
pyyaml>=6.0      # YAML loading
numpy>=1.24      # Numerical computation
GDAL>=3.8        # HiRISE DEM loading (system libgdal-dev required)
scipy>=1.10      # Procedural terrain generation
```

## Installation

### 1. Isaac Sim

Install Isaac Sim 5.1.0 following the
[official guide](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/quick-install.html).

### 2. System Dependencies

```bash
# GDAL C libraries (required for DEM loading)
sudo apt-get install -y libgdal-dev gdal-bin
```

### 3. MarsLab Package

```bash
git clone https://github.com/kimhoyun-robotair/MarsLab.git
cd MarsLab

# Install with development dependencies
pip install -e ".[dev]"
```

## Quick Start

### Run Unit Tests (no GPU needed)

```bash
pytest tests/unit/ -v
```

### Developer Hygiene (black + ruff + mypy + pip-audit)

All three CI checks plus a typing scope and a dependency audit are wired to
`pyproject.toml` (Reviewer 2 #18, 2026-04-24):

```bash
# One-time per clone: install pre-commit hooks so black/ruff run on every commit.
pip install pre-commit
pre-commit install

# Manual full sweep (matches CI):
black --check marslab/ scripts/ tests/
ruff  check   marslab/ scripts/ tests/
pytest tests/unit/ -q
mypy                           # scoped to marslab/config + marslab/environment
pip-audit --strict             # fails on any known CVE in installed deps
```

The ruff ruleset is `E,F,W,I,B,SIM`.  Adding `UP` (pyupgrade) is deferred to a
dedicated refactor — it currently surfaces ~290 violations, almost all of them
`List[X]` -> `list[X]` / `Optional[X]` -> `X | None`.

### Run Full Mars Scene (Isaac Sim required)

```bash
PYTHONPATH=/path/to/MarsLab ~/isaacsim/python.sh scripts/run_scene.py
```

### Run Integration Tests (Isaac Sim required)

The integration suite lives under `tests/integration/` and is VCS-tracked
(Reviewer 2 #15 reinstate, 2026-04-24).  All tests are gated on
`pytest.importorskip("isaacsim")` and marked `@pytest.mark.integration`,
so the default `pytest tests/unit/` run skips them cleanly on hosts
without a GPU.

Current inventory (3 integration tests + scaffolding):

| Test file                                               | What it proves                                               |
|--------------------------------------------------------|---------------------------------------------------------------|
| `tests/integration/test_imu_gravity_actual.py`         | Rover IMU z-axis within 3.72 +/- 0.05 m/s^2 (Wk1 gate)        |
| `tests/integration/test_robot_spawn_ros2_topics.py`    | `/rover/odom` publishes within 30 s of Stage-3 boot           |
| `tests/integration/test_slam_toolbox_receives_scan.py` | `/rover/scan` visible under slam_toolbox QoS (BEST_EFFORT)    |

Invoke through the `scripts/isaac_python.sh` wrapper, which strips the
system ROS 2 Jazzy environment before handing off to Isaac Sim's bundled
Python.  The `scripts/run_integration_test.py` entry point overrides
`addopts=-m 'not integration'` and runs exactly the integration suite:

```bash
# Run every integration test
scripts/isaac_python.sh scripts/run_integration_test.py

# Run a specific file
scripts/isaac_python.sh scripts/run_integration_test.py \
    tests/integration/test_imu_gravity_actual.py

# Run a specific nodeid
scripts/isaac_python.sh scripts/run_integration_test.py \
    tests/integration/test_imu_gravity_actual.py::test_imu_z_gravity_within_mars_band
```

> The older `scripts/run_scene_test.py` / `scripts/run_multi_robot_test.py`
> entry points advertised in the Phase 1a README have been retired — the
> equivalents now live as `scripts/phase1/run_stage4.py` (Stage-3 runtime)
> and the scenario-specific YAMLs under `configs/scenarios/`.

### Offline Visualizations (no GPU needed)

```bash
python3 scripts/visualize_terrain.py       # DEM + rock placement
python3 scripts/visualize_atmosphere.py    # Atmosphere physics plots
python3 scripts/visualize_procedural.py    # Procedural terrain comparison
```

## Project Structure

```
MarsLab/
├── marslab/                    # Main Python package
│   ├── config/                 # YAML loading + pydantic validation
│   ├── environment/            # Mars physics (pure Python, no Isaac Sim)
│   │   ├── sun_position.py     # Sun azimuth/elevation
│   │   ├── light_intensity.py  # Beer's Law direct irradiance
│   │   ├── diffuse_fraction.py # COMIMART diffuse model
│   │   └── sky_dome.py         # Sky color/brightness from tau
│   ├── terrain/                # Terrain generation
│   │   ├── dem_loader.py       # HiRISE GeoTIFF loading (GDAL)
│   │   ├── rock_placer.py      # Golombek SFD rock distribution
│   │   ├── procedural_generator.py  # Flat/crater/hills presets
│   │   ├── mesh_builder.py     # Elevation → USD mesh (Isaac Sim)
│   │   └── material_applicator.py   # Mars PBR materials (Isaac Sim)
│   ├── rendering/              # Isaac Sim rendering config
│   │   ├── render_settings.py  # Path-tracing / ray-tracing mode
│   │   ├── sky_renderer.py     # Dome light configuration
│   │   ├── sun_renderer.py     # Directional light (sun)
│   │   └── atmosphere_fog.py   # Dust haze / fog
│   ├── robots/                 # Robot spawning (Isaac Sim)
│   │   ├── rover.py            # 6-wheeled rover (URDF)
│   │   ├── rotorcraft.py       # Ingenuity-class (kinematic)
│   │   └── quadruped.py        # Unitree Go2 (built-in USD)
│   └── utils/                  # Shared utilities
│       └── seed.py             # Global seed management
├── configs/                    # All YAML configurations
├── tests/                      # Unit + integration tests
├── scripts/                    # Entry points + visualization
├── assets/                     # Robot URDFs, terrain data
└── work_log/                   # Development history
```

## Configuration

All parameters are in `configs/mars_env.yaml`. Key sections:

```yaml
mars_env:
  gravity: 3.72              # Mars surface gravity (m/s^2)
  dust_optical_depth: 0.3    # Atmosphere dust (tau)
  sun_elevation_deg: 45      # Sun position

terrain:
  source: "procedural"       # or "hirise"
  procedural_preset: "crater" # flat, crater, hills

robots:
  - type: "rover"
  - type: "rotorcraft"
  - type: "quadruped"
```

## Current Status (Phase 1a Complete)

| Module | Status | Tests |
|--------|--------|-------|
| config/ | Complete | 27 |
| environment/ | Complete | 30 |
| terrain/ | Complete | 46 |
| rendering/ | Complete | Isaac Sim integration |
| robots/ | Complete (3 types) | Isaac Sim integration |
| **Total** | | **130 unit + 11 integration** |

## References

- Golombek, M.P. & Rapp, D. (1997). Size-frequency distributions of rocks on Mars. JGR Planets.
- Vicente-Retortillo, A. et al. (2015). Solar radiation fluxes on Mars. JSWSC.
- Appelbaum, J. & Flood, D.J. (1990). Solar radiation on Mars. NASA TM-102299.
- Bell, J.F. et al. (2006). Chromaticity of the Martian sky. JGR Planets.


scripts/isaac_python.sh scripts/phase1/run_stage4.py --config configs/scenarios/jezero_flat.yaml
# 여기서 YAML 파일 이름만 바꿔가면서 진행하면 됨.

scripts/isaac_python.sh scripts/phase1/run_stage2.py --config configs/mars_env.yaml
scripts/isaac_python.sh scripts/phase1/run_stage4.py --config configs/scenarios/jezero_flat.yaml