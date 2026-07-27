# ROVER GUIDE

## OVERVIEW

`marslab.robots` separates Isaac/USD rover spawning and physics from pure NumPy
Ackermann control. It consumes validated rover configuration at the Kit boundary.

## WHERE TO LOOK

| Task | Location | Notes |
|---|---|---|
| Spawn/reference rover USD | `rover.py` | Pose, rigid-body discovery, mass, friction, suspension. |
| Configure articulation drives | `drive_api_setup.py` | DriveAPI before reset; tensor PD reinforcement after reset. |
| Change steering logic | `rover_control.py` | Pure CPU-testable Ackermann computation. |

## CONVENTIONS

- Defer Isaac/USD imports and keep `rover_control.py` free of runtime bindings.
- Preserve `Body_Chassis`/joint path expectations and pre-reset versus post-reset
  drive ordering.
- Treat missing rover prims as observable warnings/failures; never hide a lost
  physics override. Validate config before Kit boot.

## ANTI-PATTERNS

- Do not invoke URDF conversion from the runtime spawn path.
- Do not replace the supported `SpawnedRover` facade with direct global state.

## CHECKS

```bash
pytest tests/unit/test_rover_module.py tests/unit/test_rover_physics_inject.py -q
pytest tests/unit/test_drive_api_setup.py tests/unit/test_ackermann.py -q
```
