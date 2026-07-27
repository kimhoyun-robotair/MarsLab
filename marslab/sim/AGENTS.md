# SIMULATION BOOT GUIDE

## OVERVIEW

`marslab.sim` is the narrow Isaac lifecycle boundary: create `SimulationApp`,
enable the bridge, and build the Mars-gravity world. Its imports must remain
deferred so CPU-only tests can import surrounding modules.

## WHERE TO LOOK

| Task | Location | Notes |
|---|---|---|
| Start Kit | `boot.py` | Configures headless/renderer, enables ROS bridge, caller closes app. |
| Create the physics world | `world_setup.py` | Mars gravity, matched physics/render cadence, solver attributes. |
| Sequence the lifecycle | `../main.py`, `../runtime/` | Prechecks run before this package; cleanup is owned by `main.py`. |

## CONVENTIONS

- Import `isaacsim`, `omni`, and `pxr` only inside runtime functions.
- Keep `boot_simulation_app()` responsible for app creation and a first update;
  keep `main.py` responsible for closing it in `finally`.
- Preserve negative gravity normalization and guarded writes to `/physicsScene`.

## CHECKS

```bash
pytest tests/unit/test_sim_boot.py tests/unit/test_sim_world_setup.py -q
```

## NOTES

The terrain USDA is referenced by higher-level startup code; this package builds
the simulation container and world only, not terrain assets.
