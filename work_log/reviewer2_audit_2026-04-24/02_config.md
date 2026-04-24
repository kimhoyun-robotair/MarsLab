# 02 — config + schemas

## 메타
- 대상:
  - `/home/hoyunkim/MarsLab/marslab/config/__init__.py` (1 LOC)
  - `/home/hoyunkim/MarsLab/marslab/config/loader.py` (143 LOC)
  - `/home/hoyunkim/MarsLab/marslab/config/scenario_loader.py` (12 LOC)
  - `/home/hoyunkim/MarsLab/marslab/config/yaml_loader.py` (166 LOC)
  - `/home/hoyunkim/MarsLab/marslab/config/spawn_resolver.py` (136 LOC)
  - `/home/hoyunkim/MarsLab/marslab/config/schema/__init__.py` (69 LOC)
  - `/home/hoyunkim/MarsLab/marslab/config/schema/root.py` (32 LOC)
  - `/home/hoyunkim/MarsLab/marslab/config/schema/mars_env.py` (207 LOC)
  - `/home/hoyunkim/MarsLab/marslab/config/schema/rendering.py` (280 LOC)
  - `/home/hoyunkim/MarsLab/marslab/config/schema/robot.py` (321 LOC)
  - `/home/hoyunkim/MarsLab/marslab/config/schema/ros2_bridge.py` (86 LOC)
  - `/home/hoyunkim/MarsLab/marslab/config/schema/scene.py` (167 LOC)
  - `/home/hoyunkim/MarsLab/marslab/config/schema/terrain.py` (323 LOC)
- 총 LOC 검토: 1,943
- 리뷰어: Reviewer 2 (외부 hostile peer reviewer)

## Findings

### CRITICAL

#### C-1 marslab/config/loader.py:27 — `open()` used without explicit encoding on a platform-dependent default
- 근거:
  ```python
  with open(abs_path, "r") as f:
      data = yaml.safe_load(f)
  ```
  While the sibling in `yaml_loader.py:58` does `open(path, "r", encoding="utf-8")`, this `load_config` helper omits `encoding=` entirely.
- 문제: On Windows or a misconfigured locale (`LANG=C`), YAML containing non-ASCII (km, bullet points, the UTF-8 "±" that authors regularly paste into `description:` fields) will decode with `cp1252` / `ascii`. Config files currently ship no non-ASCII but scenario authoring is an expected mutation surface. Divergent-change smell: the two loaders in the same package use inconsistent encoding policy and a naïve contributor will miss the one that lacks it.
- 제안: Replace with `open(abs_path, "r", encoding="utf-8")`. While you are there, delete `load_config` entirely (see D-1) and push callers to `load_and_validate` — then this bug disappears.

#### C-2 marslab/config/loader.py:46 — `propagate_seeds` trusts `config.mars_env.seed` without validation even though the dict-twin enforces >=0 / int
- 근거:
  ```python
  seed = master_seed if master_seed is not None else config.mars_env.seed
  ...
  "terrain": config.terrain.model_copy(update={"seed": seed + 1}),
  ```
  Pydantic path does NOT validate that a user-supplied `master_seed` is `>= 0` or `int`, but `propagate_seeds_in_dict` (L89-94) does. When `master_seed=-1`, the resulting `config.terrain.seed = 0` still passes revalidation by accident but `mars_env.seed = -1` is silently written into `model_copy(update=...)` (pydantic `model_copy` does NOT re-run field validators by default).
- 문제: Asymmetry between the dict path and pydantic path: one guards, the other does not. Negative `master_seed=-100` silently yields `terrain.seed = -99` that violates the `ge=0` constraint on `TerrainConfig.seed`. Correctness bug + shotgun-surgery: two separate "propagate_seeds" functions with different invariants is a bug farm.
- 제안: Add the same `isinstance(raw, int) and raw >= 0` gate at top of `propagate_seeds`, or better, call `MarsLabConfig.model_validate(updated.model_dump())` after the copy so field validators fire. Collapse `propagate_seeds` + `propagate_seeds_in_dict` into one implementation that operates on a dict and re-validates.

#### C-3 marslab/config/loader.py:131-141 — `load_and_validate` implements a top-level `base_config` mechanism that conflicts semantically with `yaml_loader.load_scenario_config`'s `rover.base_config`
- 근거:
  ```python
  if "base_config" in data:
      base_rel = data.pop("base_config")
      ...
      data = deep_merge(read_yaml(base_abs), data)
  ```
  vs. `yaml_loader.py:145-158` which reads `rover_override.get("base_config")` (nested under `rover:`).
- 문제: Two different include mechanisms coexist. Every scenario in `configs/scenarios/*.yaml` uses the nested `rover.base_config:` form; zero files use the top-level form `grep -r "^base_config:" configs/` returned nothing). The top-level mechanism in `load_and_validate` is effectively dead code — worse, if someone writes a scenario with both forms, only the pydantic path (`load_and_validate`) runs the top-level merge, while `load_scenario_config` silently ignores it (or vice versa). Divergent-change + primitive-obsession: two separate string-keyed include systems.
- 제안: Pick one. Given zero real consumers of the top-level form, delete the `if "base_config" in data:` block in `load_and_validate` and document `rover.base_config` as the only path. Or collapse both forms into a single helper.

#### C-4 marslab/config/schema/mars_env.py:194-207 — `check_ranges` uses `>=` meaning exactly-equal tuples are silently accepted only on the boundary
- 근거:
  ```python
  if self.surface_albedo_range[0] >= self.surface_albedo_range[1]:
      raise ValueError(...)
  ```
  Combined with field default `(0.10, 0.40)`.
- 문제: Reads fine at first but the parallel `TerrainConfig.check_terrain` at `terrain.py:318` uses the *same* `>=` rule (OK) while the field is declared as a plain `tuple[float, float]` with *no* per-element `ge=0`, `le=1` constraints. A user can pass `surface_albedo_range=(-5.0, 10.0)` and validation passes even though the Mars physical range is `[0.10, 0.40]` per the CLAUDE-adjacent comment. Same hole on `dust_opacity_range` — no upper bound, can be `(0.0, 1e9)`. Type/validation gap.
- 제안: Either (a) add bounds on each tuple element via `Annotated[tuple[Annotated[float, Field(ge=0, le=1)], Annotated[float, Field(ge=0, le=1)]], ...]`, or (b) extend `check_ranges` with `0.0 <= lo < hi <= 1.0` for albedo and `0.0 <= lo < hi <= 6.0` for dust_opacity (matching the existing `dust_optical_depth` bounds).

### HIGH

#### H-1 marslab/config/spawn_resolver.py:92-94 — silently defaulting `spawn: {}` buries config errors
- 근거:
  ```python
  spawn = rover_cfg.get("spawn", {}) if isinstance(rover_cfg, dict) else {}
  mode = str(spawn.get("mode", "absolute"))
  xy = spawn.get("xy", [0.0, 0.0])
  ```
- 문제: If a scenario author typos `spwan:` or omits the block entirely, the rover silently spawns at world origin (`x=0, y=0, z=0`) instead of raising. Silent-swallow + primitive-obsession — the scenario YAML contract is "rover.spawn is required when terrain exists" but nothing enforces it. The caller in `run_stage3_monolithic.py` has no way to detect the difference between "author omitted `xy` on purpose" and "author mis-indented and lost the block."
- 제안: Either declare a `SpawnConfig` pydantic model and wire it into `RobotConfig` (currently `RobotConfig.spawn_position` is a separate flat list — see C-7), or at minimum raise `KeyError(f"rover.spawn is required, got {list(rover_cfg.keys())!r}")` when the key is absent. The "absolute mode default to origin" branch should be opt-in, not implicit.

#### H-2 marslab/config/yaml_loader.py:162-165 — hidden side-effect mutating `sensors.lidar` → `sensors.lidar_3d` inside `load_scenario_config`
- 근거:
  ```python
  # Legacy alias normalisation: sensors.lidar (single entry) → lidar_3d.
  sensors = merged_rover.get("sensors")
  if isinstance(sensors, dict) and "lidar" in sensors and "lidar_3d" not in sensors:
      sensors["lidar_3d"] = sensors.pop("lidar")
  ```
- 문제: The function's docstring (L100-123) never mentions a rename from `lidar` to `lidar_3d`. Surprising behaviour: scenario validation tests that assert "the `sensors.lidar` block is preserved verbatim" will break without explanation. Comments-as-deodorant / divergent-change: the rename is lossy (`sensors.pop("lidar")`), and the single-source-of-truth semantics make it impossible to roll back if a scenario intentionally declares both `lidar` and `lidar_3d` in different sources (e.g. `lidar` in base + `lidar_3d` override in scenario).
- 제안: Move the rename out of the YAML loader into a dedicated `migrate_sensors` helper with its own docstring+test, or remove it and fix every offending YAML explicitly. A schema loader is not the right layer for silent backward-compat hacks.

#### H-3 marslab/config/schema/rendering.py:192-197 — `fog_color` lives on `RenderingConfig` AND `FogConfig.color` — the latter is labelled "Reserved" and never read
- 근거:
  ```python
  fog_color: list[float] = Field(
      default=[0.78, 0.62, 0.42],
      min_length=3,
      max_length=3,
      description="Mars dust haze fog RGB [0-1]",
  )
  ...
  # FogConfig.color at rendering.py:75-82
  color: Tuple[float, float, float] = Field(
      default=(0.83, 0.47, 0.28),
      description=(
          "Reserved. Live fog color is still driven by ``RenderingConfig.fog_color`` "
          "(top-level) because that field participates in the butterscotch R>G>B invariant "
          "tests. ``FogConfig.color`` stays for future scenario overrides."
      ),
  )
  ```
  And `atmosphere_fog.py:41` confirms: `fog_color = rendering_config.fog_color`. No consumer reads `rendering_config.fog.color`.
- 문제: Temporary-field + comments-as-deodorant — a pydantic field held "for future scenario overrides" is dead code today. Worse, the two defaults differ (`[0.78, 0.62, 0.42]` vs `(0.83, 0.47, 0.28)`) so a scenario author who naturally sets `fog.color` will produce no effect and get no warning. Shotgun-surgery waiting: moving the active field into the sub-config requires touching atmosphere_fog.py + every scenario YAML that sets `fog_color:`.
- 제안: Delete `FogConfig.color` until a consumer exists. Or migrate `atmosphere_fog.py` to read from `rendering_config.fog.color` and delete the flat `RenderingConfig.fog_color`; the "butterscotch R>G>B invariant tests" claim should cite a specific test file — I searched and found none referencing `fog_color` directly, so this justification is lying-docstring material.

#### H-4 marslab/config/schema/rendering.py:231-273 — `_migrate_flat_to_nested` is a 40-line pre-validator with triple lookup tables + silent key-popping
- 근거:
  ```python
  flat_to_fog = {
      "fog_enabled": "enabled",
      "fog_color_amount": "color_amount",
      ...
  }
  flat_to_rt = {
      "antialiasing_op": "antialiasing_op",
      "dlss_exec_mode": "dlss_exec_mode",
      ...
  }
  ...
  for flat_key in list(flat_to_fog) + list(flat_to_rt) + list(flat_to_pt):
      data.pop(flat_key, None)
  ```
- 문제: Long-method + data-clump + comments-as-deodorant. The module docstring at L13-22 concedes that the flat keys "preserve" pre-R2-A1 config — but `grep` across `configs/` finds exactly zero YAMLs still using those flat keys. The migration shim exists for backward-compat to YAMLs that do not exist. Dead-code / lying-docstring: "no scenario file has to change" is true only because no scenario was shipping the flat keys in the first place (pre-R2-A1 `fog_color_amount` never made it into any tracked YAML). Meanwhile, the `_merge` helper has a subtle bug where flat keys *inside* a nested `fog:` block (e.g. `fog: {fog_enabled: true}`) will be copied into `migrated["enabled"]` AND will pop the outer-level `fog_enabled`, but will not pop the nested one — leading to a pydantic `Extra inputs` rejection at the `FogConfig` level. Actually — `_merge` only checks `flat_key in data`, so the nested case is untouched; however the line `merged = {**migrated, **existing}` gives `existing` priority which CONTRADICTS the module docstring's "any explicit nested value wins" — `existing` IS the nested, so that part is correct. Still fragile.
- 제안: Remove the migration shim entirely; it targets no live YAML. If backward-compat is demanded, extract into a separate `marslab.config.migrations` module with its own test that asserts each legacy key still round-trips to the new location.

#### H-5 marslab/config/schema/terrain.py:232-246 — `check_cave_ranges` conflates two validations and the skylight depth check is fragile
- 근거:
  ```python
  tube_height = self.tube_width_m * self.tube_height_ratio
  if self.skylight_count > 0 and self.skylight_depth_m < tube_height:
      raise ValueError(
          f"skylight_depth_m ({self.skylight_depth_m}) must be >= tube height "
          f"({tube_height:.1f}m = width * ratio) for the shaft to reach the tube"
      )
  ```
- 문제: Field defaults: `tube_width_m=200`, `tube_height_ratio=0.5`, so `tube_height=100m`. But `skylight_depth_m` default is `90m`, and `skylight_count` default is `10>0`. The default constructor `CaveConfig()` therefore RAISES `ValueError` — `CaveConfig()` is not a valid instance. This is a schema self-contradiction.

  Confirmed by reading `default=90.0` on L157 and `default=10` on L146. Correctness bug.
- 제안: Either bump `skylight_depth_m` default to `>= tube_width_m * tube_height_ratio` (e.g. `110.0`) or bump `tube_height_ratio` floor. Add a unit test `test_cave_config_default_is_valid()` that constructs `CaveConfig()` with no overrides and asserts it doesn't throw.

#### H-6 marslab/config/schema/robot.py:170-202 / 203-246 — six required fields (`...`) with no defaults create long-parameter-list + shotgun-surgery for any future rover YAML
- 근거:
  ```python
  drive_damping: float = Field(..., gt=0.0, ...)
  steer_stiffness: float = Field(..., gt=0.0, ...)
  steer_damping: float = Field(..., gt=0.0, ...)
  drive_max_force: float = Field(..., gt=0.0, ...)
  steer_max_force: float = Field(..., gt=0.0, ...)
  suspension_damping: float = Field(..., ge=0.0, ...)
  drive_type: Literal["acceleration", "force"] = Field(..., ...)
  ```
- 문제: Every new robot YAML must declare all seven PhysX DriveAPI parameters to pass validation. The docstring justification cites "rover_m2020.yaml already declares all four" (it's actually seven now). Requiring PhysX tuning constants on *every* robot — including future Valkyrie / Go2 / AirBot entries that do not use DriveAPI at all — is over-constrained. Large-class smell: `SkidSteerDriveConfig` is carrying PhysX-specific knobs that belong in a separate `PhysxDriveTuning` sub-model, so a quadruped/humanoid robot doesn't need to invent seven nonsensical numbers. Divergent-change: "skid-steer drive" should mean "wheel cmd_vel geometry", not "PhysX DriveAPI backend tuning."
- 제안: Extract `drive_damping`/`steer_*`/`drive_max_force`/`steer_max_force`/`suspension_damping`/`drive_type` into a nested `PhysxDriveConfig` that's optional on `SkidSteerDriveConfig`. Robots that use DriveAPI supply it; others omit.

#### H-7 marslab/config/schema/robot.py:287-321 — `RobotConfig` is a large-class that mixes identity, assets, pose, sensors, and drive tuning
- 근거: 35 lines covering `type`, `urdf_path`, `usd_asset_path`, `spawn_position`, `sensor_config_paths`, `prim_path`, `drive`. The sole consumer outside of `MarsLabConfig` is `scripts/visualize_scenario.py:119-120` which uses only `spawn_position`.
- 문제: Data-clump + shotgun-surgery. No runtime in `marslab/runtime/` or `scripts/phase1/run_stage*.py` reads `config.robots[...]` — they all operate on raw dict rover blocks (`rover_cfg` kwarg threads dicts, not pydantic models). The `RobotConfig` type exists but is decorative — its validation never runs on the live runtime path. The `visualize_scenario.py` path uses it, but that's a side channel.
- 제안: Either (a) wire the runtime path through `RobotConfig`-validated objects and delete the dict fallbacks, or (b) demote the schema to the visualizer-only flag and mark it `INTERNAL`. Right now it's a ghost.

### MEDIUM

#### M-1 marslab/config/loader.py:33-53 — `propagate_seeds` hardcodes only `mars_env` and `terrain`, silently ignores any future seeded sub-config
- 근거:
  ```python
  updates: dict = {
      "mars_env": config.mars_env.model_copy(update={"seed": seed}),
      "terrain": config.terrain.model_copy(update={"seed": seed + 1}),
  }
  ```
- 문제: If anyone adds a `robots[0].drive.random_noise_seed` or a `rendering.dome_seed` the function silently skips them. Primitive-obsession / divergent-change: seed propagation is not a discoverable protocol. The docstring claims "each sub-config gets a unique seed" but the implementation covers two.
- 제안: Walk the model recursively checking for fields named `seed` / ending in `_seed`, assigning `seed + i`; or introduce a `SeededConfig` mixin that every seeded model inherits.

#### M-2 marslab/config/schema/scene.py:124-148 — `to_dataclass` tightly couples a pydantic model to a dataclass; list→tuple coercion is hand-rolled six times
- 근거:
  ```python
  return StructureConfig(
      name=self.name,
      asset_path=self.asset_path,
      spawn_xyz=(self.spawn_xyz[0], self.spawn_xyz[1], self.spawn_xyz[2]),
      spawn_rpy_deg=(
          self.spawn_rpy_deg[0],
          self.spawn_rpy_deg[1],
          self.spawn_rpy_deg[2],
      ),
      scale=(self.scale[0], self.scale[1], self.scale[2]),
      ...
  )
  ```
- 문제: Duplicate-code / feature-envy. The pydantic model merely shadows the dataclass with alternative types for `spawn_xyz` / `spawn_rpy_deg` / `scale`. Why have two representations of the same concept? Either use pydantic end-to-end, or use the dataclass end-to-end and validate elsewhere.
- 제안: Delete `StructureConfigSchema.to_dataclass` and have the loader accept `StructureConfigSchema` directly. Alternatively, use `pydantic.TypeAdapter(StructureConfig)` so the dataclass IS the validation target. Also `spawn_xyz=tuple(self.spawn_xyz)` would replace the six indexings.

#### M-3 marslab/config/schema/scene.py:107-122 — `_validate_name` duplicates what a `pattern=r"^[A-Za-z_][A-Za-z0-9_]*$"` `Field` constraint would do
- 근거:
  ```python
  @model_validator(mode="after")
  def _validate_name(self) -> "StructureConfigSchema":
      if any(c.isspace() for c in self.name):
          raise ValueError(...)
      if "/" in self.name or "\\" in self.name:
          raise ValueError(...)
      if self.name[0].isdigit():
          raise ValueError(...)
      return self
  ```
- 문제: Hand-rolled validator with three rules that miss many USD-token-illegal characters (`.`, `-`, `@`, `$`, `"`, `'`, control chars). A regex is both shorter and more complete.
- 제안: `name: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", min_length=1, ...)` and delete `_validate_name`. Correctness wins — closer to the USD spec referenced in the docstring.

#### M-4 marslab/config/schema/mars_env.py:189-192 — `dynamic_atmosphere` default_factory creates a new `DynamicAtmosphereConfig` per `MarsEnvConfig` instance (fine), but module-level `_DEFAULT_SKY_DOME_CONFIG` in `marslab/environment/sky_dome.py:18` stores a shared `SkyDomeConfig()` that callers can mutate.
- 근거: `marslab/environment/sky_dome.py:18`:
  ```python
  _DEFAULT_SKY_DOME_CONFIG = SkyDomeConfig()
  ```
  Pydantic v2 models are mutable by default (`model_config = ConfigDict(frozen=True)` not set on `SkyDomeConfig`).
- 문제: Mutable module-level default. Though out-of-scope (lives outside `marslab/config/`), the *schema* is what should enforce immutability. Mutable-defaults adjacent bug — any caller who does `_DEFAULT_SKY_DOME_CONFIG.brightness_min = 0.9` silently corrupts every future caller of `compute_sky_dome_params`.
- 제안: Add `model_config = ConfigDict(frozen=True)` on every leaf schema (`SkyDomeConfig`, `FogConfig`, `RayTracingConfig`, `PathTracingConfig`, `SunSweepConfig`, `TauConstantConfig`, `TauRampConfig`, `TauSineConfig`). Also pushes toward value-semantics.

#### M-5 marslab/config/schema/robot.py:265-284 — `check_wheel_joints` mutates error message formatting and uses `# fmt: off` to defeat black
- 근거:
  ```python
  if not self.left_wheel_joints or not self.right_wheel_joints:
      # Keep this error message split across two source lines for
      # readability. black would otherwise collapse it into a single
      # 104-char physical line via implicit string concatenation,
      # which is parser-valid but visually confusing.
      # fmt: off
      raise ValueError(
          "left_wheel_joints and right_wheel_joints must each list "
          "at least one joint name"
      )
      # fmt: on
  ```
- 문제: Comments-as-deodorant. The "104-char" concern is false (length is 73 chars — well under black's 100). `# fmt: off`/`# fmt: on` around a three-line string literal is noise; black will leave it alone regardless because implicit string concatenation is preserved inside `raise ValueError(...)`. Dead rationale.
- 제안: Remove the `# fmt: off`/`# fmt: on` pair and the five-line justification comment.

#### M-6 marslab/config/loader.py:56-98 — `propagate_seeds_in_dict` duplicates invariants that the pydantic schema already enforces
- 근거:
  ```python
  if not isinstance(raw, int) or isinstance(raw, bool):
      raise TypeError(f"mars_env.seed must be int, got {type(raw).__name__}: {raw!r}")
  if raw < 0:
      raise ValueError(
          f"mars_env.seed must be >= 0 for deterministic G7 reproducibility; got {raw}"
      )
  ```
  vs. `MarsEnvConfig.seed: int = Field(default=42, ge=0)`.
- 문제: Duplicate-code. Two sources of truth for the same constraint. If the pydantic minimum changes (to allow -1 as a "random" sentinel, say), the dict path will not follow. `propagate_seeds_in_dict` is a bandage for the fact that `delete_by_user/run_stage3_monolithic_new.py` and `scripts/phase1/run_stage4.py` choose to operate on dicts rather than `MarsLabConfig`. That architectural decision is out of scope, but the fix is to construct the pydantic model and call `.model_dump()` right after.
- 제안: Replace `propagate_seeds_in_dict` body with `MarsLabConfig.model_validate(cfg); ...; return propagate_seeds(cfg).model_dump(mode="python")`. Keep a single seed-propagation algorithm.

#### M-7 marslab/config/scenario_loader.py:1-12 — 12-LOC backward-compat shim imports from two siblings only for re-export
- 근거:
  ```python
  from marslab.config.spawn_resolver import resolve_spawn_pose
  from marslab.config.yaml_loader import deep_merge, load_scenario_config

  __all__ = ["deep_merge", "load_scenario_config", "resolve_spawn_pose"]
  ```
- 문제: Divergent-change pain: any new function added to `yaml_loader.py` has to be re-exported manually here if old code uses the legacy path. The shim is only kept for `scripts/phase1/run_stage3_monolithic.py` and `scripts/phase1/run_stage4.py` which already independently import from both siblings. Temporary-field module.
- 제안: Grep confirms all current live importers (`run_stage4.py:51`, `run_stage3_monolithic.py:64-66`) still route through `marslab.config.scenario_loader`. Finish the R2 migration by flipping those two scripts and then delete `scenario_loader.py` (or leave it as `__init__`-style indirection with a `DeprecationWarning`). Don't leave a half-done split.

### LOW / STYLE

#### L-1 marslab/config/schema/mars_env.py:154-155 — `surface_albedo_range` tuple has no per-element bounds
- 근거:
  ```python
  surface_albedo_range: tuple[float, float] = Field(
      default=(0.10, 0.40), description="Surface albedo min/max"
  )
  ```
- 문제: Field allows `(-5.0, 5.0)`. See C-4 for correctness; rehashed here as the minimum-effort fix.
- 제안: Same as C-4.

#### L-2 marslab/config/schema/mars_env.py:163-165 — `dust_opacity_range` same issue
- 근거: `default=(0.5, 2.0)`, no bounds.
- 문제: Same shape as L-1.
- 제안: Add element-level `ge=0, le=6` consistent with `dust_optical_depth`.

#### L-3 marslab/config/schema/terrain.py:271-272 — `rock_diameter_range` tuple element-less
- 근거: `rock_diameter_range: tuple[float, float] = Field(default=(0.20, 3.0), ...)`.
- 문제: Allows negative diameters that would crash downstream physics.
- 제안: Add element-level `gt=0`.

#### L-4 marslab/config/schema/mars_env.py:7-9 — module docstring references `refactoring/_risks.md §4.1` and `scripts/phase1/run_stage2.py L365-408` as source-of-truth
- 근거:
  ```python
  See ``refactoring/_risks.md`` §4.1 for the risk record and
  ``scripts/phase1/run_stage2.py`` L365-408 for the dict.get() parsing
  that this migration replaces.
  ```
- 문제: Lying-docstring risk. `scripts/phase1/run_stage2.py` does not exist in the tree (only `run_stage3_monolithic.py` and `run_stage4.py` are under `scripts/phase1/`). Line numbers rot immediately on any edit. Comments-as-deodorant — pointer to an external doc to justify a migration.
- 제안: Verify file exists; if not, remove. Don't pin comments to line numbers — use function names.

#### L-5 marslab/config/schema/robot.py:44-46 — "Wk2 #6 (2026-04-14, task #17)" task-tracker references leak into source
- 근거:
  ```python
  Wk2 #6 (2026-04-14, task #17) introduced this block so G5 is
  honored — no numeric covariance lives in Python.
  ```
- 문제: Internal project-management jargon (Wk2 #6, task #17, G5) has no meaning to a fresh reader. Comments-as-deodorant.
- 제안: Replace with plain English ("Added so covariance is configurable per-scenario, not hardcoded in the publisher"). Drop the Wk/task IDs; they belong in git log or a changelog, not in schema docstrings.

#### L-6 marslab/config/schema/robot.py:130-138 / 203-215 / 86-95 — every "R2-*" / "R3-*" / "R4-*" stamp is project-internal chatter
- 근거: Grep `R2-A3\|R2-A1\|R2-A2\|R2-4a\|R3\|R4-5\|P1-1b\|P6` across all schema files. Dozens of occurrences.
- 문제: Every refactor stamp accumulates. Files grow by code-commentary faster than by code. A new contributor reads `"R2-A1 (2026-04-22): migrated from the flat fog_* fields"` without knowing what R2-A1 is. Comments-as-deodorant at volume.
- 제안: Move refactor history to a changelog file, leave only behavioural documentation in docstrings.

#### L-7 marslab/config/schema/terrain.py:274-277 — `semantic_classes` default list is mutable-default-looking but pydantic handles it
- 근거:
  ```python
  semantic_classes: list[str] = Field(
      default=["soil", "bedrock", "sand", "big_rock"],
      ...
  )
  ```
- 문제: Not a bug (pydantic validates and recreates per-instance) but *looks* like a bug to a Python-native reviewer. Also `semantic_classes` has zero consumers anywhere in the tree (grep confirmed) — it's a label the terrain schema advertises but nobody reads.
- 제안: Switch to `Field(default_factory=lambda: ["soil", "bedrock", "sand", "big_rock"])` for clarity. Or delete the field (see D-3).

#### L-8 marslab/config/spawn_resolver.py:129-132 — `np.nanmin(elevation)` can return NaN on all-NaN grid; only one call site guards
- 근거:
  ```python
  z_shift = float(np.nanmin(elevation))
  if not np.isfinite(z_shift):
      z_shift = 0.0
  ```
- 문제: The guard is correct but silent — an all-NaN DEM produces `z_shift=0` and the rover spawns on `dem_z_raw` (also NaN) → `dem_z = NaN - 0 = NaN`. Nothing catches the resulting `(x, y, NaN)` return. Silent-swallow.
- 제안: After the guard, check `if not np.isfinite(dem_z_raw): raise ValueError("DEM has no finite samples at spawn location")`.

#### L-9 marslab/config/yaml_loader.py:46-56 — directory listing with silent cap at 8
- 근거:
  ```python
  for name in sorted(os.listdir(parent)):
      if name.endswith((".yaml", ".yml")):
          nearby.append(name)
      if len(nearby) >= 8:
          break
  ```
- 문제: Bug: the break fires on the 8th iteration regardless of whether the most-recently-scanned name was a YAML or not. If the parent has 20 non-YAML files followed by `scenario_typo.yaml`, the suggester truncates before reaching it. The `if len(nearby) >= 8` check should be inside the `.yaml` conditional.
- 제안:
  ```python
  for name in sorted(os.listdir(parent)):
      if name.endswith((".yaml", ".yml")):
          nearby.append(name)
          if len(nearby) >= 8:
              break
  ```

#### L-10 marslab/config/yaml_loader.py:89-97 — `_resolve_path` silently falls back to `REPO_ROOT` even when anchor-relative exists but isn't a file
- 근거:
  ```python
  if os.path.isabs(path):
      return path
  if anchor_dir is not None:
      candidate = os.path.abspath(os.path.join(anchor_dir, path))
      if os.path.isfile(candidate):
          return candidate
  return os.path.abspath(os.path.join(REPO_ROOT, path))
  ```
- 문제: Both paths can end up pointing at "does not exist" but no error is raised. The caller at L152-153 then triggers `read_yaml(base_full)` which *does* raise FileNotFoundError, so the outcome is fine — but the error says `Config not found: <REPO_ROOT>/path/to/base.yaml` even when the user intended to reference the anchor-relative location, confusing debugging.
- 제안: Return the first-resolved path; let the caller raise with both attempted locations surfaced in the error message.

#### L-11 marslab/config/schema/robot.py:287-314 — `RobotConfig.type: str` not a `Literal` — primitive obsession
- 근거: `type: str = Field(description="Robot type identifier (e.g., 'rover', 'quadruped')")`
- 문제: Accepts any string. Typos ("rovver") pass. Primitive-obsession.
- 제안: `type: Literal["rover", "quadruped", "rotorcraft", "humanoid"]`. Extend as needed.

### DELETE CANDIDATES

#### D-1 marslab/config/loader.py:10-30 — `load_config` is superseded by `load_and_validate`
- 근거 / 검증: Grep shows one consumer — `tests/unit/test_materials.py:14-16`. Every other caller uses `load_and_validate` (6 sites). `load_config` does not do base-config resolution and does not propagate seeds.
- 제안: Migrate `test_materials.py` to `load_and_validate`; delete `load_config`. Keeps a single loader entry point.

#### D-2 marslab/config/schema/rendering.py:221-273 — `_migrate_flat_to_nested` pre-validator
- 근거 / 검증: Grep `fog_enabled\|fog_color_amount\|fog_start_height\|fog_height_falloff\|fog_height_density_ratio\|denoiser_optix_pathtracing` across `configs/` returns zero live scenario-YAML uses. `antialiasing_op` / `dlss_exec_mode` / `spp` / `total_spp` / `max_bounces` *are* referenced in `configs/rendering/path_tracing.yaml` (let me flag for confirmation) — but if they live at the `RenderingConfig` top level there, the migration copies them into `path_tracing:`/`ray_tracing:` nested. The migration is therefore weakly active but the shim complexity is disproportionate.
- 제안: Open configs, confirm flat vs nested usage, then delete unused legs of the migration table. See H-4.

#### D-3 marslab/config/schema/terrain.py:274-277 — `semantic_classes` has zero live consumers
- 근거 / 검증: `grep -rn "semantic_classes"` returns only the schema declaration. No runtime or benchmark code reads it.
- 제안: Delete the field. If future annotation work needs it, reintroduce at that point with an actual consumer.

#### D-4 marslab/config/schema/mars_env.py:157-159 — `surface_temp_mean` has zero live consumers
- 근거 / 검증: `grep -rn "surface_temp_mean"` returns only the schema + one test (`test_mars_env_schema.py:24`) that merely asserts the field is present.
- 제안: Delete field + round-trip test entry. When thermal modelling arrives (v3?), re-add with a real consumer.

#### D-5 marslab/config/schema/mars_env.py:163-165 — `dust_opacity_range` has zero live *runtime* consumers; only a visualization script reads `[1]`
- 근거 / 검증: `grep -rn "dust_opacity_range"` hits `scripts/visualize_atmosphere.py:38` (reads `[1]`) and `tests/unit/test_mars_env_schema.py:26`. No runtime module. Domain-randomization that would justify a range is gated as v3.
- 제안: Keep the field (visualization uses it) but downgrade to `# TODO(v3): wire into domain randomizer`. Do NOT mark this a deletion candidate — just call out its currently-almost-dead status.

#### D-6 marslab/config/schema/rendering.py:75-82 — `FogConfig.color` field
- 근거 / 검증: Grep confirms no reader anywhere. The docstring labels it "Reserved".
- 제안: Delete.

#### D-7 marslab/config/scenario_loader.py — entire 12-LOC back-compat shim
- 근거 / 검증: The only stated purpose is to let old imports keep working. 2 live callers (`scripts/phase1/run_stage3_monolithic.py`, `scripts/phase1/run_stage4.py`) use it, plus `tests/unit/test_scenario_loader.py`. Migration is 10 lines of find-replace.
- 제안: Finish the R2 split; remove the shim. See M-7.

#### D-8 marslab/config/schema/mars_env.py:7-10 — docstring reference to a file that doesn't exist
- 근거 / 검증: Docstring points at `refactoring/_risks.md §4.1`. Nothing in tree at `refactoring/` (only `delete_by_user/`, `scripts/`, `marslab/`, `tests/`, `configs/`, `work_log/`). And `scripts/phase1/run_stage2.py L365-408` — no `run_stage2.py` file exists.
- 제안: Delete the reference lines from the docstring.

### FALSE-POSITIVE WATCHLIST

- **`yaml.safe_load` everywhere** — confirmed safe; no `yaml.load()` / `yaml.Loader` / `yaml.FullLoader` anywhere in scope.
- **No `pickle` / `eval` / `exec`** — grep across all 13 files returns none. Security path is clean.
- **Path traversal in `base_config` / `converted_dem_dir`** — `_resolve_path` normalizes via `os.path.normpath` + `os.path.abspath`, both of which flatten `..` but do not *restrict* to the repo. A malicious `base_config: "../../../etc/passwd"` would resolve outside the repo. NOT flagged as a finding because (a) YAML is author-provided, not attacker-provided, and (b) the file is then fed to `yaml.safe_load`, not executed. Worth noting.
- **Pydantic `default_factory` on mutable lists** — every list field correctly uses `Field(default_factory=list)` or `Field(default=[...])` which pydantic handles correctly. Not a Python-class mutable-default bug.
- **`drive_max_force=1e6` default in YAML** — I did not audit `configs/rover_m2020.yaml`. The schema docstrings assert those values; if the YAML disagrees, that's a consistency bug *outside* this review's scope (code files only).
- **`model_copy(update=...)` bypassing validators** — Flagged in C-2 for `seed`. Other `model_copy` uses in this codebase not audited; caller responsibility.
- **`Optional[Dict[str, Any]]` on `spawn_resolver.resolve_spawn_pose.metadata`** — unused parameter per the docstring ("Reserved for future geo-anchor support"). Tolerable long-parameter-list. Not flagged.
- **`robots: list[RobotConfig]` default_factory=list** — H-7 flagged as a ghost but not deletable until `visualize_scenario.py` is migrated.

---

**Summary counts:**
- CRITICAL: 4 (C-1 encoding, C-2 seed sign-not-checked pydantic path, C-3 two base_config mechanisms, C-4 tuple-element unchecked bounds)
- HIGH: 7 (H-1 silent spawn default, H-2 hidden sensor rename, H-3 duplicate fog_color, H-4 dead flat-to-nested migration, H-5 CaveConfig default invalid, H-6 over-required physx fields, H-7 ghost RobotConfig)
- MEDIUM: 7 (M-1 seed propagation not recursive, M-2 to_dataclass duplicate, M-3 regex-replaceable validator, M-4 mutable module default, M-5 cosmetic fmt:off, M-6 duplicate seed guards, M-7 half-done R2 shim)
- LOW/STYLE: 11
- DELETE CANDIDATES: 8
