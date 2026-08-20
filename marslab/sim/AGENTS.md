# Simulation boot guide

`marslab.sim` is the narrow Isaac lifecycle boundary: create `SimulationApp`,
enable optional ROS 2, and build the Mars-gravity world. The supported user
launch is:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```

## Contract

- `boot.py` creates Kit with the validated runtime settings and leaves cleanup
  to the caller.
- `world_setup.py` creates the Mars-gravity physics world with matched cadence
  and guarded scene writes.
- Preflight and atmosphere preparation happen before this package; rover,
  retained sensors, bridge, and loop setup happen after the world exists.
- The companion launch owns the identity `base_link`→`Body_Chassis` frame; this
  package does not publish rover TF.

## Rules

- Import `isaacsim`, `omni`, and `pxr` only inside runtime functions after the
  SimulationApp boundary is open.
- Keep `boot_simulation_app()` responsible for app creation and its first update;
  keep `main.py` responsible for closing the app in `finally`.
- Preserve Mars-gravity normalization and guarded writes to `/physicsScene`.
- Keep comments concise and document lifecycle ownership or physics invariants.

Isaac GUI/headless, physics, sensor, ROS, TF, AtmospherePanel, and cleanup
behavior are user-only runtime validation. Agents perform only offline source,
config, and launch reconciliation; use the canonical command above for the
user handoff and do not claim runtime observations.
