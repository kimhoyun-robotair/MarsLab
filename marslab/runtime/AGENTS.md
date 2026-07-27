# RUNTIME GUIDE

## OVERVIEW

`marslab.runtime` owns preflight checks, atmosphere boot data, post-reset setup,
the live handle context, and the simulation tick loop. Preflight and atmosphere
preparation happen before Kit/scene creation; `main.py` owns final cleanup.

## WHERE TO LOOK

| Task | Location | Notes |
|---|---|---|
| Validate before Kit boot | `precheck.py` | Fail here for config/USD/lidar preconditions. |
| Prepare atmosphere inputs | `atmosphere_boot.py` | Works from scenario YAML/config snapshot. |
| Assemble live dependencies | `loop_context.py` | `LoopContext` has cross-domain handles and callbacks. |
| Change each simulation tick | `main_loop.py` | Control, odometry, IMU/wheel publishing, atmosphere updates. |
| Apply post-reset rover state | `articulation_setup.py` | Joint pose, root pin, and steering reset ordering. |
| Bind sensor coordinate frames | `sensor_frames.py` | Sensor TF, lidar aliases, and RPY tuple contract. |
| Create app/world | `../sim/boot.py`, `../sim/world_setup.py` | Sibling Isaac lifecycle boundary. |

## CONVENTIONS

- `main_loop.py` must remain offline-importable: use `TYPE_CHECKING`, injected
  context values, and deferred runtime-only imports.
- Build all live dependencies once in `build_loop_context()` rather than reaching
  back into global application state from the loop.
- When adding loop behavior, update `LoopContext`/callback contracts and their
  tests; preserve `articulation=None` behavior for `--no-rover`.
- Preserve the ordered lifecycle: precheck/atmosphere snapshot → app/world →
  post-reset articulation/sensors → context/loop → caller-owned shutdown.
- Preserve the explicit cleanup sequence in `marslab/main.py` for bridge, rclpy,
  and `SimulationApp` resources.

## ANTI-PATTERNS

- Do not instantiate Isaac/Omni objects before `boot_simulation_app()`.
- Do not rerun rover URDF conversion or author terrain from this lifecycle.
- Do not add a second owner for a loop callback, ROS publisher, or TF transform.

## CHECKS

```bash
pytest tests/unit/test_runtime_loop_context.py tests/unit/test_main_loop_structure.py -q
pytest tests/unit/test_runtime_shutdown_exit_code.py -q
pytest tests/unit/test_runtime_articulation_setup.py tests/unit/test_runtime_sensor_frames.py -q
pytest tests/unit/test_sim_boot.py tests/unit/test_sim_world_setup.py -q
```
