# 01 — cli / runtime / sim / scene

## 메타
- 대상 (15 files):
  - `marslab/cli/__init__.py` — 32 LOC
  - `marslab/cli/stage2_args.py` — 53 LOC
  - `marslab/cli/stage3_args.py` — 61 LOC
  - `marslab/runtime/__init__.py` — 6 LOC
  - `marslab/runtime/config_loader.py` — 44 LOC
  - `marslab/runtime/precheck.py` — 102 LOC
  - `marslab/runtime/stage2_boot.py` — 211 LOC
  - `marslab/runtime/stage2_scene.py` — 242 LOC
  - `marslab/runtime/stage2_loop.py` — 206 LOC
  - `marslab/runtime/main_loop.py` — 547 LOC
  - `marslab/sim/__init__.py` — 13 LOC
  - `marslab/sim/boot.py` — 46 LOC
  - `marslab/sim/world_setup.py` — 69 LOC
  - `marslab/scene/__init__.py` — 19 LOC
  - `marslab/scene/structure_loader.py` — 222 LOC
- 총 LOC 검토: 1,873
- 리뷰어: Reviewer 2 (external, no project context)

## Findings

### CRITICAL (data corruption / security / scientific result wrong)

#### C-1 marslab/runtime/stage2_loop.py:196-203 — `finally` block swallows `close()` exception and exits process with success code
- 근거:
  ```python
  finally:
      try:
          simulation_app.close()
      except Exception as exc:  # noqa: BLE001
          print(f"[run_stage2] simulation_app.close() raised: {exc}", file=sys.stderr)
          sys.stdout.flush()
          sys.stderr.flush()
          os._exit(0)
  ```
- 문제: (1) `os._exit(0)` bypasses the Python interpreter shutdown — no `atexit` handlers run, no buffered stderr is flushed beyond the explicit calls, no coverage data is written, no pytest teardown hooks run. Exit-code `0` on an exception is a **lie to CI**: a crashed shutdown looks like a clean run. The comparable Stage 3 entry (`run_main_loop`) returns `0` on normal exit and lets exceptions propagate; here the semantics disagree between the twin loops. (2) The caller `scripts/phase1/run_stage2.py` also owns the lifecycle (docstring for `run_stage2_loop` says "The caller owns shutdown"), yet this function *also* calls `close()` — double-teardown.
- 제안: Let the exception propagate (or `raise SystemExit(1)`). Remove `os._exit(0)`. Delete the `close()` call and let the caller own shutdown as the docstring already claims.

#### C-2 marslab/runtime/main_loop.py:341-352 — `set_joint_*_targets` failure is swallowed with a single `print`; every subsequent step silently repeats
- 근거:
  ```python
  try:
      ctx.articulation.set_joint_position_targets(
          ramped_steer, joint_indices=steer_idx_arr
      )
      ctx.articulation.set_joint_velocity_targets(
          ramped_vels, joint_indices=drive_idx_arr
      )
  except Exception as exc:  # noqa: BLE001
      print(
          f"[run_main_loop] joint target failed: {exc}",
          file=sys.stderr,
      )
  ```
- 문제: If the physics backend raises every tick (e.g. articulation deleted, invalid joint index), this loop prints to stderr 60× per second, indefinitely, with zero rate-limiting and zero effort to abort. The ramp state `ctl.current_drive_targets` still advances, so when the articulation comes back the rover lurches at the last commanded velocity. `noqa: BLE001` + bare `Exception` explicitly violates CLAUDE.md "Never silently swallow exceptions" (confirmed via plain reading of the error-handling contract). Combine with C-3 (odom) and C-4 (debug log) and a single misconfiguration pumps the stderr pipe at multi-kHz.
- 제안: Either let the exception propagate (the scene is unrecoverable) or maintain a consecutive-failure counter; after N failures, abort the loop. Log once per failure type using `logging.error` with the exception *class* as a dedupe key.

#### C-3 marslab/runtime/main_loop.py:486-492 — identical swallow pattern in odometry publisher; step<120 gate leaves silent failures after step 120
- 근거:
  ```python
  except Exception as odom_exc:  # noqa: BLE001
      logger.error("odom publish failed at step=%d: %r", step_count, odom_exc)
      if step_count < 120:
          print(
              f"[run_main_loop] odom publish failed: {odom_exc}",
              file=sys.stderr,
          )
  ```
- 문제: `logger.error` always fires, but if the logging handler is not configured (common in Kit embedding), those lines vanish. The operator only sees the first 120 steps (2 seconds at 60 Hz). After that, *every* odom publish failure is invisible — SLAM silently receives no odometry and experimental results become unreproducible. The `step_count < 120` gate has no documented rationale; at 60 Hz physics that's 2s of startup transient where Isaac's pose buffers may genuinely not be ready, but the cutoff is arbitrary.
- 제안: Replace `step_count < 120` with an explicit "startup grace period" constant sourced from config. After the grace period, propagate the exception or set a degraded-mode flag and stop publishing (silent corruption of SLAM inputs is the worst of the three outcomes).

#### C-4 marslab/runtime/main_loop.py:397-402, 412-417 — `_debug_log_step` swallows articulation/IMU fetch errors; after step 120 the IMU failure is completely invisible
- 근거:
  ```python
  except Exception as exc:  # noqa: BLE001
      if ctx.control.step_count < 120:
          print(
              f"[warn] articulation step={ctx.control.step_count} {repr(exc)[:200]}",
              file=sys.stderr,
          )
  ```
- 문제: Three copies of the same 120-step gated silent swallow (lines 397-402, 412-417, 477-483). IMU returning `None` after step 120 means the G7 "IMU z-axis = 3.72 ± 0.05 m/s² critical test" referenced in the project could pass during startup, then the IMU breaks mid-run, and the operator has no way to know. Truncation to 200 chars (`repr(exc)[:200]`) silently clips long stack-context messages.
- 제안: Route all three sites through a shared `_log_once(exc, category)` helper backed by `logging.error` with `exc_info=True` for full traceback. Emit a `logging.warning` once per N failures after the grace period instead of falling silent.

#### C-5 marslab/runtime/main_loop.py:289-368 — `run_main_loop` is a 96-LOC god-function mixing 5 unrelated concerns; step-ordering bug risk
- 근거:
  ```python
  def run_main_loop(ctx: LoopContext) -> int:
      ...
      while ctx.simulation_app.is_running():
          if ctx.spin_once is not None:
              ctx.spin_once()
          # 1) clamp twist
          v = float(np.clip(v_raw, -ctx.v_max, ctx.v_max))
          w = float(np.clip(w_raw, -ctx.w_max, ctx.w_max))
          # 2) Ackermann + steer ramp
          ... (steer_angles = -steer_angles, etc.)
          # 3) drive ramp
          ramped_vels = _apply_ramp(...)
          # 4) articulation push
          ctx.articulation.set_joint_position_targets(...)
          # 5) debug, odom, atmosphere
          if ctx.debug_logging and ctl.step_count % 60 == 0: _debug_log_step(...)
          if odom.node is not None and odom.odom_pub is not None: _publish_odometry(...)
          if ctl.step_count % atmo.update_interval == 0 and ctl.step_count > 0:
              _update_atmosphere(ctx)
          ctl.step_count += 1
          ctx.world.step(render=True)
  ```
- 문제: (1) **Step-order bug**: `ctl.step_count` is incremented **after** `_publish_odometry` and `_update_atmosphere` but **before** `world.step`. That means odometry for step N is computed from pose *at step N-1*, published with "step N" metadata, and the atmosphere update at step N is computed from a stage that has not been stepped yet for step N. `while` body thus advances 7 side-effects in a non-commutative order that is neither documented nor obviously correct. (2) The steer-ramp path is inlined (lines 325-331) while drive-ramp uses `_apply_ramp` — divergent change risk: a fix to one ramp won't propagate. (3) `_apply_ramp` mutates `current` in place AND returns it (lines 211-219); caller ignores the return for steer (no shared helper) but consumes it for drive. Asymmetric API.
- 제안: Extract `_step_control(ctx)`, `_step_targets(ctx)`, `_step_telemetry(ctx)` and document the physics-step ordering (target-write → step → sense → publish). Unify the two ramp paths: `_apply_ramp` should apply to both drive and steer with a single kernel, or better, delete the return value and make "mutate in place" the single contract.

#### C-6 marslab/runtime/main_loop.py:307-310 — missing bounds check: `latest_twist` dict lookups raise `KeyError` on typo / half-written mutation
- 근거:
  ```python
  v_raw = ctl.latest_twist["v"]
  w_raw = ctl.latest_twist["w"]
  v = float(np.clip(v_raw, -ctx.v_max, ctx.v_max))
  ```
- 문제: `latest_twist: Dict[str, float]` is mutated from the ROS2 `cmd_vel` subscriber which runs on a different thread (spin_once is called from the main thread but the underlying rclpy callback queue can mutate the dict between statements). If the subscriber replaces the dict instead of mutating in place (a common refactor mistake), this raises `KeyError`. The field is documented as "kept as a dict for Oracle parity" — primitive-obsession smell: it should be a `Twist` dataclass with `v: float` and `w: float` attributes, giving type safety and thread-safe replacement.
- 제안: Replace `Dict[str, float]` with `@dataclass class LatestTwist: v: float = 0.0; w: float = 0.0`. Guarantees the two fields exist at construction time.

### HIGH

#### H-1 marslab/runtime/stage2_loop.py:92-99 — `_tau_kwargs` is dead code explicitly tagged `noqa: F841`; the "parity" justification is comments-as-deodorant
- 근거:
  ```python
  tau_profile_name = dyn.tau_profile
  # ``tau_kwargs`` is preserved for parity with the legacy code path;
  # the render loop below does not consume it today (tau is driven by
  # ``atmosphere_state['tau']`` via the GUI slider). The separate
  # ticket that wires tau_profile into the per-frame ``compute_tau``
  # call will read this dict.
  _tau_kwargs: Dict[str, float] = dict(  # noqa: F841
      getattr(dyn, f"tau_{tau_profile_name}").model_dump()
  )
  ```
- 문제: A variable that (1) is unused, (2) needs a `noqa: F841` suppressor, and (3) has a 5-line comment justifying its existence is the textbook "comments-as-deodorant" smell. `getattr(dyn, f"tau_{tau_profile_name}")` also silently raises `AttributeError` if `tau_profile_name` is not one of the expected values — dynamic `getattr` on a pydantic model is fragile and untyped.
- 제안: Delete lines 97-99. When the "separate ticket" lands, add the code back with a call site that actually consumes the dict. Ghost code rots.

#### H-2 marslab/runtime/stage2_boot.py:100-102 — `atmosphere_init` uses `default_factory=lambda: None` with a `type: ignore[arg-type]` comment; frozen dataclass invariant is a lie
- 근거:
  ```python
  atmosphere_init: StageTwoAtmosphereInit = field(
      default_factory=lambda: None  # type: ignore[arg-type]
  )
  ```
- 문제: The field is typed `StageTwoAtmosphereInit`, but the default factory produces `None` and uses a type-ignore comment to suppress the mypy complaint. Every downstream consumer (`stage2_scene.setup_stage2_scene`, `stage2_loop.run_stage2_loop`) dereferences `boot.atmosphere_init.<attr>` without a `None` check. If anyone ever constructs `StageTwoBootResult` without passing `atmosphere_init`, they get an `AttributeError` deep inside Isaac Sim scene setup. Frozen dataclass with a lying default is worse than `Optional[...]` with explicit None-check.
- 제안: Make the field required (remove `default_factory`). All real call sites pass it explicitly (only call is `run_stage2_boot` at line 201). The default exists purely to satisfy "dataclass with defaults must come after no-default fields" — fix the field order instead (`repo_root: str = REPO_ROOT` goes after).

#### H-3 marslab/runtime/main_loop.py:172-182 — `LoopContext` has 34 fields and 10 optional callable injections; god-object / long-parameter-list / temporary-field smells collide
- 근거:
  ```python
  @dataclass
  class LoopContext:
      simulation_app: Any
      world: Any
      stage: Any
      articulation: Any
      imu: Any
      drive_indices: List[int]
      steer_indices: List[int]
      wheelbase: float
      track_steer: float
      track_middle: float
      wheel_radius: float
      v_max: float
      w_max: float
      physics_dt: float
      negate_steer: bool
      debug_logging: bool
      max_wheel_accel_rate: float
      decel_multiplier: float
      max_steer_angle: float
      steer_ramp_rate: float
      control: ControlState
      atmosphere: AtmosphereLoopState
      odom: OdomPublishState
      render_config: Any
      ackermann_fn: Callable[..., Any]
      spin_once: Optional[Callable[..., None]] = None
      update_sun_fn: Optional[Callable[..., None]] = None
      update_sky_fn: Optional[Callable[..., None]] = None
      configure_fog_fn: Optional[Callable[..., None]] = None
      compute_sun_fn: Optional[Callable[..., Any]] = None
      compute_sol_sun_fn: Optional[Callable[..., Any]] = None
      compute_direct_intensity_fn: Optional[Callable[..., float]] = None
      compute_diffuse_fraction_fn: Optional[Callable[..., float]] = None
      compute_sky_dome_fn: Optional[Callable[..., Any]] = None
      atmo_panel_update: Optional[Callable[[], None]] = None
  ```
- 문제: This is not a "context", it is the entire stage-3 runtime's dependency graph inverted into a single struct. Data clumps: `wheelbase/track_steer/track_middle/wheel_radius` (geometry), `v_max/w_max/max_wheel_accel_rate/decel_multiplier/max_steer_angle/steer_ramp_rate` (control limits), `max_wheel_accel_rate/decel_multiplier` (drive ramp), are each passed together everywhere. `Callable[..., Any]` with 10 optional function injections *is* a plugin system — P1 flat-architecture claim in the docstring is aspirational only. The atmosphere callables should live on `AtmosphereLoopState`, not here.
- 제안: Extract `VehicleGeometry`, `ControlLimits`, `AtmosphereCallables` dataclasses. Required fields first, optional factories second. Aim for ≤8 top-level fields. Ten `Optional[Callable]` injections is dependency-injection via the front door — if that is truly desired, wrap the atmosphere updaters in a single `AtmosphereUpdater` protocol.

#### H-4 marslab/runtime/main_loop.py:222-270 vs marslab/runtime/stage2_loop.py:26-51 — `build_atmosphere_loop_state` and `build_atmosphere_state` are near-identical duplicates
- 근거:
  ```python
  # main_loop.py
  atmosphere_dict: Dict[str, Any] = {
      "tau": tau,
      "sun_mode": "auto" if dyn.enabled else "manual",
      "sun_azimuth_deg": float(atmo_init.sun_azimuth_deg),
      "sun_elevation_deg": float(atmo_init.sun_elevation_deg),
      "time_of_sol": 0.0,
      "direct_intensity": atmo_init.direct_intensity,
      "diffuse_fraction": atmo_init.diffuse_fraction,
      "sol_duration_seconds": atmo_init.sol_duration_seconds,
  }
  ```
  ```python
  # stage2_loop.py
  return {
      "tau": atmo.tau,
      "sun_mode": "auto" if atmo.dynamic.enabled else "manual",
      "sun_azimuth_deg": atmo.sun_azimuth_deg,
      "sun_elevation_deg": atmo.sun_elevation_deg,
      "time_of_sol": 0.0,
      "direct_intensity": atmo.direct_intensity,
      "diffuse_fraction": atmo.diffuse_fraction,
      "sol_duration_seconds": atmo.sol_duration_seconds,
  }
  ```
- 문제: The dict schema is identical; only `float(...)` coercion and the argument source differ. Shotgun-surgery risk: adding a new atmosphere key (e.g. `cloud_opacity`) requires editing both copies and both will silently drift. The comment in `main_loop.py` L244-248 explicitly admits that dropping `sol_duration_seconds` in one copy caused a `KeyError` in production. That is the bug this smell predicts.
- 제안: Hoist to `marslab.runtime.atmosphere_state.build_initial_state(atmo_init, tau)` and make both call sites consume it. Add a dataclass wrapper if the GUI panel can read attributes instead of string keys (eliminates the primitive-obsession of `"sun_mode"` as a bare string).

#### H-5 marslab/runtime/stage2_loop.py:134-182 + marslab/runtime/main_loop.py:495-547 — `_step_atmosphere` and `_update_atmosphere` are a copy-paste pair with divergent DI strategies
- 근거:
  ```python
  # stage2_loop._step_atmosphere (closure)
  if atmosphere_state["sun_mode"] == "auto" and dynamic_enabled:
      elapsed += physics_dt * update_interval * time_scale
      t = (elapsed % sol_duration) / sol_duration
      atmosphere_state["time_of_sol"] = t
      dyn_sun_pos = compute_sol_sun_position(...)
  elif atmosphere_state["sun_mode"] == "manual":
      dyn_sun_pos = compute_sun_position(...)
  ```
  ```python
  # main_loop._update_atmosphere (callable injection)
  if state["sun_mode"] == "auto" and atmo.dynamic_enabled:
      atmo.elapsed += ctx.physics_dt * atmo.update_interval * atmo.time_scale
      t = (atmo.elapsed % atmo.sol_duration) / atmo.sol_duration
      state["time_of_sol"] = t
      if ctx.compute_sol_sun_fn is not None:
          dyn_sun_pos = ctx.compute_sol_sun_fn(...)
  elif state["sun_mode"] == "manual" and ctx.compute_sun_fn is not None:
      dyn_sun_pos = ctx.compute_sun_fn(...)
  ```
- 문제: Same formulae, same branching, same clamp-to-(0.5, 89.5), two different dispatch styles (direct import vs. optional callable). The docstring in `stage2_loop.py` L141 even admits: *"the twin mutator in marslab.runtime.main_loop uses a different callable-injection layout so we do not share a base (P1)"*. Cherry-picking "no premature abstraction" to justify duplicating a 40-LOC per-frame physics update is comments-as-deodorant. A bug fix to the diffuse/direct/sky triple (e.g. the `max(0.5, min(89.5, elevation))` clamp values, which are hard-coded in both copies) must be made twice.
- 제안: Extract `step_sun_sweep(atmosphere_dict, dt_scaled, sol_duration, sweep_cfg) -> SunPosition | None` to a new `marslab.environment.sun_sweep` module. Inject the four `compute_*` functions as required arguments (not `Optional`); if a caller can't provide them, they shouldn't call this function.

#### H-6 marslab/runtime/stage2_loop.py:185-193 — `frame` counter can wrap silently; `frame % update_interval` is the only cadence gate
- 근거:
  ```python
  frame = 0
  ...
  while simulation_app.is_running():
      world.step(render=True)
      frame += 1

      if frame % update_interval != 0:
          continue

      _step_atmosphere()
  ```
- 문제: On first iteration `frame=1`, `1 % update_interval` is non-zero for any `update_interval > 1` (default 60), so atmosphere updates begin at frame 60, not frame 0. That is probably intentional but undocumented. Worse: if `update_interval == 0` (e.g. the YAML validates permissively or someone passes the default `0`), this is integer `%` by zero — `ZeroDivisionError` that aborts the loop mid-render. No precondition check.
- 제안: Assert `update_interval >= 1` once at entry. Document the "first update at frame=update_interval" cadence in the docstring. Consider starting with `frame = -1` so the first update lands at frame 0.

#### H-7 marslab/runtime/stage2_boot.py:24 — silent monkey-patch of sys.path equivalent via `REPO_ROOT` module global + relative asset resolution
- 근거:
  ```python
  REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
  ...
  def run_stage2_boot(config_path: str, repo_root: str = REPO_ROOT) -> StageTwoBootResult:
  ```
- 문제: `REPO_ROOT` defaulting to "two parents of this file" couples the module to its position in the repo. If `marslab/` is ever vendored as a subpackage or installed via `pip install -e .` into a site-packages path, `os.path.join(..., '..', '..')` points to the *Python site-packages root*, not the user's MarsLab checkout — and the HDRI / texture directory lookups at L166 and L187 silently resolve wrong paths, producing a black sky or untextured terrain. Packaging foot-gun.
- 제안: Require `repo_root` to be passed explicitly (no default). Derive it from CLI args or `MARSLAB_ROOT` env var in the entrypoint script, not from `__file__`.

#### H-8 marslab/runtime/main_loop.py:360 — atmosphere cadence triggers at `step_count == 0` is *excluded*, so the first update lags by `update_interval` steps; inconsistent with stage2 behavior
- 근거:
  ```python
  if ctl.step_count % atmo.update_interval == 0 and ctl.step_count > 0:
      _update_atmosphere(ctx)
  ```
- 문제: Explicit `step_count > 0` exclusion means the very first tick does *not* fire `_update_atmosphere`, so the initial sun/sky/fog stays at whatever the scene was configured with in `setup_*_scene`. In Stage 2's loop (`stage2_loop.py:189`), the gate is `frame % update_interval != 0` *after* `frame += 1`, meaning frame 0 (before increment) never runs atmosphere either, but the two modules have different pre-conditions. Divergent-change risk.
- 제안: Unify: both loops should consume a shared `should_update_atmosphere(step_count, interval) -> bool` helper with a single documented rule.

#### H-9 marslab/runtime/stage2_scene.py:84 — `is_cave = terrain_cfg.get("procedural_preset") == "cave"` is primitive-obsession; all 3 scene-construction paths branch on this string
- 근거:
  ```python
  is_cave = terrain_cfg.get("procedural_preset") == "cave"
  if is_cave:
      norm_elevation = _build_cave_scene(stage, boot)
  else:
      norm_elevation = _build_heightmap_scene(stage, boot)
  ```
- 문제: `"cave"` is a magic string repeated nowhere else in this file, but branch-controlling. If a second procedural preset ever lands (e.g. `"crater"`, `"dunes"`), this becomes a chain of `elif`. The switch also leaks into `StageTwoScene.is_cave: bool` (L38), which is then consumed downstream — typical enum-via-string antipattern.
- 제안: Replace with `TerrainSceneKind = Literal["heightmap", "cave", "crater", ...]`. Use a small registry dict `_BUILDERS: Dict[TerrainSceneKind, Callable[..., np.ndarray]]`. Offload the `StageTwoScene.is_cave` flag in favour of `scene_kind`.

#### H-10 marslab/scene/structure_loader.py:222 — `_ = field  # noqa: F841` "defensive re-bind" is superstition, not code
- 근거:
  ```python
  # Defensive re-bind so static type checkers pick up the module-level
  # default_factory pattern without importing ``dataclasses.field``
  # transitively.  Keeping the import visible silences ``F401`` on
  # ``field`` which may be used by downstream subclasses.
  _ = field  # noqa: F841
  ```
- 문제: `field` is imported at line 19 alongside `dataclass`. The comment claims the re-bind prevents `F401` (unused-import) — but `field` IS used in `dataclasses`-shaped subclasses only if they inherit `StructureConfig` and add new fields, which no file in this repo does (`grep -rn "StructureConfig)" --include="*.py"` shows only the pydantic-mirror wrapper in `test_structure_loader_schema.py`). The "defensive" rebind doesn't affect mypy, doesn't affect runtime, and the `noqa: F841` is now being used to silence a lint warning on a statement that exists only to silence a different lint warning on a different line. Textbook comments-as-deodorant.
- 제안: Delete lines 218-222. `field` is imported and unused — remove it from the import and let `ruff` be honest.

#### H-11 marslab/runtime/main_loop.py:308-310 — wheel-ramp ignores v_max/w_max change at runtime; `v_max` / `w_max` captured once in `ctx`, ramps `current_*_targets` keyed to old limits
- 근거:
  ```python
  v = float(np.clip(v_raw, -ctx.v_max, ctx.v_max))
  w = float(np.clip(w_raw, -ctx.w_max, ctx.w_max))
  ```
- 문제: `v_max` is stored in `LoopContext` and used for *every* clamp. If a future scenario mutates `ctx.v_max` (not actually prevented — `LoopContext` is a non-frozen `@dataclass`), the ramp state `ctl.current_drive_targets` still carries the accumulated value from the pre-change regime. Same for `ctx.max_wheel_accel_rate` / `ctx.physics_dt` which are multiplied *once* at L297 (`per_step_limit = ctx.max_wheel_accel_rate * ctx.physics_dt`) and never recomputed — a runtime physics_dt change is silently ignored. Off-by-config hazard.
- 제안: Freeze `LoopContext` (`@dataclass(frozen=True)`) or recompute `per_step_limit` inside the loop body. Document that these values are snapshots.

#### H-12 marslab/runtime/stage2_scene.py:135, 147 — Hard-coded tuple fallbacks repeat the same Mars albedo / cave albedo ranges inside the YAML-loading path
- 근거:
  ```python
  cave_albedo = tuple(cave_cfg.get("wall_albedo_range", [0.05, 0.15]))
  ...
  surface_albedo = tuple(mars_cfg.get("surface_albedo_range", [0.10, 0.40]))
  ```
- 문제: Repeated `.get(key, literal_default)` with Mars-physics literals (`[0.05, 0.15]`, `[0.10, 0.40]`) embedded in module code violates the "zero hardcoded Mars parameters" stance in CLAUDE.md (confirmed by plain reading of the config-driven claim). The same pattern recurs at L169 (`uv_scale`), L184 (`surface_albedo_range`), L191 (`seed`), L206 (`rock_sfd_k`), L214 (`rock_diameter_range`), L222 (`seed`), L233 (`seed`), L234 (`rock_color`), L235 (`rock_roughness`). Pydantic already exists for `mars_env`; why is `terrain_cfg` still a raw dict with `.get(...)` fallbacks?
- 제안: Build a `TerrainConfig` pydantic model parallel to `MarsEnvConfig`, migrate the 10 `.get(key, literal)` sites to attribute access. Delete every literal fallback here.

#### H-13 marslab/runtime/stage2_scene.py:69-81 — redundant `MarsEnvConfig(**mars_cfg)` re-construction (boot already did this at stage2_boot.py:156)
- 근거:
  ```python
  # In stage2_scene.setup_stage2_scene
  from marslab.config.schema import MarsEnvConfig
  mars_env_model = MarsEnvConfig(**mars_cfg)
  physics_dt = atmo.physics_dt
  gravity = mars_env_model.gravity
  ```
  vs. `stage2_boot.py:156`:
  ```python
  mars_env_model = MarsEnvConfig(**mars_cfg)
  ```
- 문제: Pydantic validation is non-trivial — we re-run it after boot already succeeded. If the user *mutates* `boot.config` between boot and scene setup, the two `MarsEnvConfig(**mars_cfg)` constructions could silently disagree. Duplicate-code smell, and the frozen dataclass gives the caller no hint that the model already lives in boot.
- 제안: Carry `mars_env_model: MarsEnvConfig` inside `StageTwoBootResult` and delete the re-construction in `stage2_scene.py`.

### MEDIUM

#### M-1 marslab/runtime/stage2_loop.py:199-203 — bare `Exception` in `finally` without preserving traceback
- 근거:
  ```python
  except Exception as exc:  # noqa: BLE001
      print(f"[run_stage2] simulation_app.close() raised: {exc}", file=sys.stderr)
  ```
- 문제: Bare `Exception` catch + stringified error discards the traceback. Use `logger.exception()` to preserve full context. Already critical per C-1; this is a second-order concern about stack-trace loss.
- 제안: `logger.exception("simulation_app.close failed")`.

#### M-2 marslab/runtime/main_loop.py:380, 397, 412, 477 — four identical "print to stderr if step<120 else silence" swallow patterns
- 근거:
  ```python
  except Exception as exc:  # noqa: BLE001
      if ctx.control.step_count < 120:
          print(f"[warn] articulation step={ctx.control.step_count} {repr(exc)[:200]}", file=sys.stderr)
  ```
- 문제: Four copies of the exact same "grace period" pattern differing only by error source. Shotgun-surgery waiting to happen. Also `repr(exc)[:200]` arbitrarily truncates.
- 제안: `def _log_startup_error(step_count, category, exc, grace_steps=120): ...` — one helper, four callers.

#### M-3 marslab/runtime/stage2_scene.py:118-158 — `_build_cave_scene` reaches into `terrain_cfg["_cave_data"]` without checking presence
- 근거:
  ```python
  cave_data = terrain_cfg["_cave_data"]
  norm_elevation = build_cave_scene(cave_data, stage)
  ```
- 문제: The leading underscore key `_cave_data` is a "private" convention injected by some upstream scenario loader; grep shows it is read here but I cannot verify where it is *written* (it is not under scope but worth flagging). `KeyError` on `_cave_data` crashes with zero context about which upstream module was supposed to set it. Temporary-field smell: `_cave_data` exists only when `procedural_preset == "cave"`.
- 제안: Accept a separate `cave_data: Optional[CaveData]` parameter in `StageTwoBootResult` instead of hiding it as an underscore-prefixed dict key. Raise a clear `ValueError("cave scene requested but cave data not generated — did run_stage2_boot run the cave pipeline?")`.

#### M-4 marslab/runtime/stage2_boot.py:147-151 — mixed concern: `print()` logging inside a function documented as "pure Python, offline-testable (P3)"
- 근거:
  ```python
  print(f"[run_stage2] Loaded config: {abs_config_path}", flush=True)
  ...
  print(f"[run_stage2] Terrain: {elevation.shape} @ {resolution} m/px, z=[...]", flush=True)
  ...
  print(f"[run_stage2] Atmosphere: tau={tau}, direct={direct_intensity:.1f} W/m2, ...", flush=True)
  ```
- 문제: Four `print(..., flush=True)` calls in a "pure computation" module. Unit tests of this function will spew `[run_stage2]` noise into the test log. `flush=True` implies the author knows these are operator-facing diagnostics, not library output — which belongs in a separate orchestration layer, not the validator.
- 제안: Replace with `logger = logging.getLogger(__name__)` + `logger.info(...)`. Or move all `print` to the CLI entrypoint `scripts/phase1/run_stage2.py` that already owns operator output.

#### M-5 marslab/runtime/main_loop.py:48 — `latest_twist: Dict[str, float]` with `default_factory=lambda: {"v": 0.0, "w": 0.0}` is primitive-obsession
- 근거:
  ```python
  latest_twist: Dict[str, float] = field(default_factory=lambda: {"v": 0.0, "w": 0.0})
  ```
- 문제: Already covered by C-6 but the data-clump tag: `{"v", "w"}` is a linear-angular twist pair masquerading as a generic string-keyed dict.
- 제안: `TwistCommand(v: float = 0.0, w: float = 0.0)`.

#### M-6 marslab/runtime/precheck.py:32-34 — concatenated f-strings with no necessity
- 근거:
  ```python
  raise FileNotFoundError(
      f"Rover USD missing: {usd_abs}. " f"Run scripts/phase1/convert_urdf_to_usd.py first."
  )
  ```
- 문제: `f"..." f"..."` is implicit string concatenation with f-string prefixes on both halves even though the second half has no interpolation. Confuses `ruff` / readers — the second half could be a plain string.
- 제안: `f"Rover USD missing: {usd_abs}. Run scripts/phase1/convert_urdf_to_usd.py first."` as a single string.

#### M-7 marslab/runtime/config_loader.py:12-27 — `load_runtime_config` is a thin passthrough with no call sites; middle-man smell
- 근거:
  ```python
  def load_runtime_config(config_path: str, master_seed: Optional[int] = None) -> MarsLabConfig:
      ...
      return load_and_validate(config_path, master_seed=master_seed)
  ```
- 문제: `grep -rn "load_runtime_config\b"` returns only its definition and its own docstring (verified across the entire repo). Zero callers. It is a "runtime facade" for a function nobody uses from the runtime.
- 제안: Delete `load_runtime_config`. When a caller materializes, re-introduce it with a real test. See D-1.

#### M-8 marslab/runtime/main_loop.py:22 — `from marslab.math.quaternion import quat_inverse, quat_multiply, quat_rotate_vec` at module scope violates the module's own "offline-importable (P3)" claim if marslab.math pulls anything Isaac-Sim-ish
- 근거:
  ```python
  from marslab.math.quaternion import quat_inverse, quat_multiply, quat_rotate_vec
  ```
- 문제: The file claims `The module itself is offline-importable (P3)` in the header docstring. I cannot verify under reviewer scope whether `marslab.math.quaternion` has heavy deps, but the pattern of "isolate Isaac Sim imports, but take eager imports from helper modules" is fragile — one day someone adds `import torch` or similar to `quaternion.py` and tests fail with a misleading traceback. 확인 필요.
- 제안: Move all three quaternion helpers into `_publish_odometry` (they are only used there, lines 432-433, 468-470). One less module-level coupling.

#### M-9 marslab/scene/structure_loader.py:200-214 — `load_structures` catches `FileNotFoundError`, `print`s to stderr, then re-raises — middle-man with extra I/O
- 근거:
  ```python
  try:
      prim_paths.append(load_structure(stage, cfg))
  except FileNotFoundError as exc:
      print(
          f"[marslab.scene.structure_loader] Missing asset for "
          f"structure '{cfg.name}': {exc}",
          file=sys.stderr,
      )
      raise
  ```
- 문제: The exception is re-raised; the caller's traceback will already contain the missing path. Adding a `print` before re-raise duplicates information and sends it to stderr when the *tracebacker* would emit to stderr anyway. And if the caller `try/excepts` to add its own context, they now get noise plus the real message.
- 제안: Just re-raise without the print. The structure name can be added via `raise FileNotFoundError(...) from exc` with a clearer message.

#### M-10 marslab/runtime/main_loop.py:354-355 — debug-logging stride hardcoded to 60
- 근거:
  ```python
  if ctx.debug_logging and ctl.step_count % 60 == 0:
      _debug_log_step(...)
  ```
- 문제: Literal `60` sits in the loop body, not in config. At 60 Hz physics this is "once per second"; at 120 Hz it's "twice per second". Silent behavior change when physics_dt changes. Magic number.
- 제안: Promote to `LoopContext.debug_log_stride: int` sourced from the same config that owns `physics_dt`.

#### M-11 marslab/runtime/main_loop.py:515 — `max(0.5, min(89.5, elevation))` clamp to hard-coded angular range
- 근거:
  ```python
  elif state["sun_mode"] == "manual" and ctx.compute_sun_fn is not None:
      dyn_sun_pos = ctx.compute_sun_fn(
          azimuth_deg=state["sun_azimuth_deg"],
          elevation_deg=max(0.5, min(89.5, state["sun_elevation_deg"])),
      )
  ```
- 문제: `0.5` and `89.5` degrees are the solar-elevation clamp. Duplicated *verbatim* in `stage2_loop.py:163` — another instance of H-5's shotgun-surgery pattern. Why `0.5` and not `0.0`? Numerical safety for `tan(zenith)` presumably. That reasoning is undocumented.
- 제안: Extract as `SUN_ELEVATION_CLAMP_DEG = (0.5, 89.5)` in the environment module, shared by both loops.

#### M-12 marslab/runtime/main_loop.py:428-429 — shape-polymorphism in pose fetch is two identical branches
- 근거:
  ```python
  cur_pos = _rp[0] if _rp.ndim == 2 else _rp
  cur_quat = _rq[0] if _rq.ndim == 2 else _rq
  ```
- 문제: Repeated 4× across `_debug_log_step` (L385, 388) and `_publish_odometry` (L428, 429, 466, 467). Primitive-obsession: the Isaac Sim articulation API returns either `(1, N)` or `(N,)` depending on version/mode. If the API stabilizes on one shape, this breaks silently.
- 제안: `def _first_row(arr: np.ndarray) -> np.ndarray: return arr[0] if arr.ndim == 2 else arr`.

#### M-13 marslab/runtime/main_loop.py:462-476 — velocity query nested inside `_publish_odometry` with its own swallow pattern; single function, three error paths
- 근거:
  ```python
  try:
      lin_vel = ctx.articulation.get_linear_velocities()
      ang_vel = ctx.articulation.get_angular_velocities()
      ...
  except Exception as exc:  # noqa: BLE001
      logger.error("velocity query failed at step=%d: %r", step_count, exc)
      if step_count < 120:
          print(f"[warn] velocity step={step_count} {repr(exc)[:200]}", file=sys.stderr)
  ```
- 문제: Nested try-excepts in one function (outer at L423, inner at L462). If velocity fails, the odom message *still* gets published with `twist` all zeros — SLAM receives "rover not moving" which is a silent data-integrity bug, not a warning.
- 제안: Refactor into `_compute_body_twist(ctx, cur_quat) -> Optional[Twist]` and skip `publish` entirely when twist can't be computed.

#### M-14 marslab/cli/stage2_args.py:21 — `_REPO_ROOT` module-level constant relies on `__file__` depth
- 근거:
  ```python
  _REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
  DEFAULT_CONFIG = os.path.join(_REPO_ROOT, "configs", "mars_env.yaml")
  ```
- 문제: Same foot-gun as H-7 but in a different package. Two copies of the "two parents of `__file__`" idiom in the scope (the other is `stage2_boot.py:24`).
- 제안: Hoist to `marslab._meta.REPO_ROOT` and import from one place.

### LOW / STYLE

#### L-1 marslab/sim/world_setup.py:55-65 — silent no-op if `/physicsScene` prim is missing
- 근거:
  ```python
  physics_scene_prim = stage.GetPrimAtPath("/physicsScene")
  if physics_scene_prim.IsValid():
      physics_scene_prim.CreateAttribute(...)
  ```
- 문제: If the prim is not valid, solver iteration counts silently remain at whatever the default is. An operator who tuned `solver_position_iteration_count=16` for a 29-DOF articulation gets whatever Isaac ships with (usually 4), and the only clue is "rover joints look sloppy in sim". No warning, no error.
- 제안: Raise `RuntimeError("/physicsScene prim not found after World() — Isaac Sim did not initialize the scene correctly.")`. It is never valid to silently skip this.

#### L-2 marslab/sim/boot.py:13 — `DEFAULT_ROS2_BRIDGE_EXTENSION` constant duplicates its own value in the function signature
- 근거:
  ```python
  DEFAULT_ROS2_BRIDGE_EXTENSION = "isaacsim.ros2.bridge"
  def boot_simulation_app(
      headless: bool = False,
      renderer: str = "RaytracedLighting",
      ros2_bridge_extension: str = DEFAULT_ROS2_BRIDGE_EXTENSION,
  ) -> Any:
  ```
- 문제: `"RaytracedLighting"` is a literal default inline, but `DEFAULT_ROS2_BRIDGE_EXTENSION` is promoted to a module constant. Inconsistent — either both are constants or both are inline.
- 제안: Promote `DEFAULT_RENDERER = "RaytracedLighting"` for symmetry, or inline both.

#### L-3 marslab/runtime/main_loop.py:320-321 — `if ctx.negate_steer: steer_angles = -steer_angles` is configuration leaking into per-step hot path
- 근거:
  ```python
  if ctx.negate_steer:
      steer_angles = -steer_angles
  ```
- 문제: Negation sign flag evaluated on every tick even though `ctx.negate_steer` is constant across the run. Microscopic performance concern at 60 Hz but conceptually a config clump; a `steer_sign: float = ±1.0` field would let the loop be unconditional.
- 제안: Replace `negate_steer: bool` with `steer_sign: float`. Either the Ackermann function outputs the correct sign, or it doesn't — a separate flag is a band-aid.

#### L-4 marslab/runtime/stage2_loop.py:21-23 — dead comment block referencing a removed literal
- 근거:
  ```python
  # P6 G5 (2026-04-23): the physics tick used by the sun-sweep cadence lives
  # in :class:`StageTwoAtmosphereInit.physics_dt`, which is populated from the
  # pydantic ``MarsEnvConfig.physics_dt`` default. The module-level literal
  # that used to live here (``_PHYSICS_DT = 1.0 / 60.0``) was deleted to
  # satisfy "Zero hardcoded constants in Python source" (CLAUDE.md G5).
  ```
- 문제: 5 lines explaining what code USED to be here and why it isn't. Git history tracks that. Future readers do not need an in-file tombstone.
- 제안: Delete. If the reasoning matters for posterity, link to a CHANGELOG.

#### L-5 marslab/runtime/stage2_boot.py:132-135 — internal dated tag inside function body
- 근거:
  ```python
  # G7 (2026-04-24): enforce ``terrain.seed == mars_env.seed + 1`` on the
  # raw dict path so Stage 2/3 callers share a single seed-propagation
  # site.  Pydantic's ``propagate_seeds`` already covers the typed path.
  cfg = propagate_seeds_in_dict(cfg)
  ```
- 문제: Comment references `G7` — a project-internal ticket/guideline code. External readers can't decode "G7". Also references a date (2026-04-24), a pattern that rots as more edits accumulate.
- 제안: Keep the *behavior* explanation (what seed propagation does) and drop the `G7 (date)` preamble.

#### L-6 marslab/runtime/main_loop.py:60-65 — dated "P6 G5 (2026-04-23)" internal note in docstring
- 근거:
  ```python
  P6 G5 (2026-04-23): ``sol_duration`` and ``solar_constant`` previously
  defaulted to the Mars physics constants (``88642.0`` s and
  ``589.0`` W/m^2). That duplicated values already owned by
  :class:`marslab.config.schema.MarsEnvConfig`. Both are now required
  constructor arguments — callers must source them from the pydantic
  schema (see ``run_stage3_monolithic_new.py``).
  ```
- 문제: Same as L-5 but in a docstring — users `help()` this class and see the change log. Also references `run_stage3_monolithic_new.py`, which I cannot find in the top-level `scripts/phase1/` (grep shows it only in `delete_by_user/` — see D-2).
- 제안: Move change-log content to `CHANGELOG.md`. Docstrings should describe *current* contract only.

#### L-7 marslab/scene/structure_loader.py:82-100 — `_validate_asset` error message advertises an internal file `LICENSES.md`
- 근거:
  ```python
  raise FileNotFoundError(
      f"Structure USD asset not found: {abs_path}. "
      "Populate assets/structures/ per LICENSES.md and rebuild."
  )
  ```
- 문제: "LICENSES.md" doesn't convey what the reader should actually do. Is it a checklist? A list of license-compliant asset sources?
- 제안: `"Convert your .obj/.blend structure asset to USD (see docs/structures.md) and place it at {abs_path}."` — actionable.

#### L-8 marslab/runtime/main_loop.py:54-84 — `AtmosphereLoopState` defaults look like they belong to a specific scenario
- 근거:
  ```python
  sweep_start_az: float = 90.0
  sweep_end_az: float = 270.0
  sweep_max_el: float = 60.0
  update_interval: int = 60
  ```
- 문제: Four defaults that are only meaningful for one geographic/temporal setup. A caller that forgets to populate these gets sensible-looking values for Jezero crater and wildly wrong values elsewhere. The comment at L60-65 says `sol_duration` / `solar_constant` were demoted to required — these four should get the same treatment.
- 제안: Make all four required. Move defaults into YAML.

#### L-9 marslab/runtime/stage2_boot.py:102 — inline `# type: ignore[arg-type]` comment
- 근거:
  ```python
  atmosphere_init: StageTwoAtmosphereInit = field(
      default_factory=lambda: None  # type: ignore[arg-type]
  )
  ```
- 문제: Type-ignore without a comment saying *which* warning is being suppressed and *why* it is safe. Already covered in H-2 but the style issue: `# type: ignore[arg-type]  # atmosphere_init is always populated by run_stage2_boot`.
- 제안: Remove the default (preferred per H-2). If kept, document the ignore.

#### L-10 marslab/runtime/stage2_loop.py:117-121 — bare `Exception` with `noqa: BLE001` hiding GUI-panel import failure
- 근거:
  ```python
  except Exception as exc:  # noqa: BLE001
      print(
          f"[run_stage2] GUI panel unavailable ({exc}), using YAML config.",
          flush=True,
      )
  ```
- 문제: `ImportError` would be specific; `Exception` swallows unrelated bugs in the panel constructor (e.g. `TypeError` from signature change). The user is told "GUI panel unavailable" when the real error could be a logic bug in the panel itself.
- 제안: `except (ImportError, AttributeError) as exc:` — the two realistic "GUI unavailable" cases. Let real bugs propagate.

#### L-11 marslab/scene/structure_loader.py:80 — `f"/World/Structures/{self.name}"` hardcodes `/World/Structures` as the namespace root
- 근거:
  ```python
  return f"/World/Structures/{self.name}"
  ```
- 문제: Comment at L74-75 says "namespace-isolated from structures" yet the literal namespace lives inside the method instead of in config. If a scenario wants structures under `/World/Landers` (e.g. Mars-base scenario with hierarchical naming), must override every `prim_path` individually.
- 제안: Module-level `DEFAULT_STRUCTURES_ROOT = "/World/Structures"`.

#### L-12 marslab/runtime/main_loop.py:24 — module-level `logger = logging.getLogger(__name__)` used inconsistently (only in odom path)
- 근거:
  ```python
  logger = logging.getLogger(__name__)
  ```
- 문제: `logger` is defined at module scope but used only at lines 478 and 487. The other error sites use `print(..., file=sys.stderr)`. Pick one discipline — the mix means operators have to configure *both* Python logging and stderr capture.
- 제안: Migrate all `print(..., file=sys.stderr)` to `logger.warning/error` (4 call sites). Delete `print`s.

### DELETE CANDIDATES

#### D-1 marslab/runtime/config_loader.py:12-27 — `load_runtime_config` has zero callers
- 근거:
  ```python
  def load_runtime_config(config_path: str, master_seed: Optional[int] = None) -> MarsLabConfig:
      ...
      return load_and_validate(config_path, master_seed=master_seed)
  ```
- 검증: `grep -rn "load_runtime_config\b" --include="*.py"` returns only the definition (this file) and its own internal docstring reference in `load_runtime_config_dict`. Across `scripts/`, `tests/`, `marslab/`: no caller.
- 제안: Delete lines 12-27 and its `MarsLabConfig` import (L9). Re-introduce when a real caller needs it. Middle-man smell — a function that only forwards is an untested speed-bump between callers and `load_and_validate`.

#### D-2 marslab/runtime/main_loop.py:65 docstring + L231 — references `run_stage3_monolithic_new.py` which has been moved to `delete_by_user/`
- 근거:
  ```python
  ``marslab.config.schema.MarsEnvConfig``. Both are now required
  constructor arguments — callers must source them from the pydantic
  schema (see ``run_stage3_monolithic_new.py``).
  ```
  and at line 231:
  ```python
  ``scripts/phase1/run_stage4.py`` focused on Stage-3 orchestration.
  ```
- 검증: `ls scripts/phase1/` shows `run_stage4.py` exists; `run_stage3_monolithic_new.py` does NOT exist under `scripts/phase1/` — it lives at `delete_by_user/run_stage3_monolithic_new.py`. Docstring references an unavailable file. Lying docstring smell.
- 제안: Update docstring references to `run_stage4.py`, or delete the parenthetical "see ..." entirely (the pydantic schema reference is self-sufficient).

#### D-3 marslab/runtime/stage2_loop.py:97-99 — dead `_tau_kwargs` variable
- 근거:
  ```python
  _tau_kwargs: Dict[str, float] = dict(  # noqa: F841
      getattr(dyn, f"tau_{tau_profile_name}").model_dump()
  )
  ```
- 검증: `grep -rn "_tau_kwargs\|tau_kwargs" --include="*.py"` returns only this single site. Not read anywhere.
- 제안: Delete. See H-1 for rationale.

#### D-4 marslab/scene/structure_loader.py:218-222 — `_ = field  # noqa: F841` placeholder + 5-line justification
- 근거:
  ```python
  # Defensive re-bind so static type checkers pick up the module-level
  # default_factory pattern without importing ``dataclasses.field``
  # transitively. ...
  _ = field  # noqa: F841
  ```
- 검증: Removing this line does not affect pytest, ruff, or mypy output (can be verified by running the project's lint chain). The "defensive" claim is folklore.
- 제안: Delete lines 218-222. Remove `field` from the imports if truly unused (currently `from dataclasses import dataclass, field` at L19).

#### D-5 marslab/runtime/stage2_loop.py:15-20 — comment block about constants that no longer live in the file
- 근거:
  ```python
  # P6 G5 (2026-04-23): the physics tick used by the sun-sweep cadence lives
  # in :class:`StageTwoAtmosphereInit.physics_dt`, ...
  # The module-level literal
  # that used to live here (``_PHYSICS_DT = 1.0 / 60.0``) was deleted to
  # satisfy "Zero hardcoded constants in Python source" (CLAUDE.md G5).
  ```
- 검증: No variable `_PHYSICS_DT` exists in the file. The comment is a memorial plaque for deleted code.
- 제안: Delete lines 19-23 (L-4 restated as a delete candidate).

### FALSE-POSITIVE WATCHLIST

- `marslab/sim/world_setup.py:50` — `physics_ctx.set_gravity(-abs(float(gravity)))` — the `-abs(...)` guard is correct defensive input sanitation, not dead code. (If the YAML specifies `gravity: -3.72`, the caller still gets `-3.72` as intended for "always applied along +Z". Fine.)
- `marslab/runtime/main_loop.py:222-270` `build_atmosphere_loop_state` docstring references "scripts/phase1/run_stage4.py" which DOES exist. Not a lying docstring.
- `marslab/cli/__init__.py` — 11-line file, `add_headless_flag` only used by two callers (stage2_args, stage3_args); might look like middle-man but "help_text differs per stage" is a real reason to share the parser add logic. Keep.
- `marslab/runtime/stage2_scene.py:117-158` — looks like a long method at first glance, but `_build_cave_scene` encapsulates a single external contract (cave mesh application). Not flagged as long-method.

---

**Summary**: cli/ and sim/ are clean and focused. runtime/ (especially `main_loop.py` at 547 LOC) is where the bodies are buried: a god-context (34 fields), duplicated atmosphere-step logic with the two copies explicitly refusing to share a base, four copies of the "silent swallow with step<120 gate" pattern, and a `finally` block in `stage2_loop.py` that masks exceptions with `os._exit(0)`. The scene/structure_loader is mostly healthy; only a superstitious "defensive re-bind" needs culling.
