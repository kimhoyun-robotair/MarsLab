# Rover guide

`marslab.robots` separates Isaac/USD rover spawning and physics from pure
NumPy Ackermann control. The supported user launch is:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```

## Contract

- `rover.py` consumes the validated `rover` section and owns USD references,
  pose, rigid-body discovery, mass, friction, damping, and suspension setup.
- `drive_api_setup.py` applies drive APIs before reset and tensor PD reinforcement
  after reset; preserve that ordering.
- `rover_control.py` remains pure CPU-side Ackermann computation.
- The USD/URDF root remains `Body_Chassis`. The companion launch owns the sole
  identity `base_link`→`Body_Chassis` connector; do not make the rover spawner
  publish a competing connector.

## Rules

- Defer Isaac, USD, and runtime binding imports. Validate required rover assets
  before Kit creation.
- Keep missing prims and lost physics overrides observable; do not hide a
  failed configuration or silently substitute a global state.
- Keep control limits, wheel geometry, suspension names, and seeded odometry
  inputs sourced from `configs/config.yaml`.
- Keep comments concise and explain a physics or ownership invariant only.

Agent verification is limited to offline source/config reconciliation. User-only
Isaac physics, articulation, rover pose, and odometry observations use the
canonical command above and must not be inferred by an agent.
