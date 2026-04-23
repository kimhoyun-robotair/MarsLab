# PLAN.md -- MarsLab Architecture & Implementation Plan

**Version:** 4.0 (iSpaRo 2026 — Scenario-Based Robotics Platform)
**Date:** 2026-04-14
**Target:** Standardized Mars robotics testing platform with diverse mission scenarios
**Timeline:** 8 weeks (Apr 14 -- Jun 16, 2026) for v1.0 iSpaRo submission
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
|   |   `-- publisher.py                    # Wk 9 | G6       | ~90
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

> **Note (2026-04-14):** Restructured for iSpaRo 2026 submission (Jun 16 deadline).
> Version roadmap: v1.0 (scenarios + robotics) → v2.0 (photorealism) → v3.0 (terramechanics).

All tasks classified by version:

- **v1.0 MUST (iSpaRo 2026):** 7 mission scenarios, rover URDF fix, dynamic atmosphere,
  SLAM integration, Nav2 integration, experimental evaluation, 8-page paper.
- **v1.0 SHOULD:** All 7 scenarios complete. Cut to 3-5 if time-pressured.
- **v2.0 (post-iSpaRo):** High photorealism (OmniLRS-level PBR, 4K HDRI, anti-tiling,
  pebble scatter, photogrammetry rocks).
- **v3.0 (future):** Terramechanics (Bekker/Janosi), RL environments, multi-robot coordination.

**MVP definition:** 3+ Mars mission scenarios + working rover + SLAM + Nav2 + paper.
Minimum submittable: scenarios 1-3 + dynamic atmosphere + SLAM/Nav2 experiments.

---

## 5. Implementation Plan

### 5.1 Version Roadmap

> **Note (2026-04-14):** Plan restructured from photorealism-first to
> scenario-based robotics platform. Identity shift: renderer → robotics testbed.
> Wk 1-9 completed under original plan. v1.0 schedule below targets iSpaRo 2026.

| Version | Target | Focus | Deadline |
|---------|--------|-------|----------|
| Foundation (Wk 1-9) | -- | Config, terrain, atmosphere, rendering, robots, sensors, ROS2 | **COMPLETED** |
| **v1.0** | **iSpaRo 2026** | 7 mission scenarios + rover SLAM/Nav2 + paper (8 pages) | **Jun 16, 2026** |
| v2.0 | Post-iSpaRo | High photorealism (OmniLRS-level PBR, HDRI, anti-tiling) | TBD |
| v3.0 | Future | Terramechanics, RL environments, multi-robot coordination | TBD |

### 5.2 Foundation (Wk 1-9, COMPLETED)

Weeks 1-9 built the core infrastructure. See git history and work_log/LOG.md for details.
Completed: config, HiRISE DEM, procedural terrain, atmosphere, rendering, 3 robots,
sensors (RGB/depth/IMU/LiDAR), ROS2 bridge, 140 unit tests.

### 5.3 v1.0 Schedule (8 Weeks, Apr 14 -- Jun 16) [G6]

---

#### WEEK 1 (Apr 14-20): Rover URDF Fix + Mobility

**v1.0 MUST:** Rover URDF fix, 7 mission scenarios, dynamic atmosphere,
SLAM + Nav2 integration, experimental evaluation, 8-page iSpaRo paper.

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Fix rover URDF (adopt open-source or redesign for stable physics) | MUST | assets/robots/rover/ | G4 |
| 2 | Set fix_base=False, verify rover settles on terrain | MUST | marslab/robots/rover.py | G4 |
| 3 | Re-enable robot spawn in run_scene.py (uncomment) | MUST | scripts/run_scene.py | -- |
| 4 | Re-enable robots in mars_env.yaml (uncomment) | MUST | configs/mars_env.yaml | G5 |

**Deliverable:** Rover drives on Mars terrain with fix_base=False.

---

#### WEEK 2 (Apr 21-27): Scenarios 1-3 (HiRISE Crop) + ROS2 Control

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Scenario 1 config: Basic Mars (Jezero plain crop) | MUST | configs/scenarios/basic_mars.yaml | G5 |
| 2 | Scenario 2 config: Rock-Dense Zone (rock_sfd_k=0.10) | MUST | configs/scenarios/rock_dense.yaml | G5 |
| 3 | Scenario 3 config: Crater + Slopes (Jezero rim/delta crop) | MUST | configs/scenarios/crater_slopes.yaml | G5 |
| 4 | cmd_vel subscriber: /cmd_vel -> wheel control | MUST | marslab/ros2_bridge/cmd_vel_subscriber.py (new) | G6 |
| 5 | TF broadcaster: odom -> base_link -> sensor_frames | MUST | marslab/ros2_bridge/tf_broadcaster.py (new) | G6 |
| 6 | Odometry publisher: wheel encoder -> /odom | MUST | marslab/ros2_bridge/odometry.py (new) | G6 |
| 7 | Re-enable sensor ROS2 publishers | MUST | marslab/ros2_bridge/publisher.py | G6 |

**Deliverable:** 3 scenario configs + rover teleoperable via /cmd_vel.

---

#### WEEK 3 (Apr 28 -- May 4): Dynamic Atmosphere + SLAM Integration

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Dynamic sun position: time-of-sol azimuth sweep | MUST | marslab/environment/sun_position.py | G5 |
| 2 | Runtime tau variation: scene-level tau change | MUST | marslab/environment/sky_dome.py | G5 |
| 3 | Fog auto-update on tau change | MUST | marslab/rendering/atmosphere_fog.py | G5 |
| 4 | SLAM integration: slam_toolbox (2D LiDAR) | MUST | ROS2 launch files, configs/ | G1 |
| 5 | SLAM map generation on scenarios 1-3 | MUST | -- | G7 |

**Deliverable:** Dynamic atmosphere + SLAM maps from 3 scenarios.

---

#### WEEK 4 (May 5-11): Nav2 Integration + Scenario 4 (Canyon)

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Nav2 stack: costmap + planner + controller | MUST | configs/nav2/, launch files | G1 |
| 2 | Nav2 waypoint following test | MUST | test scripts | G7 |
| 3 | structure_loader.py: load OBJ/USD assets into scene | MUST | marslab/terrain/structure_loader.py (new) | G6 |
| 4 | Scenario 4: Canyon (science-based Blender mesh + placement) | SHOULD | configs/scenarios/canyon.yaml, assets/ | G4 |

**Deliverable:** Nav2 autonomous navigation + canyon scene.

---

#### WEEK 5 (May 12-18): Scenarios 5-7 (Cave, Spacecraft, Base)

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Scenario 5: Mars Cave (Blender mesh + PointLight lighting) | SHOULD | configs/scenarios/cave.yaml, assets/ | G4 |
| 2 | Scenario 6: Spacecraft Landing Site (3D model placement) | SHOULD | configs/scenarios/spacecraft.yaml, assets/ | G4 |
| 3 | Scenario 7: Mars Base (habitat/solar panel models) | SHOULD | configs/scenarios/mars_base.yaml, assets/ | G4 |
| 4 | Cave lighting mode: DomeLight off + PointLight/SpotLight | SHOULD | marslab/rendering/sky_renderer.py | G5 |

**Deliverable:** All 7 scenario scenes complete.

---

#### WEEK 6 (May 19-25): Experiments + Data Collection

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | SLAM benchmark: ATE/RPE across all scenarios | MUST | evaluation scripts | G7 |
| 2 | Nav2 benchmark: success rate, path length across scenarios | MUST | evaluation scripts | G7 |
| 3 | Tau impact experiment: SLAM accuracy at tau 0.3/1.0/2.0/4.0 | MUST | -- | G7 |
| 4 | Generate paper figures: scenario screenshots, plots | MUST | scripts/ | G4 |

**Deliverable:** All experimental tables and figures for paper.

---

#### WEEK 7 (May 26 -- Jun 1): Paper Draft v1

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Paper draft: all 8 sections (intro, related work, arch, scenarios, experiments, conclusion) | MUST | paper/ | G8 |
| 2 | Demo video (optional but strengthens submission) | SHOULD | -- | -- |

**Deliverable:** Complete 8-page draft.

---

#### WEEK 8 (Jun 2-16): Paper Revision + Submission

| # | Task | Priority | Files | Guideline |
|---|------|----------|-------|-----------|
| 1 | Paper revision based on self-review | MUST | paper/ | G10 |
| 2 | Final figures, IEEE format compliance | MUST | paper/ | -- |
| 3 | Submit to iSpaRo 2026 | MUST | -- | -- |
| 4 | GitHub v1.0.0 release | SHOULD | -- | -- |

**>>> v1.0 SUBMISSION <<<** [G10]

---

### 5.4 v2.0 / v3.0 (Post-iSpaRo, Future Work)

**v2.0: High Photorealism**
- OmniLRS-level PBR textures (4K+, anti-tiling, pebble scatter)
- Photogrammetry rock meshes (5K-40K faces)
- 4K HDRI sky with smooth tau interpolation
- Production render settings (SPP 32+, bounces 6+)

**v3.0: High Physical Fidelity**
- Terramechanics plugin (Bekker/Janosi)
- RL environments (Isaac Lab Gym API)
- Multi-robot coordination
- Ls-parameterized seasonal variation

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

## 8. Version Release Criteria

> **Note (2026-04-14):** Restructured for version-based releases.

### 8.0 Foundation (Wk 1-9) [G10]

**COMPLETED (2026-04-11).** Config, terrain, atmosphere, rendering, robots, sensors, ROS2.

### 8.1 v1.0 Release Criteria (iSpaRo 2026, Jun 16) [G10]

ALL must be true:

- [ ] Rover drives on Mars terrain (fix_base=False, stable physics).
- [ ] /cmd_vel controls rover movement. TF tree + odometry publishing.
- [ ] 3+ mission scenarios operational (HiRISE crop-based, config-driven).
- [ ] Dynamic atmosphere: tau and time-of-day affect scene.
- [ ] SLAM generates map in at least 2 scenarios (ATE/RPE measured).
- [ ] Nav2 performs waypoint navigation in at least 1 scenario.
- [ ] Experimental tables complete (SLAM accuracy vs. scenario, SLAM vs. tau).
- [ ] 8-page iSpaRo paper submitted.

**SHOULD (strengthens paper but not blocking):**
- [ ] All 7 scenarios complete (canyon, cave, spacecraft, base).
- [ ] Nav2 benchmarked across multiple scenarios.
- [ ] GitHub v1.0.0 public release.

### 8.2 v2.0 Release Criteria (Post-iSpaRo) [G4]

- [ ] OmniLRS-level photorealism (high-poly rocks, 4K HDRI, anti-tiling).
- [ ] Production render settings (SPP 32+, bounces 6+).
- [ ] Perception benchmark: sim2real transfer on AI4Mars.

### 8.3 v3.0 Release Criteria (Future) [G4]

- [ ] Terramechanics plugin (Bekker/Janosi).
- [ ] RL environments (Isaac Lab Gym API).
- [ ] Multi-robot coordination.

**What does NOT change across versions:**
- Config schema (extends, does not break). [G5]
- Module boundaries. Isaac Sim as core engine.
- Coding standards and testing requirements.

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
