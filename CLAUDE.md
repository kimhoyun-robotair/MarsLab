# CLAUDE.md — MarsLab Development Guidelines

## Project Overview

MarsLab is an open-source Mars simulation platform providing standardized mission
scenarios for planetary/field robotics research, built on NVIDIA Isaac Sim 5.1.
Target: iSpaRo 2026 Regular Paper (8 pages), submission deadline **2026-06-15**.

**Repository**: `MarsLab/` (Apache 2.0 license)
**Engine**: Isaac Sim 5.1 + Isaac Lab
**Core Stack**: Python 3.12+, ROS2 Jazzy, Isaac Sim Extensions, USD/URDF

---

## Operating Principles (always-on, OP-1 ~ OP-5)

These five principles govern HOW work is executed. They are non-negotiable and
apply to every development task regardless of phase or scope.

### OP-1: Parallel subagent execution
- All non-trivial development tasks are routed through subagents in parallel.
- Maximum **5 concurrent subagents**. Any task that needs more than 5 concurrent
  agents requires explicit user approval with a written justification.
- Strict scope isolation: each agent's write-surface is documented in advance,
  and no agent may write to another agent's surface without approval.
- Cross-validation gate: agent results are verified by either (a) a separate
  agent, or (b) a self-verification step with file:line evidence.

### OP-2: Reviewer 2 mode (always-on)
- Aggressive, evidence-based critique on every claim, decision, and output.
- file:line citations are required to support any non-trivial claim.
- No claim is accepted without verification. This applies to user proposals,
  external references, and the assistant's own outputs equally.
- Disagreement is preferred to silent acquiescence.

### OP-3: Hard deadlines
- **MarsLab v1.0 dev complete: 2026-04-30** (public-availability quality + user-friendly
  features). Dockerize and Wiki are user-led post-sprint and may finish later, but the
  code/feature scope freezes 2026-04-30.
- **iSpaRo 2026 paper submission: 2026-06-15.**
- v0.7 baseline: 2026-04-24 (Isaac Sim 5.1 base + large refactor + bugfix).
- v0.9 Codebase: 2026-04-28 (Full Pipeline Integration : DEM Loader + URDFtoUSD + Sensor + Scene Rendering + 3D SLAM Package)

### OP-4: Rollback ready
- Every task lands as a git commit unit so a single `git revert` recovers the
  prior state.
- All git commands are executed by the user, not the assistant
  (memory: feedback_no_git_commands).

### OP-5: Scope isolation across agents
- Two agents may not edit the same line, function, or file section concurrently.
- When two agents must touch the same file, partition by class, block, or YAML
  key namespace; the partition is recorded in the sprint plan.
- Main thread is responsible for cross-checking partitions before agent launch
  and for blocking violations at validation time.

---

## Version Timeline

| Version | Date | Status | Scope |
|---------|------|--------|-------|
| v0.7 | 2026-04-24 | ✓ Complete | Isaac Sim 5.1 base, terrain/atmosphere/sensors/ROS2/SLAM stack, 893 unit + 3 integration tests, large refactor + bugfix |
| v0.9 | 2026-04-25 ~ 04-28 | ✓ Complete | Full Pipeline Integration : HiRISE DEM Loader, Scene/Robot/Rover Integration in One Rendering, ROS2 and  3D Mapping (Kinematic-ICP) |
| **v1.0 sprint** | **2026-04-28 ~** | **In progress** | Dockerize (Isaac Sim 5.1 layer) + Codebase Wikie + User's Code Review + Code Refactoring + Bug Fix + Additional Function Dev |
| v1.0 release | post-sprint | Pending | Based on Github (Local Code and Dockerfile) |
| v1.5 | post-paper | Future | Engineering & Maintanance : Easier GUI for .obj loader, non-ROS2 dataset export, scenario DSL, multi-robot (maybe rover), fault injection, Rocker-Bogie Controller, Hapke optics (#13), dust dynamics (#14), CARLA2Real-style sim2real  |
| v2.0 | 2026.06.15 ~ 11.15 | Future | Towards Sim2Real : Photorealistic Based on Generative AI |
| v3.0 | TBD | Deferred | Terramechanics (Bekker/Janosi), RL environments, multi-robot coordination |

**Reference for v1.5/v2.0 candidate features:** `planetary_rover_simulator_ideas.md`. But, Can be Changed.

---

## User Guidelines (G1-G10)

Ten guidelines govern WHAT to build and what stays out of scope. Every feature,
module, and task must trace back to one or more of these guidelines.

1. **G1: Field Robotics Platform.** MarsLab = standardized Mars robotics testing
   platform for SLAM, Nav, Exploration. v1.0 scope is in this CLAUDE.md.
2. **G2: RL is Future Work (v3.0).** No RL environments, reward functions, or
   Gym API wrappers until v3.0.
3. **G3: No Code Reuse.** Algorithm/flowchart inspiration only from OmniLRS /
   RLRoverLab. No code copying. No naming derived from reference codebases.
4. **G4: Robotics First, Photorealism Later.** v1.0 = good-enough rendering +
   strong robotics. v2.0 = OmniLRS-level photorealism. v3.0 = terramechanics.
5. **G5: All Configs in YAML.** Zero hardcoded constants in Python source.
6. **G6: Extreme Modularity.** Smallest units first, expand incrementally.
7. **G7: Unit Tests for Everything.** Visual inspection only when automated
   testing is impossible.
8. **G8: Work History Log.** `work_log/LOG.md` is the append-only log; entries
   are date-keyed 3-line summaries with artifact links.
9. **G9: User Review Gate.** User reviews and may request revisions; sprint
   plans live in `~/.claude/plans/`.
10. **G10: Higher Throughout.** Deep reasoning at every design decision using xhigh or max effort.
11. **G11. Temporary Files.** If you need to create temporary files, do not use `/tmp`; use `~/MarsLab/tmp` instead.

> **Retired:** former G9 (PLAN.md = architecture; PLAN.md was deleted 2026-04-24),
> former G12 (13-agent adversarial debate; replaced by OP-1 parallel subagents),
> former G13 (4-file output PLAN.md/PLAN_kor.md/CLAUDE.md/CLAUDE_kor.md;
> reduced to 2 files since PLAN.md is gone).

---

## Architectural Principles (P1-P3)

**P1: Flat P0 Architecture.**
No premature abstraction. Start with flat procedural code. Extract classes/patterns
only when empirical complexity demands it. No plugin systems, no god objects,
no registration mechanisms. Applies to MarsLab source (`marslab/`, `scripts/`,
`tests/`). Development harness (`.claude/agents/`, `.claude/skills/`) is
infrastructure and is exempt from P1.

**P2: Unidirectional Data Flow.**
Config → pure computation modules → Isaac Sim scene configuration → native sim loop.
No module modifies the simulation loop. No circular dependencies. Config is the
only shared dependency across modules.

**P3: Offline-First Testing.**
Every pure-computation module (environment physics, config validation, rock SFD,
label conversion) must be testable without Isaac Sim or GPU. Isaac Sim-dependent
code is isolated into separate functions/files clearly marked as integration-only.

---

## Coding Standards

### General
- Python 3.12+. Type hints on all public functions.
- Docstrings: Google style. Every public class/function must have one.
- Line length: 100 chars max.
- Formatter: `black`. Linter: `ruff` (`E,F,W,I,B,SIM` rule set).
- Type checker: `mypy` scoped to `marslab/config/` + `marslab/environment/`
  (Isaac-Sim-dependent code defers to runtime).
- Dependency audit: `pip-audit --strict` (any known CVE fails).
- **Every code change must pass before completion:**
  ```bash
  black --check marslab/ scripts/ tests/
  ruff check marslab/ scripts/ tests/
  mypy
  pytest tests/unit/ -q
  pip-audit --strict
  ```
- No global state. No singletons except for Isaac Sim app instance.

### Naming Conventions
- Files/modules: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- ROS2 topics: `/{robot_name}/{sensor_type}` (e.g., `/rover/rgb/image_raw`)
- Config keys: `snake_case` in YAML

### Isaac Sim Specific
- **Prefer** `omni.isaac.lab` APIs for simulation setup.
- **Permitted:** `pxr.*` (USD Python API) and `omni.isaac.core` when Isaac Lab
  provides no wrapper. Document the reason in a comment.
- **NEVER** use `omni.isaac.orbit` (deprecated).
- **"omni" in import paths** is NVIDIA's namespace, exempt from G3.
- **No code or naming** derived from OmniLRS, RLRoverLab, or any reference
  codebase. Algorithm/pattern inspiration only.
- Built-in USD assets (G1, Go2, Valkyrie): load from Isaac Sim asset path, do
  NOT copy into repo.
- Robot import: URDF → USD via offline conversion script
  (`tools/convert_urdf_to_usd.py`). Runtime URDF import is forbidden
  (memory: reference_rover_usd_source).

### Configuration
- ALL physical parameters go in `configs/`. Never hardcode in Python.
- Use `pydantic` for config schema validation. Every BaseModel uses
  `model_config = ConfigDict(extra="forbid")` so unknown YAML keys fail at
  load time instead of being silently dropped.
- Seed-based reproducibility: every randomized process must accept a `seed`
  parameter.

### Mars Physics Constants (Reference — put in config, not code)
```yaml
# Mars physics constants (validated by marslab.config.schema.MarsEnvConfig)
mars_env:
  gravity: 3.72             # m/s^2
  atmo_pressure: 610        # Pa
  atmo_density: 0.020       # kg/m^3
  surface_temp_mean: -60    # Celsius
  sol_duration_seconds: 88642  # 24h 37m 22s
  dust_opacity_range: [0.5, 2.0]
```

---

## Module Architecture

### Module Dependency Rules
1. No circular imports. If A imports B, B never imports A.
2. `config/` is the only shared dependency. All modules read from `MarsLabConfig`.
3. `environment/` has zero Isaac Sim imports. Pure Python. Offline-testable.
4. `terrain/dem_loader.py` and `terrain/rock_placer.py` have zero Isaac Sim imports.
5. `rendering/` depends on `environment/` (one-way) for computed params.
6. `robots/` depends only on `config/`.
7. No module modifies the Isaac Sim simulation loop.
8. Every randomized function accepts a `seed` parameter.

### Module Summary
| Module | Responsibility | Isaac Sim Required? |
|--------|---------------|---------------------|
| `config/` | YAML load, pydantic validation, seed propagation | No |
| `environment/` | Mars physics: sun position, Beer's law, COMIMART, sky params | No |
| `terrain/` | DEM loading, mesh building, rock placement, materials | Partial |
| `rendering/` | Sky dome, sun light, atmosphere fog, render mode | Yes |
| `robots/` | URDF→USD spawn for rover, Ackermann controller | Yes |
| `sensors/` | Camera, LiDAR, IMU spawn (Path B unified API) | Yes |
| `ros2_bridge/` | Sensor → ROS2 topic publishing, QoS profiles | Yes |
| `scene/` | structure_loader, mesh-only assets | Yes |
| `runtime/` | Stage-2 / Stage-3 main loop orchestration | Yes |
| `math/` | Quaternion utilities, transforms (offline) | No |

---

## Error Handling

- Config validation errors: raise `pydantic.ValidationError` with descriptive message.
- Missing files (DEM, URDF, HDRI): raise `FileNotFoundError` with full path.
- Isaac Sim API failures: catch, log with `logging.error()`, re-raise with context.
  For Kit teardown failure use `os._exit(1)`.
- Out-of-range physics values at runtime: raise `ValueError` with parameter name,
  value, and valid range.
- **Never silently swallow exceptions.** **Never use bare `except:`.**
- Use `_log_once(target_logger, exc, category, step_count, grace_steps=120)` from
  `marslab/runtime/main_loop.py` for once-per-category teardown noise suppression.
- All error messages must include enough context to diagnose without a debugger.

---

## Testing Requirements

### Unit Tests (No Isaac Sim)
Run with: `pytest tests/unit/ -q`. Current count: **1142 tests**.

Coverage areas:
- Config schema (`extra="forbid"` enforcement, pydantic validators)
- Beer's Law (Appelbaum airmass, NASA TM-102299, within 5%)
- COMIMART diffuse fraction (Vicente-Retortillo et al. 2015, Rayleigh floor 0.10)
- Sun position (Allison & McEwen spherical trigonometry, obliquity 24.94°)
- Golombek SFD (CFA curve within 10% of VL1/VL2/MPF/InSight)
- Seed determinism (same seed = identical output)
- Quaternion math (gimbal-lock branch, non-unit warning)
- Sensor YAML schema, ROS2 QoS profile mapping

### Visual Inspection
Documented in `tests/visual_inspection/checklist.md`. Logged in
`work_log/LOG.md` with screenshot links.  Isaac Sim runtime verification
(rover spawn, cmd_vel, sensor topics) is performed by launching the
full sim via `marslab/isaac_python.sh marslab/main.py --config <scenario>`
rather than a separate integration-test harness (the previous
`tools/run_integration_test.py` + `tests/integration/` suite was retired
2026-05-04 in favour of full-sim visual inspection).

### CI Pipeline
- `.github/workflows/unit_tests.yaml` — "matrix [3.12]", black + ruff + mypy + pytest
- `.github/workflows/security.yaml` — `pip-audit`

---

## What NOT To Do

1. **Do NOT claim terramechanics fidelity in v1.0.** Physics = rigid body +
   Mars-calibrated friction. No BCM/SCM/DEM. Terramechanics is v3.0.
2. **Do NOT chase photorealism in v1.0.** Good-enough rendering + strong robotics.
   v2.0 covers Hapke optics + dust dynamics. Do not block robotics work for
   visual polish.
3. **Do NOT hardcode Mars parameters.** Everything in YAML.
4. **Do NOT copy Isaac Sim built-in USD assets into the repo.** Reference by path.
5. **Do NOT use deprecated Isaac Sim APIs** (`omni.isaac.orbit`).
6. **Do NOT copy code from OmniLRS or RLRoverLab.** Inspiration only.
7. **Do NOT execute `git` from agent context.** All git operations are user-led
   (memory: feedback_no_git_commands).
8. **Do NOT use venv** for installation — pip install with `--break-system-packages`
   is the project preference (memory: feedback_no_venv).
9. **Do NOT comment out dead code as a hedge.** hard-delete is the default;
   rollback is `git log -p` (memory: feedback_no_delete_comment, R4 Option C).
10. **Do NOT speculate when uncertain.** Implement a verified workaround or run
    a diagnostic first (memory: feedback_no_speculative_fixes).
11. **Do NOT extend scope beyond the user's explicit instruction.** Execute *only*
    what was requested. Do not add toggles, flags, helper scripts, override keys,
    "future-proofing" abstractions, or unit tests that were not asked for. Do not
    invent feature patterns ("make it reusable", "add a config option") on top of
    a one-shot request. If a one-line edit answers the request, that is the entire
    deliverable. When unsure whether a follow-up is in scope, ask — do not assume.

---

## Reference Codebases (Study Only — G3)

| Codebase | What to Learn | Link |
|----------|---------------|------|
| OmniLRS | Terrain gen pipeline, ROS2 bindings, rock placement | github.com/OmniLRS/OmniLRS |
| SRB | Modular task registry, sim-to-real automation | arXiv:2509.23328 |
| RLROVERLAB | Isaac Lab API patterns, three-mesh pattern | github.com/abmoRobotics/isaac_rover_orbit |
| unitree_sim_isaaclab | G1/H1 Isaac Lab integration pattern | github.com/unitreerobotics/unitree_sim_isaaclab |
| Sim2Dust | DreamerV3 world model RL, zero-shot transfer | arXiv:2508.11503 |

---

## Communication Protocol

When asked to implement a feature:
1. Check sprint plan in `~/.claude/plans/` and the version timeline above. Reject
   v2.0/v3.0 work explicitly.
2. Apply OP-1 (parallel subagents, max 5) and OP-2 (Reviewer 2 mode).
3. Check if a reference codebase already solved it. Study before reimplementing
   (G3: study only, no copy).
4. Write config-driven, seed-reproducible code (G5).
5. Include unit test (G7).
6. If unsure about Isaac Sim API, say so rather than guessing deprecated APIs.
7. Log a 3-line entry in `work_log/LOG.md` on completion (G8).

**Sprint mode (current):** subagents are launched directly via the Agent tool
under the active sprint plan. The previous Wk1-Wk6 6-agent harness is retired
in favor of OP-1 sprint-scoped delegation.
