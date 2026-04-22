# Visual Inspection Checklist

Results logged in work_log/LOG.md after each inspection.

## V1: Sky Color
- [ ] Sky is butterscotch (yellowish-brown), NOT blue or black
- Compare with: MSL Mastcam sky images
- Config: tau=0.3 (clear)

## V2: Terrain Topography
- [ ] Terrain has realistic Mars topography (craters, rocks)
- Compare with: HiRISE imagery of Jezero Crater

## V3: Rock Distribution
- [ ] Rock distribution looks natural (not grid-aligned)
- Compare with: Mars surface photographs

## V4: Tau Variation
- [ ] tau=0.3 and tau=2.0 scenes are visually different
- [ ] tau=2.0 has lower visibility (hazier)
- Method: Side-by-side screenshots

## V5: Mars vs Lunar
- [ ] Mars rendering is distinguishable from lunar parameters
- [ ] Mars: butterscotch sky, reddish terrain
- [ ] Lunar: black sky, grey terrain (if tested)

## V6: Rover on Terrain
- [ ] Rover visible on terrain surface
- [ ] Wheels touching ground (not floating)

## V7: Multi-Robot (Week 10)
- [ ] 3 robots visible simultaneously

## V8: Semantic Labels (Week 12)
- [ ] Label map overlay aligns with RGB

## V9: Rover on Terrain + Rocker-Bogie Articulation (Wk1)
- [x] Rover body rests stably on Mars terrain with fix_base=False (no drift, no explosion)
  -- PASSED 2026-04-14 via v4 probe `|v| < 0.05 m/s` settle gating (user run,
  exit 0, Kit clean shutdown at [155.003s])
- [x] Six wheels in contact with terrain (no floating, no penetration)
  -- PASSED 2026-04-14 via v4 probe: settle gating + clean shutdown imply all
  wheel colliders resolved without penetration or loss of contact
- [ ] Rocker-bogie suspension articulates when rover traverses uneven rocks
  (left and right rocker arms visibly rotate independently)
  -- PENDING: requires cmd_vel drive test, deferred to Wk2 #4 (TaskList #15)
- [x] IMU z-axis reading = 3.72 +/- 0.05 m/s^2 when rover is at rest
  (THE critical Wk1 acceptance test, run by user in Isaac Sim)
  -- PASSED 2026-04-14 via v4 probe `IMUSensor.lin_acc[z] ∈ [3.67, 3.77]` gating
  (user run, exit 0, evidence at /home/hoyunkim/MarsLab/temp.txt line 462)
- Method: spawn rover in scripts/run_scene.py, step sim ~5s, screenshot + IMU log
- Spawn geometry (post code-quality-reviewer C1, 2026-04-14): spawn_position
  z = 0.50 m above the sampled terrain surface. Wheel radius = 0.15 m, so
  the wheel bottoms start with a 0.20 m drop gap, avoiding explosive t=0
  contact on sloped cells. Expected stdout line:
  `rover spawn: (cx, cy, surface_z+0.50) [surface=surface_z, offset=0.5]`.
  If the existing Isaac Sim run was done with the pre-C1 offset=0.3 and
  showed penetration/flip, **re-run with the updated YAML**.
- IMU probe procedure (post task #8 / Amendment 2, 2026-04-14, Isaac Sim 5.x):
  - Expected `rover prim:` stdout reads `/World/Rover` (NASA JPL m2020 공식 자산 경로).
  - `[Warning] [isaacsim.asset.importer.urdf] Creating Asset in an in-memory stage`
    is INFORMATIONAL — not a failure.
  - Use `isaacsim.sensors.physics.IMUSensor` (5.x); the deprecated
    `omni.isaac.sensor.IMUSensor` segfaults when bound to a live physics scene.
  - Physics MUST be actively stepping. Wrap the probe in a temporary
    `isaacsim.core.api.SimulationContext(physics_prim_path="/physicsScene",
    physics_dt=1/200)` + `.reset()` + 1000 `.step(render=False)` calls (~5 s sim
    time). `scripts/run_scene.py` alone only does `simulation_app.update()` and
    never advances physics.
  - Rover prim path is read at runtime from `robot_prim_paths["rover_0"]`
    (populated by the spawn loop), not hardcoded.
  - Primary path: `IMUSensor(prim_path=f"{rover_prim_path}/base_link/wk1_imu_probe")`
    under try/except. Expected stdout:
    `[wk1-imu] lin_acc (IMU) = [...]` + `[wk1-imu] |z| (IMU) = <value> m/s^2`.
  - Fallback (if IMUSensor path raises): read
    `UsdPhysics.Scene(stage.GetPrimAtPath("/physicsScene")).GetGravityMagnitudeAttr()`
    AND assert `SingleArticulation.get_linear_velocity()` has `|v| < 0.05 m/s`
    to confirm the rover actually settled. Both paths feed the same `imu_z`
    variable and the same Mars-band assert `3.67 <= imu_z <= 3.77`.
  - Expected PASS line: `[wk1-imu] PASS: |z| = <value> m/s^2 in [3.67, 3.77]`.
  - Revert the entire probe block from `scripts/run_scene.py` after the run;
    permanent publisher is Wk2 #7 scope under `marslab/ros2_bridge/`.
  - Full procedure (Steps 1-5) lives in `_workspace/wk1_robotics_handoff.md`
    "THE critical test" section; old v1 snippet preserved as HTML comment
    `DISABLED (wk1_imu_probe_v1): replaced 2026-04-14`.
- IMU probe v5 procedure (post TaskList #10 + #11, 2026-04-14):
  - **Status:** v5 is the live probe, sentinel-delimited at
    `scripts/run_scene.py:374-627` by `# === Wk1 acceptance probe v5:
    dual-sink logging (TEMPORARY) ===` / `# === end Wk1 acceptance probe
    v5 ===`. Historical versions v1-v4 preserved as HTML comments in
    `_workspace/wk1_robotics_handoff.md` at lines 250, 277, 347, 415.
  - **Physics now runs** (task #10, 2026-04-14): `marslab/robots/rover.py`
    applies `PhysxSchema.PhysxSceneAPI.Apply(scene_prim)` idempotently;
    `scripts/run_scene.py` instantiates `isaacsim.core.api.World(
    physics_prim_path="/physicsScene",
    sim_params={"gravity": (0, 0, -config.mars_env.gravity)})` before the
    stage is built, and drives the main loop with `world.reset()` +
    `world.step(render=True)` instead of `simulation_app.update()`. IMU
    sensors now have a real physics scene to bind to.
  - **v5 gating chain (all 5 must pass):**
    1. `robot_prim_paths["rover_0"]` non-None + `base_link` child exists
    2. `UsdPhysics.Scene("/physicsScene").GetGravityMagnitudeAttr()`
       matches `config.mars_env.gravity` within 1e-4
    3. `gravity_mag` in Mars band [3.67, 3.77]
    4. After 1000 `world.step(render=True)` (5 s sim time),
       `SingleArticulation.get_linear_velocity()` has `|v| < 0.05 m/s`
    5. After 30 more `world.step()`, `IMUSensor.get_current_frame()`
       `|lin_acc[z]|` in Mars band [3.67, 3.77]
  - **Dual-sink logging (task #11):** every probe line is emitted via
    a `_wk1_log(msg)` helper that writes to THREE sinks:
    - `_workspace/wk1_imu_probe_result.json` (structured, atomic
      tmp+rename via `os.replace`, schema_version=1, source of truth)
    - `carb.log_warn(line)` / `carb.log_error(line)` for
      level="error" — lands in Kit stderr so `2> run.log` captures it
    - `print(line, flush=True)` for interactive runs
  - **Final verdict line (grep-able from both sinks):**
    `[wk1-imu] VERDICT: PASS|FAIL|ERROR reason="..." |g|=<value> imu_status=...`
  - **Expected PASS stdout:**
    `[wk1-imu] PASS: |g| = <value>, IMU |z| = <value>` followed by
    `[wk1-imu] VERDICT: PASS reason="..." |g|=<value> imu_status=valid`
  - **Recommended invocation** (so stdout is captured even without
    task #11's carb mirror):
    `cd ~/MarsLab && ~/isaacsim/python.sh scripts/run_scene.py --config configs/mars_env.yaml 2>&1 | tee /tmp/run_scene.log`
    The authoritative source of truth is always
    `_workspace/wk1_imu_probe_result.json` regardless of log capture.
  - **Fail-mode table (ordered by likelihood, for user triage):**
    1. `rover not settled: |v|=<large>` -- terrain collider may not be
       picked up by PhysX. If `|v| > 0.5`: ping scenario-terrain-architect
       for `UsdPhysics.CollisionAPI` on `/World/Terrain`. If `0.1-0.3`:
       raise `SETTLE_STEPS` in the probe.
    2. `IMU |z| outside Mars band` with small speed -- IMU pipeline
       live but reading wrong; check `gravity_dir = (0, 0, -1)`.
    3. `YAML (3.72) and PhysxScene (9.81) gravity disagree` -- World's
       PhysicsContext clobbered Mars gravity with Earth default. Move
       `World(...)` earlier in `main()` or nest the dict.
    4. `World ready: ... gravity=3.72 m/s^2` missing from stdout --
       World constructor failed silently. Rare, needs investigation.
    5. Post-assert Kit SIGSEGV -- try/finally should prevent; if it
       still happens, the v5 shutdown structure regressed.
  - **Revert after PASS:** delete the entire block between the v5
    sentinels from `scripts/run_scene.py`. Permanent IMU publisher is
    Wk2 #7 scope under `marslab/ros2_bridge/`.

## V10: ROS2 Bridge — cmd_vel / TF / Odometry Live (Wk2)

**Precondition:** This checklist is meaningful only AFTER slam-nav-integrator
lands Wk2 #7 (sensor ROS2 re-enable). Until then the three new modules
(`marslab/ros2_bridge/cmd_vel_subscriber.py`,
`marslab/ros2_bridge/tf_broadcaster.py`, `marslab/ros2_bridge/odometry.py`)
are offline-verified but not wired into `scripts/run_scene.py`. The user run
described below assumes task #7 has landed an `rclpy.init()` + single-threaded
executor + `rclpy.shutdown()` lifecycle block in `main()` that instantiates
`CmdVelSubscriber`, `TfBroadcaster`, and `OdometryPublisher` against the
spawned `SingleArticulation`.

- [ ] `/rover_0/cmd_vel` subscriber moves the rover
  - Method: in a second terminal (ROS2 Jazzy sourced), run
    `ros2 topic pub --once /rover_0/cmd_vel geometry_msgs/msg/Twist \
     '{linear: {x: 0.3, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}'`
    and watch the rover in Isaac Sim. Expected: all six wheels spin
    forward at `0.3 / 0.15 ≈ 2.0 rad/s`, rover accelerates along +x.
  - Expected: `ros2 topic echo /rover_0/odom --once` shows
    `twist.twist.linear.x ≈ 0.3` within numerical precision after
    ~1 s of settling.
- [ ] `/rover_0/cmd_vel` watchdog zeros the wheels on message drop
  (Wk2 #7b / task #18)
  - Method: publish a non-zero Twist once (as above), verify the rover
    starts moving, then **do not publish again for > 0.5 s**.
  - Expected: rover decelerates to a stop within one watchdog tick
    (0.05 s) after the 0.5 s timeout expires. Check the log for one
    (and only one) `cmd_vel watchdog: no Twist received in 0.500 s on
    /rover_0/cmd_vel — zeroing wheels ...` warning line.
  - Expected: re-publishing a fresh Twist resumes motion immediately
    and clears the warning latch (subsequent drops log a fresh
    warning, not silent).
- [ ] In-place left pivot is visibly symmetric
  - Method: `ros2 topic pub --once /rover_0/cmd_vel ... \
     '{linear: {x: 0.0, ...}, angular: {x: 0.0, y: 0.0, z: 0.4}}'`.
  - Expected: left wheels spin backward, right wheels spin forward at
    equal magnitude `(0.4 * 0.35) / 0.15 ≈ 0.933 rad/s`. Rover rotates
    counter-clockwise about `base_link`, no translation.
- [ ] Speed clamp engages on over-range commands
  - Method: publish `linear.x: 10.0` (over the 1.0 m/s limit).
  - Expected: wheels spin at `1.0 / 0.15 ≈ 6.667 rad/s`, not 66.67. The
    drive-layer clamp is silent (no error), matching Nav2's "planner
    produces over-eager velocity, drive layer caps it" expectation.
- [ ] `/tf` chain matches `_workspace/ros2_topic_spec.md` diagram
  - Method: `ros2 run tf2_tools view_frames` → produces `frames.pdf`.
  - Expected tree:
    ```
    odom
    └── base_link
        ├── camera_link   (static, stereo_rgb mount)
        ├── depth_link    (static, depth camera mount)
        ├── lidar_link    (static, 3D lidar roof mount)
        └── imu_link      (static, base_link origin)
    ```
  - Expected: the dynamic `odom → base_link` edge updates at ~50 Hz;
    check with `ros2 run tf2_ros tf2_echo odom base_link` while the
    rover drives.
- [ ] `/rover_0/odom` publishes at 50 Hz (±10%)
  - Method: `ros2 topic hz /rover_0/odom` for ~10 s.
  - Expected: average rate between 45 Hz and 55 Hz, per the
    `_workspace/ros2_topic_spec.md` ±10% tolerance budget.
- [ ] `/rover_0/odom` twist matches the commanded Twist at steady state
  - Method: publish `linear.x: 0.25, angular.z: 0.1` for 3 s, then stop
    publishing (the watchdog will zero the wheels after 0.5 s).
  - Expected: just before the drop, `/rover_0/odom.twist.twist.linear.x`
    should read ~0.25 m/s and `.angular.z` ~0.1 rad/s — this verifies
    the FK round-trip (`compute_wheel_velocities → set_joint_velocities
    → PhysX → get_joint_velocities → wheel_velocities_to_twist`) is
    internally consistent on a non-slipping rover.
- [ ] Pose integration matches visible rover trajectory
  - Method: drive the rover in a known pattern (e.g. forward 1 m, left
    turn 90°, forward 1 m) via `ros2 topic pub --rate 10` commands, and
    visually compare the final rover position in Isaac Sim against the
    final `/rover_0/odom.pose.pose.position` reading.
  - Expected: positions agree within ~0.05 m on flat terrain. Larger
    drift on sloped terrain is expected for v1.0 (no slip compensation,
    exact arc integration assumes rigid, non-slipping wheels).

**Notes / gotchas for slam-nav-integrator when wiring Wk2 #7:**

1. The three Node classes (`CmdVelSubscriber`, `TfBroadcaster`,
   `OdometryPublisher`) all expose a `.node` property that returns the
   underlying `rclpy.node.Node`. Use a single `rclpy.executors.SingleThreadedExecutor`
   to spin all three in parallel inside the `world.step()` loop via
   `executor.spin_once(timeout_sec=0.0)` between physics steps.
2. Construction order must be: `world.reset()` → `SingleArticulation.initialize()`
   → `rclpy.init()` → three Node constructors (each takes the
   articulation handle) → executor registration → main `world.step()`
   loop.
3. In the finally block, shut down in reverse order: destroy nodes,
   `rclpy.shutdown()`, `simulation_app.close()`. The rclpy shutdown
   MUST precede the simulation_app close, otherwise Kit's atexit
   chain unloads the rclpy C++ shared libs at an awkward time.
4. The cmd_vel watchdog uses `node.create_timer(0.05, ...)` which
   spins off the same executor — no special handling required, but
   the executor must actually spin at least every ~50 ms or the
   watchdog will fire late.
5. The Wk1 IMU probe block (sentinel `# === Wk1 acceptance probe v5`)
   should be reverted in the same Wk2 #7 edit that wires the ROS2
   modules in — the handoff doc flags this explicitly.

## V10: Wk2 ROS2 Bridge Live Topic Plumbing (Wk2 #7 acceptance)

Wk2 #7 landed 2026-04-14 (TaskList #7 completed). `scripts/run_scene.py`
now wires the full ROS2 bridge lifecycle: `rclpy.init()` →
`CmdVelSubscriber` + `TfBroadcaster` + `OdometryPublisher` →
`SingleThreadedExecutor` → main publish loop → reverse-order shutdown
(`executor.shutdown()` → node destroy → `rclpy.shutdown()` →
`simulation_app.close()`) inside a `try/finally` wrapper. Offline gate
is green (black 78 / ruff / pytest 243). The Wk1 v5 probe block is
disabled via raw-string wrap (`_WK1_PROBE_V5_DISABLED = r'''...'''`) so
its historical `except` handlers are data, not executable code (verified
via Python AST — only 5 active exception handlers in run_scene.py,
matching slam-nav-integrator's manual count).

Live-topic verification is USER-RUN in Isaac Sim with ROS2 Jazzy sourced.
qa-validator prepares the procedure only.

Expected stdout marker for a clean run:
`[run_scene] Shutting down ROS2 + Isaac Sim...` in finally, then
`simulation_app.close()` without Kit atexit SIGSEGV.

### Acceptance procedure (user-run in Isaac Sim)

- [ ] **V10-1** Headless smoke loop completes with `MARSLAB_PUBLISH` unset:
  `~/isaacsim/python.sh scripts/run_scene.py --config configs/mars_env.yaml 2>&1 | tee /tmp/run_scene_wk2.log`
  - Pass criterion: exit code 0, 400-step publish loop executes,
    reverse-order shutdown reached, no Kit SIGSEGV, no
    `rclpy.shutdown()` exception logged.
- [ ] **V10-2** Continuous publish mode with topic plumbing checks:
  `MARSLAB_PUBLISH=1 ~/isaacsim/python.sh scripts/run_scene.py --config configs/mars_env.yaml`
  In a second terminal (ROS2 Jazzy sourced):
  - [ ] `ros2 topic list` shows `/rover_0/rgb/image_raw`,
    `/rover_0/lidar/points`, `/rover_0/imu/data`, `/tf`, `/rover_0/odom`,
    `/rover_0/cmd_vel`, `/clock` (plus any depth/stereo depending on
    sensor config YAMLs)
  - [ ] `ros2 topic hz /rover_0/imu/data` → ~200 Hz within ±10%
  - [ ] `ros2 topic hz /rover_0/lidar/points` → at configured rate
  - [ ] `ros2 topic hz /rover_0/rgb/image_raw` → at configured rate
  - [ ] `ros2 topic hz /tf` → non-zero, broadcaster active
  - [ ] `ros2 run tf2_tools view_frames` produces a complete tree:
    `map` → `odom` → `base_link` → wheel + sensor frames. No
    disconnected subtrees.
  - [ ] `ros2 topic hz /rover_0/odom` → matches odometry publisher rate
- [ ] **V10-3** cmd_vel drive test (verifies task #15 cmd_vel subscriber
  end-to-end):
  - [ ] Send continuous forward command:
    `ros2 topic pub /rover_0/cmd_vel geometry_msgs/msg/Twist "linear: {x: 0.3}" --rate 10`
    → rover visibly drives forward in Isaac Sim viewport, wheels rotate
  - [ ] Send turn command:
    `ros2 topic pub /rover_0/cmd_vel geometry_msgs/msg/Twist "angular: {z: 0.5}" --rate 10`
    → rover turns in place (skid-steer, opposing wheel banks)
  - [ ] Rocker-bogie visual articulation observable when rover traverses
    a rock (this also closes V9's pending rocker-bogie line)
- [ ] **V10-4** Watchdog test (verifies task #18 cmd_vel watchdog):
  - [ ] Send a single Twist message, then stop publishing:
    `ros2 topic pub /rover_0/cmd_vel geometry_msgs/msg/Twist "linear: {x: 0.3}" --once`
  - [ ] After `SkidSteerDriveConfig.cmd_vel_timeout_s` elapses, stdout
    from `~/isaacsim/python.sh` shows
    `cmd_vel watchdog: no Twist received in X.XXX s on /cmd_vel`
    warning line (logger.warning, not error — it's a recovery path not
    a failure), and the rover comes to a stop without an emergency brake
- [ ] **V10-5** Clean Ctrl+C shutdown (verifies try/finally reverse-order
  shutdown): `Ctrl+C` the `run_scene.py` process.
  - [ ] `KeyboardInterrupt` is caught at run_scene.py:517
  - [ ] Stdout shows `[run_scene] Shutting down ROS2 + Isaac Sim...`
  - [ ] No `executor.shutdown() raised: ...` / `destroy_node() raised: ...` /
    `rclpy.shutdown() raised: ...` log lines (those are the per-step
    log-and-continue handlers at lines 537/547/556 — they only fire if
    shutdown misbehaves; a clean Ctrl+C should not trigger any of them)
  - [ ] No Kit atexit SIGSEGV, no crash dump file

### Known Wk2 limitations (inform user before V10 run)

- Slopes in crater_slopes.yaml are limited (mean ~4° / p90 ~8° / max ~31°)
  because the bundled Jezero tile is flat plain. scenario-terrain-architect
  flagged as R-S1. Higher-relief DEM is Wk3+ follow-up.
- Wk1 V9 rocker-bogie articulation checkbox will close automatically
  as part of V10-3 (drive test over a rock) — no separate re-run needed.
- `MARSLAB_PUBLISH` env var is the switch between CI smoke (unset, 400 steps)
  and live user-run (set, continuous). Neither changes the ROS2 lifecycle
  wiring — same nodes, same executor, same shutdown path.

### Action on failure

If any V10 checkbox fails, copy the exact log lines + any crash dump
path and forward to slam-nav-integrator (tasks #7/#15/#16/#17/#18 are
all their surface). If the rover doesn't drive at all in V10-3, also
ping robotics-mobility-lead because the articulation wiring is their
surface.
