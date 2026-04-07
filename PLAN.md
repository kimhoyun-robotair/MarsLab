# PLAN.md -- MarsLab Architecture & Implementation Plan

**Version:** 2.0 (Final -- 13-Agent Adversarial Synthesis)
**Date:** 2026-04-07
**Target:** ICRA 2027 Seoul (deadline ~Sep 15, 2026)
**Timeline:** 22 weeks (Apr 7 -- Sep 15, 2026)
**License:** Apache 2.0

**Methodology:** This plan was produced through a 13-agent adversarial debate system.
Agents 1 and 6 independently drafted architecture-first and learning-path-first plans.
Agents 2-4 and 7-9 conducted cross-reviews identifying 19 critical issues. Agents 5 and
10-12 synthesized fixes into a unified specification. Agent 13 produced this final document.
All 19 critical fixes were applied (100% defense rate).

**Predecessor Documents:**
- `plan/marslab_plan_v2.pdf` -- Research Plan v2.0
- `plan/marslab_weekly_schedule_en.pdf` -- 22-Week Schedule
- `dev/architecture_blueprint_en.md` -- Architecture Blueprint (adversarially validated)
- `dev/mars_first_requirements_en.md` -- Mars-First Requirements Elicitation
- `dev/rlroverlab_analysis_en.md` -- RLRoverLab API Feasibility Analysis
- `dev/omnilrs_analysis_plan.md` -- OmniLRS Analysis Plan

---

## 1. Purpose

This document is the single source of truth for MarsLab development. It defines:

1. **What** the codebase architecture looks like (directory tree, modules, interfaces).
2. **How** each module is built (smallest unit first, incremental expansion).
3. **When** each piece is implemented (22-week Phase 1 schedule).
4. **How we verify** correctness (unit tests, integration tests, visual inspection).
5. **How we track** progress (work history log format).

Every developer -- including a third party joining mid-project -- should be able to read
this document and understand the entire project state, architecture rationale, and next
steps.

---

## 2. Guiding Principles

These 13 guidelines govern all architectural and implementation decisions. Every section
references the guidelines it implements by number (e.g., [G1]).

**[G1] Perceptual Robotics Focus.**
MarsLab is a photorealistic Mars robot simulator for perception tasks: object detection,
semantic segmentation, SLAM, navigation, and exploration. Phase 1 scope = OD + Seg +
sensor data generation. SLAM/Nav = Phase 2. RL is strictly future work (Phase 2+).

**[G2] RL is Future Work.**
No RL environments, reward functions, or training loops in Phase 1. Isaac Lab's Gym API
wrapper is deferred to Phase 2. All Phase 1 code serves perception and data generation.

**[G3] No Code Reuse from Reference Codebases.**
No code copied from OmniLRS, RLRoverLab, or any reference. Only algorithmic/flowchart
inspiration is permitted. Study the pattern, understand the algorithm, reimplement from
scratch using `omni.isaac.lab` APIs. No naming derived from `OmniLRS` or `RLRoverLab` in
MarsLab source. Note: `omni.*` is NVIDIA's namespace and is exempt from this rule.

**[G4] Photorealism is Top Priority.**
RTX path-tracing rendering quality is the primary differentiator. High-fidelity physics
(terramechanics) is secondary and deferred to Phase 2. Phase 1 physics = rigid body +
Mars-calibrated friction parameters.

**[G5] YAML-Driven Configuration.**
ALL environment parameters live in YAML config files. Zero hardcoded physical constants
in Python source. Changing a YAML parameter (gravity, dust opacity, albedo, rock density)
must alter the simulated environment without any code changes.

**[G6] Extreme Modularity.**
Start from the smallest possible unit: a single function, a single class, a single file.
Expand incrementally only when complexity demands it. The user must be able to follow the
flow and learn step by step. No premature abstraction, no god objects, no monolithic
modules.

**[G7] Unit Tests for Everything.**
Every module has unit tests. Pure computation modules (Mars physics, config validation,
rock SFD sampling) are tested offline without Isaac Sim. Isaac Sim-dependent modules use
integration tests. When automated testing is impossible, a documented GUI visual
inspection protocol is provided.

**[G8] Work History Log.**
Every completed task is summarized in a structured log entry. A new third party joining
the project can trace the full development history by reading the work log.

**[G9] Architecture-First Plan.**
This document includes both the codebase architecture AND the detailed implementation
plan. It is the master reference. All other planning documents are predecessors.

**[G10] User Review Gate.**
This plan is a draft for user review. The user will review, revise, and approve before
implementation begins. Checkpoints at Week 8 and Week 16.

**[G11] Ultrathink Throughout.**
Deep reasoning applied at every design decision. No shallow pattern-matching.

**[G12] 13-Agent Adversarial Debate.**
This plan was produced through multi-agent adversarial review, not single-pass generation.
All critical issues identified and resolved before finalization.

**[G13] Four Output Files.**
PLAN.md (EN), PLAN_kor.md (KR), CLAUDE.md (EN), CLAUDE_kor.md (KR) -- complete,
consistent, and cross-referenced.

---

## 3. Codebase Architecture

### 3.1 Architectural Principles

**P1: Flat P0 Architecture.**
No premature abstraction. Start with flat procedural code. Extract classes/patterns only
when empirical complexity demands it. No plugin systems, no god objects, no registration
mechanisms in Phase 1.

**P2: Unidirectional Data Flow.**
Config -> pure computation modules -> Isaac Sim scene configuration -> native sim loop.
No module modifies the simulation loop. No circular dependencies. Config is the only
shared dependency across modules.

**P3: Offline-First Testing.**
Every pure-computation module (environment physics, config validation, rock SFD, label
conversion) must be testable without Isaac Sim or GPU. Isaac Sim-dependent code is
isolated into separate functions/files clearly marked as integration-only.

### 3.2 Directory Tree

Every file listed with: (1) creation week, (2) guideline(s) it implements, (3) estimated
lines. Files are grouped by package subdirectory. [G6]

```
MarsLab/                                    # Repository root
|-- PLAN.md                                 # Wk 0 | G9       | ~800 lines
|-- CLAUDE.md                               # Wk 0 | G9       | ~250 lines
|-- README.md                               # Wk 8 | --       | ~100
|-- LICENSE                                 # Wk 0 | --       | Apache 2.0
|-- pyproject.toml                          # Wk 1 | G6       | ~50
|-- .gitignore                              # Wk 1 | --       | ~30
|
|-- .github/                                # CI/CD
|   `-- workflows/
|       |-- unit_tests.yaml                 # Wk 1 | G7       | ~40
|       `-- lint.yaml                       # Wk 1 | G7       | ~25
|
|-- configs/                                # ALL configuration [G5]
|   |-- mars_env.yaml                       # Wk 1 | G5       | ~60
|   |-- terrain/
|   |   |-- jezero_crater.yaml              # Wk 2 | G5       | ~25
|   |   |-- procedural_flat.yaml            # Wk 5 | G5       | ~20
|   |   |-- procedural_crater.yaml          # Wk 5 | G5       | ~25
|   |   `-- procedural_hills.yaml           # Wk 5 | G5       | ~25
|   |-- robots/
|   |   |-- rover.yaml                      # Wk 4 | G5       | ~30
|   |   |-- rotorcraft.yaml                 # Wk 7 | G5       | ~25
|   |   |-- quadruped.yaml                  # Wk 7 | G5       | ~20
|   |   `-- humanoid.yaml                   # Wk 10 | G5      | ~20
|   |-- sensors/
|   |   |-- stereo_rgb.yaml                 # Wk 11 | G5      | ~20
|   |   |-- depth_camera.yaml               # Wk 11 | G5      | ~15
|   |   |-- lidar_3d.yaml                   # Wk 11 | G5      | ~20
|   |   `-- imu.yaml                        # Wk 11 | G5      | ~15
|   |-- benchmark/
|   |   |-- terrain_seg.yaml                # Wk 13 | G5      | ~30
|   |   `-- domain_randomization.yaml       # Wk 13 | G5      | ~40
|   `-- rendering/
|       `-- path_tracing.yaml               # Wk 6 | G4,G5   | ~20
|
|-- marslab/                                # Main Python package
|   |-- __init__.py                         # Wk 1 | G6       | ~5
|   |
|   |-- config/                             # Configuration loading [G5][G6]
|   |   |-- __init__.py                     # Wk 1 |          | ~3
|   |   |-- schema.py                       # Wk 1 | G5       | ~150
|   |   `-- loader.py                       # Wk 1 | G5       | ~70
|   |
|   |-- environment/                        # Pure-Python Mars physics [G6]
|   |   |-- __init__.py                     # Wk 3 |          | ~3
|   |   |-- sun_position.py                 # Wk 3 | G5,G6    | ~60
|   |   |-- light_intensity.py              # Wk 3 | G5,G6    | ~40
|   |   |-- diffuse_fraction.py             # Wk 3 | G5,G6    | ~50
|   |   `-- sky_dome.py                     # Wk 3 | G4,G6    | ~50
|   |
|   |-- terrain/                            # Terrain gen + annotation [G6]
|   |   |-- __init__.py                     # Wk 2 |          | ~3
|   |   |-- dem_loader.py                   # Wk 2 | G5,G6    | ~70
|   |   |-- mesh_builder.py                 # Wk 4 | G6       | ~120
|   |   |-- rock_placer.py                  # Wk 2 | G5,G6    | ~90
|   |   |-- procedural_generator.py         # Wk 5 | G5,G6    | ~120
|   |   |-- material_applicator.py          # Wk 4 | G4,G6    | ~60
|   |   `-- semantic_labeler.py             # Wk 12 | G1,G6   | ~60
|   |
|   |-- rendering/                          # Mars rendering config [G4][G6]
|   |   |-- __init__.py                     # Wk 6 |          | ~3
|   |   |-- sky_renderer.py                 # Wk 6 | G4,G6    | ~60
|   |   |-- sun_renderer.py                 # Wk 6 | G4,G6    | ~70
|   |   |-- atmosphere_fog.py               # Wk 6 | G4,G6    | ~50
|   |   `-- render_settings.py              # Wk 6 | G4,G6    | ~40
|   |
|   |-- robots/                             # Robot spawning [G6]
|   |   |-- __init__.py                     # Wk 4 |          | ~3
|   |   |-- rover.py                        # Wk 4 | G6       | ~70
|   |   |-- rotorcraft.py                   # Wk 7 | G6       | ~80
|   |   |-- quadruped.py                    # Wk 7 | G6       | ~50
|   |   `-- humanoid.py                     # Wk 10 | G6      | ~50
|   |
|   |-- sensors/                            # Sensor attachment [G6]
|   |   |-- __init__.py                     # Wk 11 |         | ~3
|   |   |-- camera.py                       # Wk 11 | G5,G6   | ~80
|   |   |-- lidar.py                        # Wk 11 | G5,G6   | ~60
|   |   `-- imu.py                          # Wk 11 | G5,G6   | ~50
|   |
|   |-- ros2_bridge/                        # ROS2 publishing [G6]
|   |   |-- __init__.py                     # Wk 9 |          | ~3
|   |   |-- publisher.py                    # Wk 9 | G6       | ~90
|   |   `-- topic_config.py                 # Wk 9 | G6       | ~30
|   |
|   |-- annotation/                         # Synthetic data annotation [G6]
|   |   |-- __init__.py                     # Wk 12 |         | ~3
|   |   |-- replicator_setup.py             # Wk 12 | G6      | ~70
|   |   |-- label_converter.py              # Wk 12 | G1,G6   | ~60
|   |   `-- dataset_writer.py               # Wk 12 | G6      | ~70
|   |
|   |-- benchmark/                          # AI4Mars benchmark [G1][G6]
|   |   |-- __init__.py                     # Wk 13 |         | ~3
|   |   |-- data_generator.py               # Wk 13 | G1,G5   | ~110
|   |   |-- domain_randomizer.py            # Wk 13 | G5,G6   | ~90
|   |   `-- evaluator.py                    # Wk 16 | G1      | ~110
|   |
|   `-- utils/                              # Shared utilities [G6]
|       |-- __init__.py                     # Wk 1 |          | ~3
|       |-- seed.py                         # Wk 1 | G5       | ~25
|       `-- usd_helpers.py                  # Wk 4 | G6       | ~40
|
|-- tests/                                  # ALL tests [G7]
|   |-- __init__.py                         # Wk 1 |          | ~1
|   |-- unit/                               # No Isaac Sim required
|   |   |-- __init__.py                     # Wk 1 |          | ~1
|   |   |-- test_config_schema.py           # Wk 1 | G7       | ~80
|   |   |-- test_config_loader.py           # Wk 1 | G7       | ~50
|   |   |-- test_sun_position.py            # Wk 3 | G7       | ~40
|   |   |-- test_light_intensity.py         # Wk 3 | G7       | ~50
|   |   |-- test_diffuse_fraction.py        # Wk 3 | G7       | ~40
|   |   |-- test_sky_dome.py                # Wk 3 | G7       | ~35
|   |   |-- test_dem_loader.py              # Wk 2 | G7       | ~50
|   |   |-- test_rock_placer.py             # Wk 2 | G7       | ~80
|   |   |-- test_seed.py                    # Wk 1 | G7       | ~30
|   |   |-- test_label_converter.py         # Wk 12 | G7      | ~40
|   |   |-- test_robot_config.py            # Wk 4 | G7       | ~40
|   |   |-- test_domain_randomizer.py       # Wk 13 | G7      | ~50
|   |   `-- test_materials.py               # Wk 4 | G7       | ~35
|   |-- integration/                        # Isaac Sim required
|   |   |-- __init__.py                     # Wk 6 |          | ~1
|   |   |-- test_terrain_render.py          # Wk 6 | G7       | ~60
|   |   |-- test_robot_spawn.py             # Wk 4 | G7       | ~60
|   |   |-- test_sensor_output.py           # Wk 11 | G7      | ~80
|   |   |-- test_full_scene.py              # Wk 6 | G7       | ~60
|   |   |-- test_annotation.py              # Wk 12 | G7      | ~50
|   |   |-- test_atmosphere_fog.py          # Wk 6 | G7       | ~40
|   |   |-- test_ros2_bridge.py             # Wk 9 | G7       | ~50
|   |   `-- test_multi_robot.py             # Wk 10 | G7      | ~50
|   `-- visual_inspection/
|       `-- checklist.md                    # Wk 6 | G7       | ~50
|
|-- scripts/                                # Entry points
|   |-- hello_isaac.py                      # Wk 1 | G6       | ~40
|   |-- run_scene.py                        # Wk 6 | G6       | ~80
|   |-- generate_dataset.py                 # Wk 13 | G1      | ~60
|   |-- run_benchmark.py                    # Wk 16 | G1      | ~60
|   `-- convert_urdf.py                     # Wk 4 | G6       | ~40
|
|-- assets/                                 # Project-specific (NOT Isaac Sim built-in)
|   |-- terrain/
|   |   `-- dem/                            # Downloaded HiRISE GeoTIFFs
|   |-- sky/
|   |   `-- hdri/                           # Mars sky HDR images
|   |-- materials/
|   |   `-- mars_pbr/                       # Mars PBR material MDLs
|   `-- robots/
|       |-- rover/                          # Custom rover URDF + meshes
|       `-- rotorcraft/                     # Custom rotorcraft URDF + meshes
|
|-- docker/                                 # Docker config
|   |-- Dockerfile                          # Wk 15 |         | ~60
|   `-- docker-compose.yaml                 # Wk 15 |         | ~30
|
|-- work_log/                               # Work history [G8]
|   `-- LOG.md                              # Wk 1+ | G8      | append-only
|
`-- dev/                                    # Predecessor analysis docs (existing)
    |-- architecture_blueprint_en.md
    |-- mars_first_requirements_en.md
    |-- rlroverlab_analysis_en.md
    `-- omnilrs_analysis_plan.md
```

**Total estimated source lines:** ~3,400 (marslab/ package + tests + scripts)

### 3.3 Module Descriptions and Interfaces

Each module has a single responsibility. Dependencies flow strictly downward. [G6]

#### 3.3.1 `marslab/config/` -- Configuration Management

**Responsibility:** Load YAML config files, validate all parameters against physically
meaningful ranges, propagate seeds to all randomized modules. [G5]

**Dependencies:** None (standalone, pure Python + pydantic).

**Key interfaces:**

```python
# schema.py
class MarsEnvConfig(BaseModel):
    gravity: float = Field(ge=3.0, le=4.0, description="m/s^2")
    atmo_pressure: float = Field(ge=400, le=1200, description="Pa")
    dust_optical_depth: float = Field(ge=0.05, le=6.0, description="tau")
    solar_constant_mean: float = Field(ge=480, le=730, description="W/m^2")
    surface_albedo_range: tuple[float, float]
    seed: int

class TerrainConfig(BaseModel):
    source: str  # "hirise" or "procedural"
    rock_sfd_k: float = Field(ge=0.001, le=0.15, description="CFA fraction")
    semantic_classes: list[str] = ["soil", "bedrock", "sand", "big_rock"]
    seed: int

class MarsLabConfig(BaseModel):
    mars_env: MarsEnvConfig
    terrain: TerrainConfig
    robots: list[RobotConfig]
    rendering: RenderingConfig
    benchmark: BenchmarkConfig | None = None

# loader.py
def load_config(config_path: str) -> MarsLabConfig: ...
def propagate_seeds(config: MarsLabConfig) -> MarsLabConfig: ...
```

#### 3.3.2 `marslab/environment/` -- Mars Environmental State

**Responsibility:** Compute all Mars-specific environmental parameters from configuration
values. Pure computation -- zero Isaac Sim imports. Offline-testable. [G6]

**Dependencies:** `marslab/config/` only.

**Key interfaces:**

```python
# sun_position.py
@dataclass
class SunPosition:
    azimuth_deg: float
    elevation_deg: float
    zenith_angle_rad: float

def compute_sun_position(azimuth_deg: float, elevation_deg: float) -> SunPosition:
    """Phase 1: user-configured values from YAML.
    Phase 2: Allison & McEwen (2000) Ls-based computation."""

# light_intensity.py
def compute_direct_intensity(
    solar_constant: float, tau: float, zenith_angle_rad: float
) -> float:
    """Beer's Law: I = I_0 * exp(-tau / cos(theta_z))."""

# diffuse_fraction.py
def compute_diffuse_fraction(tau: float) -> float:
    """COMIMART model lookup. Vicente-Retortillo et al. (2015)."""

# sky_dome.py
@dataclass
class SkyDomeParams:
    base_color_rgb: tuple[float, float, float]
    brightness: float
    hdri_texture_path: str

def compute_sky_dome_params(tau: float, hdri_dir: str) -> SkyDomeParams: ...
```

#### 3.3.3 `marslab/terrain/` -- Terrain Generation and Annotation

**Responsibility:** Generate Mars terrain from HiRISE DEMs or procedural methods. Place
rocks via Golombek SFD. Assign AI4Mars semantic labels. Apply PBR materials. [G6]

**Dependencies:** `marslab/config/`. Isaac Sim required only for `mesh_builder.py`.

**Key interfaces:**

```python
# dem_loader.py  (offline, no Isaac Sim)
def load_hirise_dem(dem_path: str) -> tuple[np.ndarray, dict]: ...

# rock_placer.py  (offline, no Isaac Sim)
@dataclass
class RockPlacement:
    x: float; y: float; diameter: float; height: float

def sample_rocks_golombek(
    area_m2: float, k: float, diameter_range: tuple[float, float], seed: int
) -> list[RockPlacement]:
    """Golombek & Rapp (1997): F_k(D) = k * exp[-q(k) * D]."""

# mesh_builder.py  (Isaac Sim required)
def build_terrain_mesh(
    elevation: np.ndarray, resolution: float, stage, prim_path: str
) -> None: ...

# semantic_labeler.py
def assign_terrain_labels(
    mesh_prim, class_map: dict, rock_placements: list[RockPlacement]
) -> None: ...
```

#### 3.3.4 `marslab/rendering/` -- Mars Rendering Configuration

**Responsibility:** Configure Isaac Sim rendering for Mars-accurate imagery. [G4][G6]

**Dependencies:** `marslab/environment/` (for computed params), `marslab/config/`.

```python
def configure_sky_dome(stage, sky_params: SkyDomeParams) -> None: ...
def configure_sun_light(stage, sun_pos, intensity, diffuse_fraction) -> None: ...
def configure_atmosphere_fog(stage, tau: float) -> None: ...
def set_render_mode(mode: str) -> None:
    """path_tracing (data gen default) or ray_tracing (interactive default)."""
```

#### 3.3.5 `marslab/robots/` -- Robot Integration

**Responsibility:** Load and spawn robots. Built-in USD assets referenced by path, NOT
copied into repo. [G6]

**Dependencies:** `marslab/config/`. Does not import terrain or rendering.

```python
def spawn_rover(stage, config: RobotConfig, gravity: float) -> None: ...
def spawn_rotorcraft(stage, config, gravity, atmo_density) -> None: ...
def spawn_quadruped(stage, config: RobotConfig, gravity: float) -> None:
    """Go2 from built-in USD. Perception-ready only."""
def spawn_humanoid(stage, config: RobotConfig, gravity: float) -> None:
    """G1 from built-in USD. Perception-ready only. No dynamics claims."""
```

#### 3.3.6 `marslab/sensors/` -- Sensor Configuration

**Responsibility:** Attach and configure perception sensors. All params from YAML. [G5][G6]

```python
def attach_stereo_camera(robot_prim, config_path: str) -> tuple: ...
def attach_lidar(robot_prim, config_path: str): ...
def attach_imu(robot_prim, config_path: str):
    """Must read ~3.72 m/s^2 on z-axis when stationary."""
```

#### 3.3.7-3.3.9 Remaining Modules

- **`ros2_bridge/`**: Publish sensor data to ROS2 Humble topics. [G6]
- **`annotation/`**: Isaac Sim Replicator for semantic/instance/depth annotation. [G6]
- **`benchmark/`**: Seeded bulk data gen with domain randomization + AP/mIoU/F1. [G1][G6]

### 3.4 Dependency Rules

These rules are inviolable. [G6]

```
                    MarsLabConfig (pydantic)
                    /    |     |      \
                   /     |     |       \
            environment terrain rendering robots
               |          |       |        |
               +-----+----+--+---+--------+
                     |       |
                     v       v
              Isaac Sim   sensors --> ros2_bridge
              Native       |
              Loop     annotation --> benchmark
```

1. **No circular dependencies.** If A imports B, B must never import A.
2. **Config is the only shared dependency.** All modules read from `MarsLabConfig`.
3. **`environment/` has zero Isaac Sim imports.** Pure Python. Offline-testable.
4. **`terrain/dem_loader.py` and `terrain/rock_placer.py` have zero Isaac Sim imports.**
5. **`rendering/` depends on `environment/`** (one-way) for computed params.
6. **`robots/` depends on `config/`** only. Does not import terrain or rendering.
7. **No module modifies the Isaac Sim simulation loop.**
8. **Every function that uses randomness accepts a `seed` parameter.** [G5]

### 3.5 Config Schema

**Master config:** `configs/mars_env.yaml` [G5]

```yaml
mars_env:
  gravity: 3.72                    # m/s^2 (IAU standard)
  atmo_pressure: 610               # Pa (Viking/MSL mean)
  atmo_density: 0.020              # kg/m^3
  dust_optical_depth: 0.3          # tau (clear-ish default)
  solar_constant_mean: 589         # W/m^2 at 1.52 AU
  surface_albedo_range: [0.10, 0.40]
  surface_temp_mean: -60           # Celsius
  sol_duration_seconds: 88642      # 24h 37m 22s
  dust_opacity_range: [0.5, 2.0]   # tau range for DR
  seed: 42

terrain:
  source: "hirise"
  dem_path: "assets/terrain/dem/jezero_crater.tif"
  rock_sfd_k: 0.05                # CFA = 5%
  rock_diameter_range: [0.05, 3.0]
  semantic_classes: ["soil", "bedrock", "sand", "big_rock"]
  seed: 42

rendering:
  mode: "path_tracing"
  sky_dome_hdri_dir: "assets/sky/hdri/"
  resolution: [1280, 720]

robots:
  - type: "rover"
    urdf_path: "assets/robots/rover/perseverance.urdf"
    spawn_position: [0.0, 0.0, 0.5]
    sensor_config_paths:
      - "configs/sensors/stereo_rgb.yaml"
      - "configs/sensors/depth_camera.yaml"
      - "configs/sensors/lidar_3d.yaml"
      - "configs/sensors/imu.yaml"

benchmark:
  annotation_format: "ai4mars"
  dr_axes: ["dust_optical_depth", "surface_albedo", "rock_sfd_k",
            "sun_elevation", "camera_trajectory"]
  num_samples: 10000
  seed: 42
```

---

## 4. Priority Tiers [G10]

All tasks and features are classified:

- **MUST:** Required for ICRA 2027 MVP submission. Failure = no paper.
  Includes: config, terrain (HiRISE + procedural), atmosphere, rendering,
  rover, sensors, annotation, benchmark evaluation.
- **SHOULD:** Strengthens paper significantly. Cut only if >1 week behind.
  Includes: rotorcraft, quadruped, multi-robot, Docker, procedural terrain presets.
- **COULD:** Nice-to-have. First to defer under time pressure.
  Includes: humanoid (G1), arXiv preview, advanced DR axes.

**MVP definition:** Mars environment + single rover + terrain seg benchmark.
Paper is viable with rover-only. Multi-robot adds strength but is not required.

---

## 5. Implementation Plan (22 Weeks)

### 5.1 Phase Overview

| Phase | Weeks | Dates | Focus |
|-------|-------|-------|-------|
| Phase 1a | Wk 1-8 | Apr 7 -- May 31 | Config, terrain, atmosphere, rendering, rover |
| Phase 1b | Wk 9-16 | Jun 2 -- Jul 27 | ROS2, multi-robot, sensors, benchmark, annotation |
| Phase 1c | Wk 17-22 | Jul 28 -- Sep 15 | Sim2Real experiments, paper, submission |

### 5.2 Week-by-Week (Smallest Unit First) [G6]

---

#### WEEK 1 (Apr 7-13): Dev Environment + Config + CI

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Install Isaac Sim 5.x, verify GPU | MUST | -- | -- |
| 2 | Create repo structure, pyproject.toml, .gitignore | MUST | pyproject.toml | G6 |
| 3 | Set up GitHub Actions CI (unit tests + lint) | MUST | .github/workflows/ | G7 |
| 4 | Write seed.py (set_global_seed) | MUST | marslab/utils/seed.py | G5 |
| 5 | Write config schema.py (all pydantic models) | MUST | marslab/config/schema.py | G5 |
| 6 | Write config loader.py | MUST | marslab/config/loader.py | G5 |
| 7 | Write mars_env.yaml (full config) | MUST | configs/mars_env.yaml | G5 |
| 8 | Write hello_isaac.py (verify Isaac Sim runs) | MUST | scripts/hello_isaac.py | G6 |
| 9 | Write unit tests for config + seed | MUST | tests/unit/ | G7 |

**Deliverable:** Config validates, CI green, Isaac Sim runs hello_isaac.py.

---

#### WEEK 2 (Apr 14-20): HiRISE Terrain + Rock Placement (Offline)

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Download HiRISE DTM (Jezero) | MUST | assets/terrain/dem/ | -- |
| 2 | Write dem_loader.py (GDAL -> numpy) | MUST | marslab/terrain/dem_loader.py | G5,G6 |
| 3 | Write rock_placer.py (Golombek SFD) | MUST | marslab/terrain/rock_placer.py | G5,G6 |
| 4 | Write jezero_crater.yaml | MUST | configs/terrain/ | G5 |
| 5 | Write unit tests | MUST | tests/unit/ | G7 |

**HiRISE DTM source:**
- AWS: `s3://nasa-usgs-mars-hirise-dtms/` (free, no auth)
- Specific product: DTEEC_045994_1985_046060_1985 (Jezero Crater)
- USGS: `astrogeology.usgs.gov/search?pmi-target=mars`
- Index: `github.com/roncapat/NASA-Hirise-DTMs-DEMs-index`

**Deliverable:** Offline terrain + rock pipeline. All unit tests pass.

---

#### WEEK 3 (Apr 21-27): Mars Atmosphere + Lighting (Offline)

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Write sky_dome.py (tau -> color/brightness) | MUST | marslab/environment/sky_dome.py | G4,G6 |
| 2 | Write light_intensity.py (Beer's Law) | MUST | marslab/environment/light_intensity.py | G5,G6 |
| 3 | Write diffuse_fraction.py (COMIMART) | MUST | marslab/environment/diffuse_fraction.py | G5,G6 |
| 4 | Write sun_position.py (configurable) | MUST | marslab/environment/sun_position.py | G5,G6 |
| 5 | Write all atmosphere unit tests | MUST | tests/unit/ (4 files) | G7 |

**compute_sun_position Phase 1 vs Phase 2:**
- Phase 1: `compute_sun_position(azimuth_deg, elevation_deg) -> SunPosition`
  (user-configured values from YAML, no orbital mechanics)
- Phase 2: `compute_sun_position(ls, latitude, time_of_sol) -> SunPosition`
  (Allison & McEwen 2000 Ls-based computation)
- The SunPosition dataclass does not change between phases.

**Deliverable:** All Mars physics offline-testable. Zero Isaac Sim dependency.

---

#### WEEK 4 (Apr 28 -- May 4): Rover (Simplified Chassis) + PBR Materials

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Write material_applicator.py | MUST | marslab/terrain/material_applicator.py | G4,G6 |
| 2 | Write mesh_builder.py (elevation -> USD) | MUST | marslab/terrain/mesh_builder.py | G6 |
| 3 | Create simplified rover URDF (box chassis + 6 wheels) | MUST | assets/robots/rover/ | G6 |
| 4 | Write rover.py (spawn_rover) | MUST | marslab/robots/rover.py | G6 |
| 5 | Write convert_urdf.py script | MUST | scripts/convert_urdf.py | G6 |
| 6 | Write unit tests (robot config, materials) | MUST | tests/unit/ | G7 |
| 7 | Write test_robot_spawn.py (integration) | MUST | tests/integration/ | G7 |

**Rover URDF source:**
- Wk 4: Simplified box chassis + 6 cylindrical wheels. No rocker-bogie.
  Purpose: validate URDF->USD pipeline, gravity, terrain interaction.
- Wk 14: Full rocker-bogie from NASA 3D Resources CAD (nasa3d.arc.nasa.gov).

**Deliverable:** Rover on Mars terrain. Mars gravity confirmed. PBR materials v1.

---

#### WEEK 5 (May 5-11): Procedural Terrain + Seed Reproducibility

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Write procedural_generator.py (flat/crater/hills) | SHOULD | marslab/terrain/ | G5,G6 |
| 2 | Write 3 terrain preset YAMLs | SHOULD | configs/terrain/ | G5 |
| 3 | Implement merged collision mesh | SHOULD | marslab/terrain/mesh_builder.py | G6 |
| 4 | Verify seed reproducibility across all modules | MUST | tests/ | G5 |

**Deliverable:** 3+ terrain presets. Seed reproducibility verified end-to-end.

---

#### WEEK 6 (May 12-18): Rendering Integration + Visual Validation

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Write render_settings.py | MUST | marslab/rendering/ | G4 |
| 2 | Write sky_renderer.py (dome light + HDRI) | MUST | marslab/rendering/ | G4,G6 |
| 3 | Write sun_renderer.py (directional light) | MUST | marslab/rendering/ | G4,G6 |
| 4 | Write atmosphere_fog.py (tau -> visibility) | MUST | marslab/rendering/ | G4,G6 |
| 5 | Write run_scene.py (full scene orchestrator) | MUST | scripts/run_scene.py | G6 |
| 6 | Integration tests: full scene, atmosphere fog | MUST | tests/integration/ | G7 |
| 7 | Visual inspection: Mars vs lunar, tau comparison | MUST | -- | G7 |

**Rendering mode:** Default for data generation: RTX Interactive (path-tracing).
Default for interactive dev: RTX Real-Time (ray-tracing). Both always supported.

**Deliverable:** Integrated Mars scene v1. Screenshot comparison with real Mars.

---

#### WEEK 7 (May 19-25): Rotorcraft + Quadruped

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Create Ingenuity-class rotorcraft URDF | SHOULD | assets/robots/rotorcraft/ | G6 |
| 2 | Write rotorcraft.py (simplified kinematic) | SHOULD | marslab/robots/ | G6 |
| 3 | Write quadruped.py (Go2 from built-in USD) | SHOULD | marslab/robots/ | G6 |
| 4 | Write robot config YAMLs | SHOULD | configs/robots/ | G5 |

**Deliverable:** 3 robot types in Mars scene.

---

#### WEEK 8 (May 26 -- Jun 1): Checkpoint + Buffer

**>>> USER REVIEW GATE 1 <<<** [G10]

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Phase 1a checkpoint report | MUST | work_log/LOG.md | G8 |
| 2 | README.md v1 with installation guide | SHOULD | README.md | -- |
| 3 | Demo video of current capabilities | SHOULD | -- | -- |
| 4 | Buffer: catch up on any delayed MUST tasks | MUST | -- | -- |
| 5 | Schedule assessment + re-prioritization | MUST | -- | G10 |

**Deliverable:** Checkpoint report. User reviews. Buffer consumed if needed.

---

#### WEEK 9 (Jun 2-8): ROS2 Bridge

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Write topic_config.py | MUST | marslab/ros2_bridge/ | G6 |
| 2 | Write publisher.py | MUST | marslab/ros2_bridge/ | G6 |
| 3 | Write test_ros2_bridge.py | MUST | tests/integration/ | G7 |

**Deliverable:** ROS2 topics verified with `ros2 topic list/echo`.

---

#### WEEK 10 (Jun 9-15): Multi-Robot + Humanoid

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Write humanoid.py (G1 from built-in USD) | COULD | marslab/robots/ | G6 |
| 2 | Multi-robot spawn with independent namespaces | SHOULD | marslab/robots/ | G6 |
| 3 | FPS benchmark: 1/2/3/4 robots | SHOULD | -- | -- |
| 4 | Write test_multi_robot.py | SHOULD | tests/integration/ | G7 |

**Deliverable:** Multi-robot demo. G1 perception-ready (no dynamics claims).

---

#### WEEK 11 (Jun 16-22): Full Sensor Suite

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Write imu.py (Mars-calibrated noise) | MUST | marslab/sensors/imu.py | G5,G6 |
| 2 | Write camera.py (stereo RGB + depth) | MUST | marslab/sensors/camera.py | G5,G6 |
| 3 | Write lidar.py | MUST | marslab/sensors/lidar.py | G5,G6 |
| 4 | Write sensor config YAMLs | MUST | configs/sensors/ | G5 |
| 5 | Write test_sensor_output.py | MUST | tests/integration/ | G7 |
| 6 | **IMU gravity test: z-axis = 3.72 +/- 0.05** | MUST | tests/integration/ | G7 |

**Deliverable:** 4 sensor modalities on ROS2 topics. IMU gravity verified.

---

#### WEEK 12 (Jun 23-29): Annotation Pipeline

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Write semantic_labeler.py (AI4Mars 4-class) | MUST | marslab/terrain/ | G1 |
| 2 | Write replicator_setup.py | MUST | marslab/annotation/ | G6 |
| 3 | Write label_converter.py | MUST | marslab/annotation/ | G1 |
| 4 | Write dataset_writer.py | MUST | marslab/annotation/ | G6 |
| 5 | Unit + integration annotation tests | MUST | tests/ | G7 |

**Deliverable:** Annotation pipeline v1. RGB + semantic label pairs.

---

#### WEEK 13 (Jun 30 -- Jul 6): Benchmark Design

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Write domain_randomizer.py (5 DR axes) | MUST | marslab/benchmark/ | G5 |
| 2 | Write data_generator.py (seeded bulk gen) | MUST | marslab/benchmark/ | G1,G5 |
| 3 | Write benchmark config YAMLs | MUST | configs/benchmark/ | G5 |
| 4 | Write test_domain_randomizer.py | MUST | tests/unit/ | G7 |

**Deliverable:** Benchmark protocol. Synthetic dataset v1 (10K+ pairs).

---

#### WEEK 14 (Jul 7-13): Robot Polish + Dataset Finalization

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Upgrade rover URDF: full rocker-bogie | SHOULD | assets/robots/rover/ | -- |
| 2 | Robot model QA (collision, inertia, joints) | MUST | -- | -- |
| 3 | Complete synthetic dataset, train/val/test split | MUST | -- | G5 |

**Deliverable:** Final robot models. Complete synthetic dataset.

---

#### WEEK 15 (Jul 14-20): Docker + Buffer

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Write Dockerfile + docker-compose | SHOULD | docker/ | -- |
| 2 | Final data generation with full DR diversity | MUST | -- | G5 |
| 3 | Buffer: catch up on any SHOULD tasks | -- | -- | -- |

**Deliverable:** Docker image v1. Final dataset.

---

#### WEEK 16 (Jul 21-27): ML Pipeline + Evaluation

**>>> USER REVIEW GATE 2 <<<** [G10]

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Write evaluator.py (AP, mIoU, F1) | MUST | marslab/benchmark/ | G1 |
| 2 | Write run_benchmark.py script | MUST | scripts/ | G1 |
| 3 | User review of full system | MUST | -- | G10 |

**Deliverable:** Evaluation pipeline ready. User sign-off for Phase 1c.

---

#### WEEKS 17-22: Experiments + Paper

| Week | Focus | Priority |
|------|-------|----------|
| 17 | Train SegFormer, zero-shot + fine-tune on AI4Mars | MUST |
| 18 | Ablation, multi-robot demo, failure analysis | MUST/SHOULD |
| 19 | Paper draft v1 (ICRA 6+2 format) | MUST |
| 20 | Paper v2, 3-min video, code cleanup | MUST |
| 21 | Internal review, IEEE format, final polish | MUST |
| 22 | SUBMIT ICRA 2027 + GitHub v1.0.0 release | MUST |

---

## 6. Testing Strategy [G7]

### 6.1 Unit Tests (No Isaac Sim)

Run with: `pytest tests/unit/ -v` (no GPU, runs in CI)

| Module | Test File | Pass Criterion |
|--------|-----------|----------------|
| config | test_config_schema.py | Invalid params raise ValidationError |
| config | test_config_loader.py | Config loads correctly, seeds inherit |
| environment | test_light_intensity.py | Within 5% of Appelbaum & Flood (1990) |
| environment | test_diffuse_fraction.py | tau=0.3: [0.29, 0.38]; tau=1.0: [0.50, 0.53] |
| environment | test_sun_position.py | Physically reasonable zenith angles |
| environment | test_sky_dome.py | Butterscotch RGB range at low tau |
| terrain | test_dem_loader.py | Elevation range matches GeoTIFF header +/- 0.1m |
| terrain | test_rock_placer.py | CFA within 10% of published VL1/VL2/MPF data |
| terrain | test_materials.py | Albedo within Mars range [0.10, 0.40] |
| annotation | test_label_converter.py | Valid AI4Mars 4-class labels |
| benchmark | test_domain_randomizer.py | Seed reproducibility, parameter ranges |
| robots | test_robot_config.py | Valid URDF paths, spawn positions |
| utils | test_seed.py | Same seed = identical sequences |

### 6.2 Integration Tests (Isaac Sim Required)

Run with: `pytest tests/integration/ -v`

| Test File | Pass Criterion |
|-----------|----------------|
| test_terrain_render.py | Terrain loads and renders without error |
| test_robot_spawn.py | IMU z-axis = 3.72 +/- 0.05 m/s^2 |
| test_sensor_output.py | All sensors publish at configured Hz +/- 10% |
| test_full_scene.py | Mars-like render (not lunar, not Earth) |
| test_annotation.py | AI4Mars labels pixel-aligned with RGB |
| test_atmosphere_fog.py | Visibility changes with tau |
| test_ros2_bridge.py | Topics appear, messages received within 5s |
| test_multi_robot.py | 2+ robots with independent namespaces |

### 6.3 Visual Inspection Protocol [G7]

**File:** `tests/visual_inspection/checklist.md`

| Checkpoint | What to Inspect | Comparison Target |
|------------|-----------------|-------------------|
| V1 | Sky is butterscotch, not blue/black | MSL Mastcam sky images |
| V2 | Terrain has realistic Mars topography | HiRISE imagery of same site |
| V3 | Rock distribution looks natural | Mars surface photographs |
| V4 | tau=0.3 vs tau=2.0 visually different | Side-by-side screenshots |
| V5 | Mars rendering vs lunar params | Must be distinguishable |
| V6 | Rover on terrain, suspension visible | Visual check |
| V7 | 3 robots visible simultaneously | Visual check |
| V8 | Semantic labels overlay aligns | Label map on RGB |

### 6.4 CI Pipeline

- `.github/workflows/unit_tests.yaml`: runs on every push/PR. No GPU needed.
- `.github/workflows/lint.yaml`: black + ruff on every push/PR.
- Integration tests: run manually or in GPU-enabled CI (if available).

---

## 7. Work History Log [G8]

### 7.1 Location

**File:** `work_log/LOG.md` (append-only)

A third party joining mid-project reads this file to understand the full development
history.

### 7.2 Entry Template

```markdown
## [YYYY-MM-DD] Task Title

**Week:** Wk N (Mon DD -- Mon DD)
**Module:** marslab/module_name/
**Type:** [Feature | Fix | Test | Research | Documentation]

### What Was Done
- Concise bullet points with file references.

### Key Decisions
- Architectural/implementation decisions with rationale.

### Test Results
- Unit tests: N passed, M failed.
- Integration tests: result summary.
- Visual inspection: passed/failed with screenshot path.

### Blockers / Issues
- Problems encountered and resolutions.

### Next Steps
- What follows from this task in the plan.
```

### 7.3 Example Entry

```markdown
## [2026-04-14] Config Schema + YAML Loader

**Week:** Wk 1 (Apr 7 -- Apr 13)
**Module:** marslab/config/
**Type:** Feature

### What Was Done
- Created marslab/config/schema.py with 6 pydantic models.
- Created marslab/config/loader.py with load_config() and propagate_seeds().
- Created configs/mars_env.yaml with all Mars P0 parameters.
- Created marslab/utils/seed.py with set_global_seed().

### Key Decisions
- Used pydantic v2 (not dataclass) for automatic range checking via Field. [G5]

### Test Results
- Unit tests: 12 passed, 0 failed.

### Blockers / Issues
- None.

### Next Steps
- Week 2: HiRISE DEM loader + Golombek rock placer.
```

---

## 8. Phase Transition Criteria

### 8.1 Phase 1a -> Phase 1b (Wk 8 -> Wk 9) [G10]

ALL must be true:

- [ ] `marslab/config/` fully functional with validated YAML loading.
- [ ] `marslab/environment/` computes correct Beer's Law, diffuse fraction, sky dome.
- [ ] `marslab/terrain/` loads HiRISE DEM, procedural terrain, Golombek SFD rocks.
- [ ] `marslab/rendering/` produces Mars-like scene (butterscotch sky, correct shadows).
- [ ] Rover spawns in Mars scene with 3.72 m/s^2 gravity.
- [ ] All unit tests pass. Integration tests pass.
- [ ] Visual inspection V1-V5 signed off.

### 8.2 Phase 1b -> Phase 1c (Wk 16 -> Wk 17) [G10]

ALL must be true:

- [ ] ROS2 bridge publishes all sensor data on correct topics.
- [ ] Multi-robot spawn (3+ types) works simultaneously.
- [ ] All 4 sensor modalities verified.
- [ ] Annotation pipeline produces AI4Mars-compatible labels.
- [ ] Benchmark synthetic dataset generated (10K+ pairs) with seed-fixed DR.

### 8.3 Phase 1 -> Phase 2 (Post-ICRA) [G2]

ALL must be true:

- [ ] ICRA 2027 paper submitted.
- [ ] GitHub v1.0.0 released publicly.
- [ ] AI4Mars benchmark: mIoU > baseline.
- [ ] Gap analysis documents absent P1/P2 phenomena.
- [ ] Work log complete for all 22 weeks. [G8]

**What changes in Phase 2:**
- RL integration (Isaac Lab Gym API wrapper). [G2]
- Terramechanics plugin (data-driven). [G4]
- SLAM/Nav modules. [G1]
- Ls-parameterized temporal variation.

**What does NOT change:**
- Config schema (extends, does not break). [G5]
- Module boundaries. Isaac Sim as core engine. AI4Mars benchmark format.

---

## 9. Anti-Patterns [G3][G5][G6]

### 9.1 Hardcoding Mars Parameters [G5]
**Mistake:** Writing `gravity = 3.72` in Python source.
**Rule:** Every constant goes in `configs/mars_env.yaml`. Load via `MarsLabConfig`.

### 9.2 Copying Code from References [G3]
**Mistake:** Copy-pasting terrain code from OmniLRS or RLRoverLab.
**Rule:** Read the algorithm. Understand it. Rewrite using `omni.isaac.lab` APIs.

### 9.3 Using Deprecated APIs
**Mistake:** Importing from `omni.isaac.orbit`.
**Rule:** Always use `omni.isaac.lab`. Never `omni.isaac.orbit`.

### 9.4 Building Abstractions Before Prototypes [G6]
**Mistake:** Designing a plugin system on Day 1.
**Rule:** Write flat procedural code. Extract abstractions only when patterns emerge.

### 9.5 Designing Phase 2 During Phase 1
**Mistake:** Building terramechanics interfaces "for future extensibility."
**Rule:** Phase 1 delivers working MVP. Phase 2 interfaces emerge from Phase 1 learnings.

### 9.6 Copying Isaac Sim Built-in Assets
**Mistake:** Copying G1/Go2 USD files into `assets/`.
**Rule:** Reference by Isaac Sim asset path. Never copy.

### 9.7 Treating RL as Phase 1 Work [G1][G2]
**Mistake:** Adding reward functions or training loops.
**Rule:** Phase 1 is perception only. RL is strictly future work.

---

## 10. References

### Planetary Science

1. NASA Mars Fact Sheet. https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html
2. Golombek & Rapp (1997). Rock SFD on Mars. JGR 102(E2).
3. Golombek et al. (2003). Rock size-frequency distributions. JGR 108(E12).
4. Golombek et al. (2021). InSight landing site assessment. Earth & Space Science.
5. Smith (2004). TES atmospheric observations. Icarus 167.
6. Vicente-Retortillo et al. (2015). COMIMART model. JSWSC.
7. Appelbaum & Flood (1990). Solar radiation on Mars. NASA TM-102299.
8. Swan et al. (2021). AI4Mars: Terrain-aware driving on Mars. CVPRW.
9. Allison & McEwen (2000). Areocentric solar coordinates. Planet. Space Sci. 48(2-3).

### Simulation Platforms (Studied, NOT Code-Reused) [G3]

10. Richard et al. (2023). OmniLRS. arXiv:2309.08997.
11. Mortensen & Boegh (2024). RLROVERLAB. iSpaRo 2024.
12. SRB (2025). arXiv:2509.23328.
13. Sim2Dust (2025). arXiv:2508.11503.
14. unitree_sim_isaaclab (2025). github.com/unitreerobotics/unitree_sim_isaaclab.

### Engine Documentation

15. Isaac Lab API Reference. isaac-sim.github.io/IsaacLab/.
16. Isaac Sim Robot Assets. docs.isaacsim.omniverse.nvidia.com/
17. NVIDIA Replicator Tutorials. docs.isaacsim.omniverse.nvidia.com/

---

*This document was produced through the 13-agent adversarial debate system with 19/19
critical fixes applied. It serves as the single source of truth for MarsLab development
targeting ICRA 2027 Seoul.*
