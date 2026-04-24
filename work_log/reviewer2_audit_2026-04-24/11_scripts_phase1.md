# Reviewer 2 — scripts/phase1/ audit

Scope: 4 files, 2,202 lines total.

| File | Lines | Assessment |
|------|------:|-----------|
| `run_stage2.py` | 57 | Acceptable thin CLI shim. |
| `run_stage3_monolithic.py` | 1,495 | **REJECT. Delete.** |
| `run_stage4.py` | 356 | Substantive. Needs cleanup. |
| `convert_urdf_to_usd.py` | 294 | Brittle but tolerable. Several concrete issues. |

My position as an external reviewer: **`run_stage3_monolithic.py` would not pass code review in any team I've ever been on.** A 1,239-line `main()` is not a file, it is a refusal to refactor. The in-tree justifications for keeping it ("Oracle", "diff=0 policy", "frozen md5", "monolithic twin") have no weight outside this project. An external engineer inheriting this repo sees exactly one thing: a nine-hundred-line procedural blob that re-implements code that lives one directory over in tested modules.

---

## 1. `run_stage3_monolithic.py` — REJECT

### 1.1 The 1,239-line `main()`

- File: `scripts/phase1/run_stage3_monolithic.py:253-1491`.
- The body of `main()` runs from line **253** to line **1491** — **1,239 lines**, CC ≈ 112. Everything is inline: config loading, terrain dispatch, Isaac Sim boot, gravity/solver setup, terrain mesh + materials + rocks, atmosphere, GUI panel, rover spawn, CoM/damping, rigid-body discovery, sensors, OmniGraph construction, DriveAPI setup, articulation init, PD gains, rclpy init, cmd_vel subscription, static TFs, manual odom publisher, **locally-defined quaternion helpers** inside `main()`, and the per-step control + odom + atmosphere loop.
- **Would I accept this in a PR?** Absolutely not. 1,239-line `main()` fails every review rubric I know — at Google it would bounce at the first review pass, at any OSS project with gatekeeping it is an automatic "please split this."
- **Can it be split safely?** Yes — it already has been. The entire logical content exists in `marslab.*`: `run_stage2_boot`, `setup_stage2_scene`, `spawn_rover`, `configure_drives`, `reinforce_pd_gains`, `spawn_sensors`, `build_sensor_graph`, `init_rclpy_side`, `run_main_loop`, `build_atmosphere_loop_state`. **`run_stage4.py` is that split and runs 356 lines.**

### 1.2 Massive duplication with `marslab/`

Every block listed below is **verbatim re-implementation** of code that exists as a tested module:

| Inline block | Lines | Exists in marslab as |
|---|---:|---|
| `clamp`, `clamp_twist` | `75-88` | *(nowhere — this logic is inline; `np.clip` is used elsewhere)* |
| `rpy_to_quat` | `91-108` | `marslab/math/quaternion.py:113` |
| `resolve_joint_indices` | `111-131` | `marslab/robots/rover.py:49` |
| `load_terrain_elevation` | `139-216` | `marslab/terrain/terrain_loader.py::load_scenario_terrain` |
| Atmosphere precompute | `286-305` | `marslab/runtime/stage2_boot.py:125-172` |
| Terrain mesh / cave / materials / rocks | `400-521` | `marslab/runtime/stage2_scene.py` |
| Atmosphere renderers (sun/sky/fog) | `523-536` | `stage2_scene.py`, `rendering/*` |
| Rover USD reference + spawn + CoM/damping | `595-670` | `marslab/robots/rover.py::spawn_rover` |
| Rigid-body discovery | `672-692` | same (`SpawnedRover.rigid_body_path`) |
| Sensor spawn (camera/lidar/imu/lidar2d) | `696-793` | `marslab/sensors/sensor_spawner.py::spawn_sensors` |
| OmniGraph construction (~100 lines) | `800-907` | `marslab/ros2_bridge/sensor_graph.py::build_sensor_graph` + `sensor_graph_builder.py` |
| Pre-reset USD DriveAPI | `918-1008` | `marslab/robots/drive_api_setup.py::configure_drives` |
| Articulation init + warmup + PD gains | `1013-1109` | `marslab/robots/drive_api_setup.py::reinforce_pd_gains` |
| rclpy init + cmd_vel + static TF + odom publisher | `1133-1213` | `marslab/ros2_bridge/rclpy_integration.py::init_rclpy_side` |
| `quat_inverse`/`quat_multiply`/`quat_rotate_vec` **locally nested in `main()`** | `1215-1240` | `marslab/math/quaternion.py:35-110` |
| Main control loop (ackermann + ramp + odom + atmo) | `1243-1467` | `marslab/runtime/main_loop.py::run_main_loop` |

The file imports exactly three marslab helpers (`load_scenario_config`, `resolve_spawn_pose`, `ackermann_command`) and then re-writes everything else inline.

### 1.3 Dead / lying code

- **`scripts/phase1/run_stage3_monolithic.py:55`**
  ```python
  import yaml  # noqa: F401  (kept for parity with run_stage1; unused directly)
  ```
  Imported-and-never-used. `# kept for parity` is an anti-reason. Delete.

- **`scripts/phase1/run_stage3_monolithic.py:1133-1137`** — dead initialization: `node`, `static_broadcaster` (marked `# noqa: F841`), `odom_tf_broadcaster`, `odom_pub`, `odom_init_quat_inv` are all set to `None`, then the real binding happens 100 lines later inside the `if not args.no_ros2` block, then `odom_init_quat_inv` is **shadowed unconditionally at line 1240** — so the initial `None` binding accomplishes nothing. Lying code.

- **`scripts/phase1/run_stage3_monolithic.py:761, 775`** — `lidar = LidarRtx(...)  # noqa: F841` and `lidar_2d = LidarRtx(...)  # noqa: F841`. The comment "handle kept alive for extension lifetime" is superstitious — nothing in this file keeps those names alive more than the next statement would. `lidar.initialize()` is called, then `lidar` is never referenced again. If there really is a GC / RAII concern it needs a comment citing the Isaac Sim version, not a `# noqa`.

- **`scripts/phase1/run_stage3_monolithic.py:1134`** — `static_broadcaster = StaticTransformBroadcaster(node)  # noqa: F841`. Same superstition — a local variable does not "keep alive" a ROS2 broadcaster any differently than a normal assignment.

- **`scripts/phase1/run_stage3_monolithic.py:1215-1238`** — `quat_inverse`, `quat_multiply`, `quat_rotate_vec` defined as **closures inside `main()`**. These are pure mathematical functions, they are duplicates of `marslab.math.quaternion.quat_*`, they cannot be unit tested, and defining them 1,500 lines into `main()` is actively hostile to whoever reads this file next.

- Docstring at lines `1-47`: the "Backbone" / "Inserted scene block" / "monolithic file exists because ... modular version ... silently abort Isaac Sim" narrative is exactly the kind of internal-term citation the audit brief told me to treat as deodorant. It is telling me *why* the author felt bad about the duplication, not *what the code does*. Modern external review: that goes into CHANGELOG/git history, not the file header.

### 1.4 Comment-as-documentation smells

- **`L8, L44, L55, L63, L71, L135, L401, L523, L591, L633, L673, L694, L795, L911, L1010, L1043, L1129, L1242`**: paragraph-long comments citing `run_stage1.py L253-309 verbatim`, `run_stage2.py L67-144`, `§ 7.X`, etc. These section numbers refer to an internal PLAN.md. An external reviewer cannot verify them — so from my point of view they are meaningless. The code reviews worse than the comments pretend it does: the claimed "verbatim" lines are not verifiable because the source files have since been modified.

- **`L45`**: "# Log capture — `2>&1 | tee` is shell redirection, NOT argparse." — this comment exists because the argparse wiring was so brittle someone actually tried to pass `2>&1 | tee ~/stage3.log` as a CLI argument. The fix the author reached for was L244 `args.config = args.config.strip()`. See 1.6.

### 1.5 Silent exception swallowing (G-policy violation)

- **`run_stage3_monolithic.py:1037, 1326, 1353, 1364, 1422, 1426, 1468, 1474, 1478, 1485`** — 10 `except Exception` clauses. Five end in bare `pass`:

  ```python
  except Exception:  # noqa: BLE001
      pass
  ```
  e.g. L1353-L1354 (debug log), L1364-L1365 (IMU read), L1422-L1423 (body-twist compute), L1474-L1475, L1478-L1479 (shutdown). Errors disappear. There is no per-failure rate limit, no logger hook. Compare to `marslab/runtime/main_loop.py:397-402` which at least emits a rate-limited `[warn]` with `repr(exc)[:200]`.

- **`run_stage3_monolithic.py:1488`**: `os._exit(0)` swallows the *success* exit if `simulation_app.close()` raises. Hiding an error behind a success exit is a real bug, not a comment-worthy one. See also 3.3.

### 1.6 CLI argparse

- **`run_stage3_monolithic.py:224-245`**: bare `argparse.ArgumentParser(description=__doc__)` where `__doc__` is ~47 lines including shell examples — that entire blob gets printed on `--help`.
- **`L244`**: `args.config = args.config.strip()`. This is a bandaid because something (shell pipeline, user paste) kept leaving trailing `\n` or `2>&1` debris on the arg. The correct fix is to not invite that in the first place; the comment pointing to "plan § 10.4" is not reassuring to me.
- No `--config` existence / readability check in parser. Check happens at line 320 (USD existence) but the YAML path is trusted blindly and handed to `load_scenario_config` which will throw somewhere downstream with worse diagnostics.
- `--no-ros2` (boolean), `--headless` (boolean): fine.
- No `--yes` or destructive-confirm flag. No `input()` calls. So at least there is no interactive-confirmation gap.

### 1.7 Path handling

- **`L57-61`** `sys.path.insert(0, REPO_ROOT)` — runtime sys.path manipulation for module resolution. Ugly but it's a script, forgivable.
- **`L259`** `config_path = os.path.abspath(args.config)` — no traversal protection, but it's a dev CLI so this is acceptable.
- **`L316-319`, `L439`, `L477`, `L503`, `L506`** — every asset-dir resolution goes `os.path.join(REPO_ROOT, relative)`. No validation that the joined path actually lives *under* REPO_ROOT. If a YAML file contained `texture_dir: /etc`, it would resolve and be used. Low severity — the YAMLs are trusted — but a one-line `os.path.commonpath(...)` check would cost nothing.

### 1.8 Correctness drift between inline math and `marslab/math/quaternion.py`

I compared line-by-line:

- `rpy_to_quat` (L91-108 vs `marslab/math/quaternion.py:113`): **mathematically identical.** No drift.
- `quat_inverse` (L1215 vs `quat_inverse` module L35): **identical formula.** But the inline version does **not** cast input via `np.asarray(q, dtype=np.float32)` and does **not** validate shape. The module version does both. So the inline version accepts malformed input silently, the module version raises `ValueError`. Drift in robustness.
- `quat_multiply` (L1219 vs module L57): **identical formula.** Same drift: module version shape-validates.
- `quat_rotate_vec` (L1233 vs module L87): **identical formula.** Same drift.

So not a numerical-correctness drift, but an input-validation drift — and of course if anyone ever changes the module version (e.g. handles a new quaternion shape) the inline copy silently lags forever.

### 1.9 Ackermann

L1293-L1296 calls `ackermann_command` imported from `marslab.robots.rover_control` — this is the one piece the author did de-duplicate. Good. But the surrounding per-step ramping (L1304-L1321) re-implements what `marslab/robots/rover_control.py::ramp_steer_angles` and `ramp_wheel_velocities` do (the marslab module is unit tested; the inline copy is not). So even here, half of it is duplicated.

### 1.10 Odometry

Inline at L1367-L1432 re-implements what `marslab/ros2_bridge/odometry_math.py::compute_odom_delta` + `world_twist_to_body` + `marslab/ros2_bridge/odometry_publisher.py` already do. The `try: ... except Exception: pass` at L1422 silently hides body-twist compute failures.

### 1.11 Logging / `print` spam

58 `print(...)` calls in one file. No use of `logging`. The `[run_stage3_mono]` prefix is hand-pasted 50+ times. Every print is `flush=True` because stdout buffering with Isaac Sim is broken and the author is whack-a-moling it. Move to a module-level logger and fix it once.

### 1.12 Type hints

`main() -> int` is annotated, good. But internal state is bare: `rover_poses_odom`, `cur_pos`, `cur_quat`, `delta_pos_world`, `delta_pos_odom`, `delta_quat`, `odom_tf`, `odom_msg` — all un-annotated. The three locally-nested quaternion helpers have `np.ndarray` annotations — good. The big `atmosphere_state: Dict[str, Any]` at L566 is a grab-bag dict — type hint exists but it's `Dict[str, Any]` which is not a real type hint, it's a placeholder.

### 1.13 Verdict on `run_stage3_monolithic.py`

**Delete this file.**

The justifications I can see in tests/comments for keeping it — `tests/unit/test_monolithic_new_uses_main_loop.py`, `tests/unit/test_monolithic_new_seed_propagation.py`, md5-pinning ("`beefa125...`"), "Oracle diff=0 policy" — are *internal* artefacts. Seven tests exist only to prove that this frozen file continues to frozen-exist. That is not engineering, it is an archive with CI permissions.

From outside: the project already has `run_stage4.py` doing the same job in 356 lines of ordinary orchestration, and all the underlying primitives are tested in `marslab/`. The correct move is:

1. Rename `run_stage4.py` to `run_stage3.py`.
2. Delete `run_stage3_monolithic.py`.
3. Delete the tests that exist purely to assert the Oracle's existence (see §6).
4. Update `README.md` lines 177-181 which still reference both `run_stage3_monolithic.py` and the already-deleted `run_stage3_monolithic_new.py`.

If the project team wants an "Oracle" for regression — diff against git history, or commit the last-known-good run's stdout as a golden log. Neither requires keeping a 1,500-line source file around.

---

## 2. `run_stage2.py` — ACCEPT

- `scripts/phase1/run_stage2.py`, 57 LOC. Actual thin CLI shim.
- Boots Isaac Sim only after running pure-Python prelude, then calls three marslab helpers. Clean P2 / P3 design.
- Minor:
  - `L21-26` `sys.path` insert — fine for a script.
  - `L42` `from isaacsim import SimulationApp  # noqa: E402` — the `noqa` is to keep flake8 quiet about module-level-import-not-at-top. Acceptable because Isaac Sim really does need to be launched before any `omni.*` resolves.
  - `L44-46` constructs `SimulationApp({"headless": bool(args.headless), "renderer": "RaytracedLighting"})`. Hard-coded `"RaytracedLighting"` — G1/G4 say both RT and path-tracing should be supported; that belongs in YAML, not here. Same complaint applies to `run_stage4.py:108` via `marslab/sim/boot.py` if the same hard-code is there.
  - `L13-14` docstring says "the original 421-LOC script was split ... Rollback path is `git log` before 2026-04-23" — internal history in the docstring. Move to CHANGELOG.

Accept with trivial cleanup.

---

## 3. `convert_urdf_to_usd.py` — ACCEPT WITH CONCERNS

- `scripts/phase1/convert_urdf_to_usd.py`, 294 LOC. Sanitizes NASA JPL m2020 URDF with regex then runs `URDFParseAndImportFile`.

### 3.1 Security: XML parsing

- There is **no XML parser at all**. The file treats the URDF as a **raw string** and applies `re.sub` / `re.findall` on it (L73-145).
- Upside: cannot be vulnerable to XXE / billion-laughs / external-DTD attacks — there's no XML engine to exploit.
- Downside: the sanitizer is pattern-fragile. For example `_DRIVE_JOINT_RE` at `L90-93` assumes joint tags are on single lines and that attribute order is stable. A minor whitespace change in the upstream URDF would silently skip the drive-widening pass — producing a rover that locks up on first wheel revolution and no error message. Would I recommend swapping to `defusedxml.ElementTree`? **Yes, for a production tool.** For a one-shot build script that runs once per rover version, the current approach is defensible — but `L120-124` does at least validate `'parent link="ground"'` absence post-sub, and `L131-138` validates exactly-one-root-link, which is decent defense-in-depth.

### 3.2 `os._exit` everywhere

- **`L234, L255, L266, L283, L351`** (stage4 too): multiple `os._exit(N)` calls, justified by "Isaac Sim 5.x shutdown path heap-corrupts after URDF import".
- **This is a legitimate workaround for a real Isaac Sim bug**, and the code documents it. However:
  - `os._exit(0)` **inside the try block (L283)** bypasses the `finally` at L284-290. The finally block is dead on the happy path. The author acknowledges this at L237-241 but leaves the finally there anyway. That is confusing — strip the finally, or explicitly comment "dead on success, runs only on sanitize_urdf-then-exception path."
  - `os._exit` does not flush Python-level file buffers that weren't explicitly `flush=True`'d. Everywhere in this file there are `sys.stdout.flush()` / `sys.stderr.flush()` calls before `os._exit` — defensive, correct.

### 3.3 `kit.close()` commented out

- **L228-231, L277-282**: `kit.close()` is commented out. The cargo-cult in-code documentation here is actively harmful — either delete the commented call or leave a one-line pointer ("see github issue #XXXX"). A commented-out `kit.close()` just invites the next developer to un-comment it and discover the heap corruption anew.

### 3.4 Temp-file race

- **`L141-144`**: `temp_path = source_path + ".isaac_tmp"` — predictable name, next to the source file. Not in `tempfile.mkstemp`, not unique, not `O_EXCL`. If two conversions ever run in parallel they stomp each other. For a single-user dev tool this is fine; for CI this is a latent bug. The comment at L17 says "the temp file lives in the same directory as the original so mesh references (./meshes/*.gltf) still resolve" — OK, fair, but that still allows `tempfile.NamedTemporaryFile(dir=os.path.dirname(source_path), suffix=".isaac_tmp", delete=False)` which fixes the race.

### 3.5 Regex DRIVE joint widening

- **L41** `_DRIVE_JOINT_NAMES` hard-codes 6 NASA joint names. G5 says no hardcoded constants; these belong in a YAML. Mild violation since the whole file is URDF-specific.
- **L99-100**: `re.sub(r'lower="-3\.14159"', 'lower="-1000000"', body)` — depends on the previous `_LIMIT_REPLACEMENTS` pass having landed those exact strings. Load-bearing order. The comment at L44 says so. Brittle but functional.

### 3.6 argparse

- L148-151: simple `--urdf` and `--usd` with defaults. No `--force`, no existence check on `--urdf` until L160. Path handling is fine (uses `os.path.abspath`). No `--yes`, no `input()`.
- **L169-171**: `os.remove(usd_path)` **unconditional** if the file exists — no `--force` prompt. For an asset-build script targeting `assets/robots/rover/m2020.usd` this is normal behaviour, but worth calling out: anyone passing `--usd ~/random/file.usd` gets it silently removed. A `--force` flag would be the idiomatic guard.

### 3.7 Isaac Sim API versioning

- The file talks to `omni.kit.commands.execute("URDFCreateImportConfig")` and `"URDFParseAndImportFile"` — these are the legacy URDF commands. The guidance in CLAUDE.md etc. prefers `omni.isaac.lab.sim.converters.UrdfConverter` for new code. This file predates or ignores that preference. Not my problem — but an external reviewer would flag it as "check which API version you're targeting."

---

## 4. `run_stage4.py` — MOSTLY ACCEPT

- `scripts/phase1/run_stage4.py`, 356 LOC. The actual decomposed Stage-3 runner.

### 4.1 The docstring lies

- **L1-32** docstring is a lecture on the "Oracle twin" and md5-pinning. Three lines of "what this script does" would suffice. `L26-27`: `Oracle (run_stage3_monolithic.py, md5 beefa12579dd43f3da27b1dae3c6f852) remains frozen; paper experiments run through this twin.` — that's a commit message, not a module docstring.

### 4.2 F401 / `noqa` cargo

- **L49-72**: 20 `# noqa: E402` comments + two `F401`: `propagate_seeds_in_dict` at L50 and `load_scenario_config` at L51.
- **L328**: `_ = (propagate_seeds_in_dict, AtmosphereLoopState, load_scenario_config)` — explicitly binds these names to silence linters. The comment says "Silence unused-import linters for names kept as F401 for test-text checks." So the imports exist purely so that a grep-based test (the one in `tests/unit/test_monolithic_new_*.py` that scans the file source for these symbol names) continues to pass.

That is test-driven dead code. I would:
- Delete the F401 imports.
- Delete the `_ = (...)` binding.
- Either delete the grep-based tests or rewrite them to import the module and check real module behavior.

### 4.3 Same GUI-panel-lifecycle dance

- **L211-234**: 24 lines of comment explaining why `AtmospherePanel` has to be built *after* `world.reset()`, citing `AttributeError: 'AtmospherePanel' object has no attribute '_az_slider'` and "Oracle parity." This is a brittle UI-lifecycle workaround where neither `world.reset()` nor `AtmospherePanel.__init__` provide hooks. The right fix is in `marslab/gui/atmosphere_panel.py` (build sliders lazily or gate on `widgets_ready` event), not here. This file papers over it with 5 fake `simulation_app.update()` calls.

### 4.4 Quaternion handling

- **L241-244**: `odom_init_quat = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)` — fine, scalar-first.
- **L278**: `quat_inverse(odom_init_quat)` uses the one from `marslab.runtime.main_loop` (L64 import). OK.

### 4.5 Shutdown path

- **L333-351**: `finally` with four `except Exception: pass` and an `os._exit(0)`. Same Isaac-Sim-can-segfault-on-close story as `convert_urdf_to_usd.py`. Adequately documented at L345-351. The silent bare `except` for `node.destroy_node()` (L336-338) and `rclpy.shutdown()` (L340-344) is at least bounded to shutdown; tolerable.

### 4.6 Deeper problem: bad wiring

- **L162** `imu = handles.imu` — assigned to a local then passed into `ctx.imu` at L294. If the sensor spawner ever returns a different attribute name, IMU integration silently breaks.
- **L319-323** — `ctx.compute_sun_fn=compute_sun_position`, `ctx.compute_sol_sun_fn=compute_sol_sun_position`, ... six functions passed as fields. The `LoopContext` dataclass (in `main_loop.py`) effectively has a giant hand-wired plugin registry. For 6 fields this is fine; if it grows, consider a single `services: LoopServices` dataclass so the wiring site stays one field.

### 4.7 `List[tuple]` soup

- **L250-256**: `sensor_frames: List[tuple] = [("camera_link", camera_cfg["local_translation"]), ...]` — `List[tuple]` without type arguments is meaningless. Either `List[Tuple[str, Sequence[float]]]` or a namedtuple. The fact that `scan_frame` gets conditionally appended is exactly the "add a dataclass" signal.

---

## 5. Correctness: does `run_stage3_monolithic.py` math match `marslab/`?

- `rpy_to_quat`: **identical**.
- `quat_inverse`, `quat_multiply`, `quat_rotate_vec`: **formula identical**, inline version lacks input shape validation (L1215-1240).
- Ackermann: inline calls `marslab.robots.rover_control.ackermann_command` — **no drift, same implementation.**
- Odometry math: inline at L1367-L1432 **inlines the same algorithm** as `odometry_math.compute_odom_delta` + `world_twist_to_body` + `odometry_publisher`. Same math, different error handling (inline swallows with `pass`, module logs).
- Velocity / steer ramp: inline at L1304-L1321, module has `ramp_steer_angles` and `ramp_wheel_velocities` in `rover_control.py`. **Algorithm matches.**
- Solver iteration count hack: L381-397 sets `physxScene:solverPositionIterationCount=16, Velocity=4` directly on the USD prim because "PhysicsContext has no set_solver_*_iteration_count in Isaac Sim 5.x". The equivalent in `run_stage4.py` / `stage2_boot` is — absent? I don't see this being done in the modular path. **That is a real drift.** If the Oracle needs 16/4 iterations to stabilize the 29-DOF articulation, the twin (`run_stage4.py`) is running at default 4/1 and may have subtly different PD-gain behaviour. Flagged for the team to verify.

---

## 6. DELETE CANDIDATES

### 6.1 Entire file: `scripts/phase1/run_stage3_monolithic.py`

Reasons covered in §1. The single worst file in the repo from an external-reviewer standpoint. 1,239-line `main()`, massive duplication with clean modules, inline closures of pure functions, cargo-cult `noqa` comments, 10 bare `except Exception`, `os._exit(0)` after silent failure.

### 6.2 `tests/unit/test_monolithic_new_uses_main_loop.py`

Grep shows this file exists solely to assert:
- the Oracle md5 matches `beefa12579dd43f3da27b1dae3c6f852`, and
- the twin imports specific symbols by name.

`grep ORACLE_PATH` / `grep "md5"` in the test is not a behavioral test — it's a wax seal on a frozen file. Delete with §6.1.

### 6.3 `tests/unit/test_monolithic_new_seed_propagation.py`

Same pattern: pins Oracle path and Oracle md5. Seed-propagation behavior deserves a real test, but pinned against the modular code (`marslab/config/loader.py::propagate_seeds_in_dict`), not against a frozen script. Rewrite in place, don't keep pointing at the Oracle.

### 6.4 Dead imports + `_ = (...)` line in `run_stage4.py`

- `scripts/phase1/run_stage4.py:50, 51, 328`. Delete once §6.2/§6.3 are gone.

### 6.5 `yaml` import in `run_stage3_monolithic.py:55`

- Imported-and-unused. Moot if §6.1 lands. Otherwise delete.

### 6.6 Commented-out `kit.close()` calls in `convert_urdf_to_usd.py`

- L231, L282. Replace with a link to the relevant Isaac Sim issue tracker or remove. Commented-out code in a committed file is a code smell.

### 6.7 Docstring narrative in `run_stage2.py` L12-14

- "R7-2 (2026-04-23): the original 421-LOC script was split into three focused modules..." — historical narrative belongs in CHANGELOG/git. Strip from docstring.

---

## 7. Security summary

| Vector | Verdict |
|---|---|
| `subprocess` / `shell=True` / `os.system` / `os.popen` | None. Clean. |
| XML external entity (XXE) | No XML parser used in `convert_urdf_to_usd.py` (regex-based). Not vulnerable. |
| `tempfile.mktemp` | Not used; but `source_path + ".isaac_tmp"` (L141) is a predictable temp-name (§3.4). |
| `eval` / `exec` | None. |
| YAML unsafe load | `run_stage3_monolithic.py:55` imports yaml but never calls it. Downstream `load_scenario_config` needs to be audited separately (out of this scope). |
| Path traversal | No joined-path-under-root check (§1.7). Low severity. |
| `input()` / interactive prompts | None. |
| `--yes` / destructive-confirm flags | Not present. `convert_urdf_to_usd.py` unconditionally removes existing `--usd` output (§3.6); no `--force` gate. |
| Hard-coded secrets / tokens | None found. |

No security show-stoppers. Several hygiene items (§3.4, §3.6).

---

## 8. Style / type hint summary

- `run_stage2.py`, `run_stage4.py`: `main() -> int` hint; internals mostly un-annotated. Typical for CLI glue, acceptable.
- `convert_urdf_to_usd.py`: `sanitize_urdf(source_path: str) -> str`, `parse_args() -> argparse.Namespace`, `main() -> int` — consistent.
- `run_stage3_monolithic.py`: `main() -> int`; `clamp`, `clamp_twist`, `rpy_to_quat`, `resolve_joint_indices`, `load_terrain_elevation` annotated. Everything else bare. Inline quaternion closures (L1215-1238) are annotated. Docstrings are Google-style where present but the 1,239-line main has *no* internal docstrings beyond section banners (`# § 7.X` comments).

---

## 9. Recommended action order (external reviewer's plan)

1. **Merge `run_stage4.py` → `run_stage3.py`**, delete `run_stage3_monolithic.py`.
2. **Delete** `tests/unit/test_monolithic_new_uses_main_loop.py` + `test_monolithic_new_seed_propagation.py`.
3. **Replace** the seed-propagation test with a real behavior test against `marslab/config/loader.py::propagate_seeds_in_dict`.
4. **Move** `physxScene` solver iteration setup from the Oracle path into `marslab/runtime/stage2_scene.py` (or wherever the world is built) — this is a real drift, not dead code.
5. **Fix** `convert_urdf_to_usd.py`: strip the commented-out `kit.close()` lines, switch to `tempfile.NamedTemporaryFile(dir=..., suffix=..., delete=False)`, drop the happy-path `finally` block (or comment it as dead-on-success), add `--force` guard for existing `--usd` removal.
6. **Fix** `run_stage2.py`: move hard-coded `"RaytracedLighting"` into config; strip historical narrative from docstring.
7. **Fix** `run_stage4.py`: drop the three `F401` imports + the `_ = (...)` line; fix AtmospherePanel lifecycle inside `marslab/gui/atmosphere_panel.py` instead of papering over it with 5 `simulation_app.update()` calls; replace `List[tuple]` with a typed structure.
8. **Update** `README.md` lines 177-181 which currently advertise two scripts (one of which — `run_stage3_monolithic_new.py` — is already deleted).

---

## 10. Three-line summary

- `scripts/phase1/run_stage3_monolithic.py` is a 1,495-line file with a 1,239-line `main()` that verbatim re-implements 10+ already-modularised `marslab/` subsystems (quaternions, odometry math, rover spawn, sensor spawn, OmniGraph build, DriveAPI setup, rclpy init, main loop); **delete the file, delete its grep-based tests, and rename `run_stage4.py` to `run_stage3.py`**.
- `convert_urdf_to_usd.py` is brittle but functional — regex-as-XML-parser is defensible for a one-shot converter, but the commented-out `kit.close()` cargo-cult, predictable `.isaac_tmp` side-file, unconditional `os.remove(--usd)`, and multiple `os._exit` branches all need cleanup before any external engineer could maintain it.
- `run_stage4.py` is the correct decomposed runtime (356 LOC, calls clean marslab modules) but carries three F401 imports and a `_ = (...)` line whose only purpose is to satisfy grep-based tests against the Oracle; strip them together with §1 / §6.
