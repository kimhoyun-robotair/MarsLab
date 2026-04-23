# R6 Modularization Report

**Date:** 2026-04-23
**Plan reference:** `~/.claude/plans/log-md-r4-addendum-jolly-spring.md` § 6
**Author:** robotics-mobility-lead agent (Opus 4.7)

## 1. LOC diff (Oracle vs twin)

```
Oracle (frozen):       scripts/phase1/run_stage3_monolithic.py      1501 LOC
Twin  (post-R6):       scripts/phase1/run_stage3_monolithic_new.py  1171 LOC   (-330)
Extracted loop:        marslab/runtime/main_loop.py                  513 LOC   (new)
CLI wrapper:           scripts/run_marslab.py                        109 LOC   (new)
```

Twin shrunk by 330 LOC because the main-loop body (§7.23 Ackermann ramp,
odom publish, dynamic atmosphere) now lives in `marslab.runtime.main_loop`.
The extracted module is larger (513 LOC) than the raw loop body it
replaced (≈260 LOC) because of (a) dataclass surfaces, (b) Google
docstrings on every public symbol, and (c) two helper functions
(`_publish_odometry`, `_update_atmosphere`) broken out for readability.

## 2. Section x facade coverage

| Twin section | Module responsible | Approx. LOC moved |
|--------------|-------------------|-------------------|
| §7.7 SimulationApp boot | `marslab.sim.boot.boot_simulation_app` (R4-1) | ~20 |
| §7.8-7.10 World + gravity | `marslab.sim.world_setup.create_world` (R4-1) | ~25 |
| §7.11-7.13 Terrain / atmosphere config | inline (reads facades from `terrain.*`, `environment.*`, `rendering.*`) | n/a |
| §7.16b Structures | `marslab.scene.structure_loader.load_structures` (P1) | ~15 |
| §7.17 Sensors | `marslab.sensors.sensor_spawner.spawn_sensors` (R4-5) | ~55 |
| §7.18 OmniGraph | `marslab.ros2_bridge.sensor_graph.build_sensor_graph` (R8-equivalent facade) | *still inline* |
| §7.19 USD DriveAPI | inline (R5 candidate) | *still inline* |
| §7.21 PD gains readback | inline | *still inline* |
| §7.23 Main loop | **R6-1: `marslab.runtime.main_loop.run_main_loop`** | **~260** |
| CLI dispatch | `marslab.cli.stage3_args.parse_stage3_args` (R3-A2) + **R6-2 `scripts/run_marslab.py`** | ~20 |

## 3. v2.0 extraction candidates

Three blocks remain monolithic in the twin and are strong candidates for
post-iSpaRo 2026 modularization:

1. **§7.18 OmniGraph wiring (≈110 LOC)** — static node creation, edges,
   and `set_values` for the ROS2 sensor graph (clock, TF, IMU, camera,
   LiDAR). High surface area but well-structured; a dataclass-driven
   builder (`SensorGraphSpec`) would make it far easier to add the
   navigation radar planned for v2.0.
2. **§7.19-7.21 DriveAPI + gains (≈130 LOC)** — pre-reset USD DriveAPI
   setup plus post-reset `articulation.set_gains()` readback. Natural home:
   `marslab.robots.rover.apply_drive_profile(articulation, control_cfg)`.
3. **§7.22 cmd_vel + static TF + odom publisher setup (≈70 LOC)** — the
   construction side of the loop state already extracted into
   `OdomPublishState`. A `marslab.ros2_bridge.odometry_setup` facade could
   return a populated `OdomPublishState` directly, eliminating the
   final rclpy wiring left in the twin.

## 4. Test-count delta

| Metric | Pre-R6 | Post-R6 | Delta |
|--------|--------|---------|-------|
| Unit tests (pytest) | 669 | 712 | +43 |
| Failures | 0 | 0 | 0 |
| Black | clean | clean | n/a |
| Ruff | 1 pre-existing I001 in twin L68 | clean | fixed as R6 housekeeping |

## 5. Follow-up work owed

*   **User-driven Isaac Sim smoke test** on Scenario 1 (`configs/scenarios/jezero_flat.yaml`)
    to confirm the extracted loop is byte-exact with the Oracle output
    stream. Memory `feedback_isaac_sim_user_runs` applies.
*   Once smoke passes, `scripts/run_marslab.py` can be promoted from the
    current "delegates into the twin's `main()`" pattern to a proper
    modular pipeline (see candidate list above).
