# CLAUDE.md -- MarsLab Development Guidelines

## Project Overview

MarsLab is an open-source, photorealistic Mars simulation platform for heterogeneous
planetary robotics research, built on NVIDIA Isaac Sim. Target: ICRA 2027 Seoul
submission (deadline ~Sep 15, 2026).

**Repository**: `MarsLab/` (Apache 2.0 license)
**Engine**: Isaac Sim 5.x + Isaac Lab
**Core Stack**: Python 3.10+, ROS2 Jazzy, Isaac Sim Extensions, USD/URDF

## User Guidelines (G1-G13)

These 13 guidelines govern all development decisions. Every feature, module, and task
must trace back to one or more of these guidelines.

1. **G1: Perceptual Robotics Focus.** MarsLab = photorealistic Mars robot simulator for
   OD, Seg, SLAM, Nav, Exploration. Phase 1 = OD + Seg + sensor data gen. SLAM/Nav =
   Phase 2.
2. **G2: RL is Future Work.** No RL environments, reward functions, or Gym API wrappers
   in Phase 1.
3. **G3: No Code Reuse.** Algorithm/flowchart inspiration only from OmniLRS/RLRoverLab.
   No code copying. No naming from reference codebases in MarsLab source.
4. **G4: Photorealism = Top Priority.** Physics fidelity is secondary (Phase 2).
5. **G5: All Configs in YAML.** Zero hardcoded constants in Python source.
6. **G6: Extreme Modularity.** Smallest units first, expand incrementally.
7. **G7: Unit Tests for Everything.** Visual inspection when automated testing impossible.
8. **G8: Work History Log.** Every task summarized, traceable by new team members.
9. **G9: PLAN.md = Architecture + Implementation Plan.**
10. **G10: User Review Gate.** User reviews and may request revisions.
11. **G11: Ultrathink Throughout.** Deep reasoning at every design decision.
12. **G12: 13-Agent Adversarial Debate.** Plan produced through multi-agent review.
13. **G13: Four Output Files.** PLAN.md (EN), PLAN_kor.md (KR), CLAUDE.md (EN),
    CLAUDE_kor.md (KR).

## Architectural Principles

Three principles govern all structural decisions:

**P1: Flat P0 Architecture.**
No premature abstraction. Start with flat procedural code. Extract classes/patterns
only when empirical complexity demands it. No plugin systems, no god objects, no
registration mechanisms in Phase 1.

**P2: Unidirectional Data Flow.**
Config -> pure computation modules -> Isaac Sim scene configuration -> native sim loop.
No module modifies the simulation loop. No circular dependencies. Config is the only
shared dependency across modules.

**P3: Offline-First Testing.**
Every pure-computation module (environment physics, config validation, rock SFD,
label conversion) must be testable without Isaac Sim or GPU. Isaac Sim-dependent
code is isolated into separate functions/files clearly marked as integration-only.

## Coding Standards

### General
- Python 3.10+. Type hints on all public functions.
- Docstrings: Google style. Every public class/function must have one.
- Line length: 100 chars max.
- Formatter: `black`. Linter: `ruff`.
- **Every code change must pass all three checks before completion:**
  ```bash
  black --check marslab/ scripts/ tests/
  ruff check marslab/ scripts/ tests/
  python3 -m pytest tests/unit/ -v
  ```
  Run `black marslab/ scripts/ tests/` to auto-format, then `ruff check --fix` for auto-fixable lint.
- No global state. No singletons except for Isaac Sim app instance.

### Naming Conventions
- Files/modules: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- ROS2 topics: `/{robot_name}/{sensor_type}` (e.g., `/rover_0/rgb/image_raw`)
- Config keys: `snake_case` in YAML

### Isaac Sim Specific

#### API Usage Rules
- **Prefer** `omni.isaac.lab` APIs for all simulation setup.
- **Permitted:** `pxr.*` (USD Python API) and `omni.isaac.core` when Isaac Lab
  provides no wrapper for a needed capability. Document the reason in a comment.
- **NEVER** use `omni.isaac.orbit` (deprecated, renamed to `omni.isaac.lab`).
- **"omni" in import paths** is NVIDIA's namespace. It is NOT a reference codebase
  name and is exempt from guideline G3 (no code reuse naming).
- **No code or naming** derived from OmniLRS, RLRoverLab, or any reference codebase
  in MarsLab source files. Algorithm/pattern inspiration only.

#### Rendering & Assets
- Terrain: use `TerrainImporter` for DEM-based, `TerrainGenerator` for procedural.
- Robot import: URDF -> USD via `omni.isaac.lab.sim.converters.UrdfConverter`.
- Built-in USD assets (G1, Go2, Valkyrie): load from Isaac Sim asset path, do NOT
  copy into repo.
- Sensors: use Isaac Sim built-in sensor classes. Add noise models as wrappers.
- Rendering: always support both RTX Real-Time (ray-tracing) and RTX Interactive
  (path-tracing). Default = path-tracing for data generation, ray-tracing for
  interactive use.

### Configuration
- ALL physical parameters go in `configs/mars_env.yaml`. Never hardcode.
- Robot spawn positions, sensor params, benchmark configs: YAML files in `configs/`.
- Use `dataclass` or `pydantic` for config schema validation.
- Seed-based reproducibility: every randomized process must accept a `seed` parameter.

### Mars Physics Constants (Reference -- put in config, not code)
```yaml
# configs/mars_env.yaml
mars:
  gravity: 3.72          # m/s^2
  atmo_pressure: 610     # Pa
  atmo_density: 0.020    # kg/m^3
  atmo_composition: "95.3% CO2, 2.7% N2, 1.6% Ar"
  surface_temp_mean: -60  # Celsius
  sol_duration: 88642     # seconds (24h 37m 22s)
  dust_opacity_range: [0.5, 2.0]  # tau
```

## Module Architecture

### Module Dependency Rules
1. No circular imports. If A imports B, B never imports A.
2. `config/` is the only shared dependency. All modules read from `MarsLabConfig`.
3. `environment/` has zero Isaac Sim imports. Pure Python. Offline-testable.
4. `terrain/dem_loader.py` and `terrain/rock_placer.py` have zero Isaac Sim imports.
5. `rendering/` depends on `environment/` (one-way) for computed params.
6. `robots/` depends only on `config/`. Does not import terrain or rendering.
7. No module modifies the Isaac Sim simulation loop.
8. Every randomized function accepts a `seed` parameter.

### Module Summary
| Module | Responsibility | Isaac Sim Required? |
|--------|---------------|-------------------|
| `config/` | YAML load, pydantic validation, seed propagation | No |
| `environment/` | Mars physics: sun position, Beer's law, COMIMART, sky params | No |
| `terrain/` | DEM loading, mesh building, rock placement, materials, labels | Partial |
| `rendering/` | Sky dome, sun light, atmosphere fog, render mode | Yes |
| `robots/` | URDF->USD spawn for rover/rotorcraft/quadruped/humanoid | Yes |
| `sensors/` | Camera, LiDAR, IMU attachment and config | Yes |
| `ros2_bridge/` | Sensor -> ROS2 topic publishing | Yes |
| `annotation/` | Replicator setup, label conversion, dataset writing | Yes |
| `benchmark/` | Domain randomization, bulk data gen, AP/mIoU/F1 eval | Partial |

## Priority Tiers

All tasks and features are classified:

- **MUST:** Required for ICRA 2027 MVP submission. Failure = no paper.
  Includes: config, terrain (HiRISE + procedural), atmosphere, rendering,
  rover, sensors, annotation, benchmark evaluation.
- **SHOULD:** Strengthens paper significantly. Cut only if >1 week behind.
  Includes: rotorcraft, quadruped, multi-robot, Docker, procedural terrain presets.
- **COULD:** Nice-to-have. First to defer under time pressure.
  Includes: humanoid (G1), arXiv preview, advanced DR axes.

MVP definition: Mars environment + single rover + terrain seg benchmark.
Paper is viable with rover-only. Multi-robot adds strength.

## Error Handling

- Config validation errors: raise `pydantic.ValidationError` with descriptive message.
- Missing files (DEM, URDF, HDRI): raise `FileNotFoundError` with full path.
- Isaac Sim API failures: catch, log with `logging.error()`, re-raise with context.
- Out-of-range physics values at runtime: raise `ValueError` with parameter name,
  value, and valid range.
- Never silently swallow exceptions. Never use bare `except:`.
- All error messages must include enough context to diagnose without a debugger.

## Testing Requirements

### Unit Tests (No Isaac Sim)
Run with: `pytest tests/unit/ -v`
- Config validation: valid/invalid/out-of-range parameters
- Beer's Law: validated against Appelbaum & Flood (1990) NASA TM-102299 within 5%
- COMIMART diffuse fraction: validated against Vicente-Retortillo et al. (2015)
- Golombek SFD: CFA curve within 10% of published VL1/VL2/MPF/InSight data
- Seed determinism: same seed = identical output for all randomized functions
- Label conversion: AI4Mars 4-class format compliance
- Sky dome params: butterscotch RGB range at low tau
- Material albedo: within Mars range [0.10, 0.40]
- Robot config: valid URDF paths, spawn positions
- Domain randomizer: seed reproducibility, parameter ranges

### Integration Tests (Isaac Sim Required)
Run with: `pytest tests/integration/ -v`
- Terrain renders without error
- Robot spawn: IMU z-axis = 3.72 +/- 0.05 m/s^2 (THE critical test)
- Sensors publish on ROS2 topics at configured Hz +/- 10%
- Full scene: Mars-like appearance (not lunar, not Earth)
- Annotation: AI4Mars labels pixel-aligned with RGB
- Atmosphere fog: visibility changes with tau
- ROS2 bridge: topics appear, messages received within 5s
- Multi-robot: 2+ robots with independent namespaces

### Visual Inspection
Documented in `tests/visual_inspection/checklist.md`. Results logged in work_log.

### CI Pipeline
- `.github/workflows/unit_tests.yaml`: runs on every push/PR. No GPU needed.
- `.github/workflows/lint.yaml`: black + ruff on every push/PR.
- Integration tests: run manually or in GPU-enabled CI (if available).

## Phase 1 Scope (ICRA 2027)

**In scope:**
- Object detection, semantic segmentation on synthetic Mars imagery
- Sensor data generation (RGB, depth, LiDAR, IMU)
- Sim2real benchmark: synthetic training -> real Mars image evaluation
- Multi-robot scene composition (perception-ready)

**Explicitly out of scope for Phase 1:**
- SLAM / autonomous navigation (deferred to Phase 2)
- Reinforcement learning environments, reward functions, Gym API wrappers
- Terramechanics (BCM/SCM/DEM) -- rigid body + Mars friction only
- Legged robot dynamics validation in Mars gravity
- Mars aerodynamics for rotorcraft (simplified kinematic model only)
- Ls-based seasonal variation (fixed configurable sun position)

## Work History Log

**Location:** `work_log/LOG.md` (append-only)

Every completed development task gets a structured entry with:
- Date, week number, module name
- What was done (bullet points with file references)
- Key decisions with rationale
- Test results (pass/fail counts)
- Blockers and resolutions
- Next steps

A third party joining mid-project reads this file to understand the full
development history. See PLAN.md Section 7 for the entry template.

## What NOT To Do

1. **Do NOT claim terramechanics fidelity in Phase 1.** Physics = rigid body +
   Mars-calibrated friction. No BCM/SCM/DEM. Terramechanics is Phase 2 plugin.
2. **Do NOT validate legged robot dynamics in Mars gravity.** G1/Go2 are
   perception-ready only. No locomotion policy transfer claims.
3. **Do NOT hardcode Mars parameters.** Everything in config YAML.
4. **Do NOT copy Isaac Sim built-in USD assets into the repo.** Reference by
   asset path.
5. **Do NOT implement Mars aerodynamics for rotorcraft in Phase 1.** Use
   simplified kinematic model. Full CFD aero = separate project.
6. **Do NOT copy code from OmniLRS or RLRoverLab.** Study their ROS2 binding
   patterns and terrain pipeline algorithms for inspiration only. Do not copy
   code or maintain API compatibility.
7. **Do NOT use deprecated Isaac Sim APIs** (`omni.isaac.orbit` -> use
   `omni.isaac.lab`).

## Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Isaac Sim | 5.x | Core simulation engine |
| Isaac Lab | latest | Robot learning framework |
| ROS2 | Humble | Robot communication |
| Python | 3.10+ | Primary language |
| GDAL | latest | GeoTIFF/DEM processing |
| trimesh | latest | Mesh processing |
| PyTorch | 2.x | ML training (benchmark) |
| MMSegmentation or HuggingFace | latest | SegFormer/DeepLab training |

## Benchmark Design Rules

- Output format: AI4Mars-compatible 4-class labels (soil, bedrock, sand, big_rock).
- Every benchmark config must be seed-fixed for reproducibility.
- Report both zero-shot (synthetic-only) and fine-tuned results.
- Evaluation metrics: AP, mIoU, F1 (per-class and mean).
- Domain randomization axes: lighting (Sol phase), dust opacity (tau), terrain type,
  rock density, camera trajectory.

## Reference Codebases (Study Before Implementing)

| Codebase | What to Learn | Link |
|----------|---------------|------|
| OmniLRS | Terrain gen pipeline, ROS2 bindings, rock placement | github.com/OmniLRS/OmniLRS |
| SRB | Modular task registry, sim-to-real automation | arXiv:2509.23328 |
| RLROVERLAB | Isaac Lab API patterns, three-mesh pattern | github.com/abmoRobotics/isaac_rover_orbit |
| unitree_sim_isaaclab | G1/H1 Isaac Lab integration pattern | github.com/unitreerobotics/unitree_sim_isaaclab |
| Sim2Dust | DreamerV3 world model RL, zero-shot transfer | arXiv:2508.11503 |

## Communication Protocol

When asked to implement a feature:
1. Check which Phase/Week it belongs to. Respect dependency order.
2. Check if a reference codebase already solved it. Study before reimplementing.
3. Write config-driven, seed-reproducible code.
4. Include unit test.
5. If unsure about Isaac Sim API, say so rather than guessing deprecated APIs.
