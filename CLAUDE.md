# CLAUDE.md -- MarsLab Development Guidelines

## Project Overview

MarsLab is an open-source Mars simulation platform providing standardized mission
scenarios for planetary/field robotics research, built on NVIDIA Isaac Sim.
Target: iSpaRo 2026 Regular Paper (8 pages), deadline Jun 16, 2026.

**Repository**: `MarsLab/` (Apache 2.0 license)
**Engine**: Isaac Sim 5.x + Isaac Lab
**Core Stack**: Python 3.10+, ROS2 Jazzy, Isaac Sim Extensions, USD/URDF

## User Guidelines (G1-G13)

These 13 guidelines govern all development decisions. Every feature, module, and task
must trace back to one or more of these guidelines.

1. **G1: Field Robotics Platform.** MarsLab = standardized Mars robotics testing platform
   for SLAM, Nav, Exploration. v1.0 = 7 mission scenarios + rover + SLAM/Nav2 (iSpaRo 2026).
   v2.0 = high photorealism. v3.0 = terramechanics + RL.
2. **G2: RL is Future Work (v3.0).** No RL environments, reward functions, or Gym API wrappers
   until v3.0.
3. **G3: No Code Reuse.** Algorithm/flowchart inspiration only from OmniLRS/RLRoverLab.
   No code copying. No naming from reference codebases in MarsLab source.
4. **G4: Robotics First, Photorealism Later.** v1.0 = good-enough rendering + strong
   robotics (scenarios, SLAM, Nav2). v2.0 = OmniLRS-level photorealism. v3.0 = terramechanics.
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
**Scope:** P1 applies to MarsLab source code (`marslab/`, `scripts/`, `tests/`).
The development harness (`.claude/agents/`, `.claude/skills/`) is infrastructure,
not product code, and is exempt from P1.

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
- ROS2 topics: `/{robot_name}/{sensor_type}` (e.g., `/rover/rgb/image_raw`)
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

All tasks classified by version (iSpaRo 2026 deadline: Jun 16):

- **v1.0 MUST:** Rover URDF fix, 7 mission scenarios, dynamic atmosphere,
  SLAM + Nav2 integration, experimental evaluation, 8-page iSpaRo paper.
- **v1.0 SHOULD:** All 7 scenarios complete. GitHub v1.0.0 release.
- **v2.0 (post-iSpaRo):** OmniLRS-level photorealism (high-poly rocks, 4K HDRI,
  anti-tiling, pebble scatter, production SPP).
- **v3.0 (future):** Terramechanics, RL environments, multi-robot coordination.

MVP definition: 3+ scenarios + rover + SLAM + Nav2 + paper.
Minimum submittable: scenarios 1-3 + dynamic atmosphere + SLAM/Nav2 experiments.

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

## Version Scope

### v1.0 (iSpaRo 2026, Current)

**In scope:**
- 7 mission scenarios: Basic Mars, Rock-Dense, Crater+Slopes, Canyon, Cave,
  Spacecraft Landing, Mars Base
- Rover with dynamic physics (fix_base=False, stable URDF)
- ROS2 full stack: cmd_vel, TF, odometry, sensors
- SLAM integration (slam_toolbox or rtabmap)
- Nav2 autonomous navigation
- Dynamic atmosphere: time-of-day sun sweep + tau variation
- Experimental evaluation: SLAM accuracy vs. scenario, SLAM vs. tau
- 8-page iSpaRo paper

**Explicitly out of scope for v1.0:**
- OmniLRS-level photorealism (deferred to v2.0)
- Terramechanics (deferred to v3.0)
- RL environments (deferred to v3.0)
- Multi-robot coordination (future work)

### v2.0 (Post-iSpaRo): High Photorealism

- OmniLRS-level PBR, anti-tiling, 4K HDRI, pebble scatter
- Photogrammetry rocks, production render settings
- Sim2Real perception benchmark (AI4Mars)

### v3.0 (Future): High Physical Fidelity

- Terramechanics (Bekker/Janosi)
- RL environments (Isaac Lab Gym API)
- Multi-robot coordination
- Ls-parameterized seasonal variation

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

1. **Do NOT claim terramechanics fidelity in v1.0.** Physics = rigid body +
   Mars-calibrated friction. No BCM/SCM/DEM. Terramechanics is v3.0 plugin.
2. **Do NOT chase photorealism in v1.0.** Good-enough rendering + strong robotics.
   OmniLRS-level photorealism is v2.0. Do not block robotics work for visual polish.
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
0. **Check for active harness.** If `.claude/agents/` exists and the work falls
   within v1.0 scope (Wk1~Wk6), route the request through the
   `marslab-dev-orchestrator` skill instead of implementing directly. Single-developer
   direct mode is reserved for trivial questions, documentation tweaks, and Wk7-8
   paper writing.
1. Check which Phase/Week it belongs to. Respect dependency order.
2. Check if a reference codebase already solved it. Study before reimplementing.
3. Write config-driven, seed-reproducible code.
4. Include unit test.
5. If unsure about Isaac Sim API, say so rather than guessing deprecated APIs.

## 하네스: MarsLab v1.0 개발팀

**목표:** iSpaRo 2026 v1.0 (8주, 2026-04-14 ~ 2026-06-16) 개발을 6명 에이전트 팀으로 병렬 수행.

**트리거:** Wk1~Wk6 범위의 개발 작업 요청 시 `marslab-dev-orchestrator` 스킬을 사용한다. 단순 질문, 문서 오타 수정, Wk7~8 논문 작성은 직접 응답 가능. v2.0(photorealism) / v3.0(terramechanics, RL) 작업은 out-of-scope로 거절.

**팀 실행 모드:** 에이전트 팀 (6명). 모든 Agent 호출은 `model: "opus"`.

**상세 정의:** 에이전트 역할·통신 프로토콜·사용 스킬은 `.claude/agents/` 및 `.claude/skills/` 에 있다. 이 CLAUDE.md는 포인터만 제공한다 (중복 회피).

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-04-14 | 초기 하네스 구성 (6 agents, 9 skills, 1 orchestrator) | `.claude/` 전체 | iSpaRo v1.0 8주 병렬 개발 체계 구축. Plan: `~/.claude/plans/cheerful-brewing-hammock.md`. |
