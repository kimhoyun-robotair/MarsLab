# PROJECT KNOWLEDGE BASE

**Generated:** 2026-07-25  
**Commit:** `04f4346` on `main`

## OVERVIEW

MarsLab is an Isaac Sim 5.x Mars-rover simulator with optional ROS 2 Jazzy
bridging. Python package code lives in `marslab/`; the supported runtime path
is intentionally separated from CPU-only unit testing.

## STRUCTURE

```text
MarsLab/
├── marslab/                 # Python package and simulator entry points
│   ├── config/              # YAML loading and Pydantic v2 schemas
│   ├── environment/         # Offline Mars/environment calculations
│   ├── rendering/           # Sky, sun, fog, render settings
│   ├── robots/              # Rover USD spawning and drive/physics setup
│   ├── ros2_bridge/         # OmniGraph/rclpy publishers, TF, QoS
│   ├── runtime/             # Prechecks, lifecycle context, simulation loop
│   ├── sensors/             # Isaac sensor creation and overrides
│   └── sim/                 # SimulationApp and world bootstrapping
├── configs/                 # Canonical/default and rover configuration YAML
├── tests/unit/              # CPU-only pytest suite
├── assets/                  # Rover USD assets; `m2020-urdf-models` is a submodule
├── launch/                  # Separate ROS 2 companion launch files
└── .github/workflows/       # CI lint, test, and security jobs
```

## WHERE TO LOOK

| Task | Location | Notes |
|---|---|---|
| Run the simulator | `marslab/main.py` | Sole runtime entry point; orchestrates all layers. |
| Run under Isaac | `marslab/isaac_python.sh` | Isolates Isaac's Python 3.11 and bundled ROS libraries. |
| Add config/schema | `marslab/config/` | Read its local guide first. |
| Change simulation lifecycle | `marslab/sim/`, `marslab/runtime/` | Isaac imports stay deferred until `SimulationApp` exists. |
| Change ROS, TF, or sensor graphs | `marslab/ros2_bridge/` | Read its local guide first. |
| Add CPU tests | `tests/unit/` | Read its local guide and reuse `conftest.py` fixtures. |
| Convert rover source assets | `marslab/fix_urdf_inertia.py`, `convert_urdf_to_usd.py` | One-shot preparation, never runtime work. |

## CODE MAP

| Symbol | Location | Role / reach |
|---|---|---|
| `main` | `marslab/main.py` | CLI and lifecycle orchestrator. |
| `boot_simulation_app` | `marslab/sim/boot.py` | Creates Kit/Isaac boundary and enables ROS bridge. |
| `spawn_rover` | `marslab/robots/rover.py` | Creates/configures rover USD; called by `main`. |
| `spawn_sensors` | `marslab/sensors/sensor_spawner.py` | Creates Isaac sensors; nine call sites in `main`. |
| `build_loop_context` | `marslab/runtime/loop_context.py` | Packages live handles/callbacks for the runtime loop. |
| `run_main_loop` | `marslab/runtime/main_loop.py` | Stateful physics/control/publishing loop. |

Runtime flow: precheck/config → atmosphere snapshot → SimulationApp → world/terrain
reference → rover/sensors → optional ROS 2 side → `LoopContext` → main loop → cleanup.

## CONVENTIONS

- Python 3.12+ for development. Black and Ruff target `py312`, 100 columns.
- Keep the dependency direction: configuration → pure computation → Isaac scene →
  runtime loop. Keep pure/offline code importable without Isaac or GPU.
- Defer `omni`, `isaacsim`, `pxr`, and live `rclpy` imports until their runtime
  boundary. Isaac must be started through `marslab/isaac_python.sh`.
- Scene USDZ packages are explicit runtime inputs; do not add terrain or scene
  authoring back into this repository.
- `assets/m2020-urdf-models` is a git submodule. Clone/update it recursively.

## ANTI-PATTERNS (THIS PROJECT)

- Do not introduce plugin systems, registration layers, god objects, or circular
  imports to a deliberately flat architecture.
- Do not rerun URDF conversion at runtime.
- Do not put per-scenario adjustments in `configs/rover_m2020.yaml`; use scenario
  YAML/CLI overrides instead.
- Do not import or export deprecated sensor Path A modules (`camera.py`, `imu.py`,
  `lidar.py`).
- Do not run two ROS publishers for the same TF transform.
- Do not mix a system ROS environment into the Isaac process; use a separate ROS
  terminal for `launch/rover_state_publisher.launch.py`.

## COMMANDS

```bash
pip install -e ".[dev]"
pytest tests/unit/ -q
black --check marslab/ tests/
ruff check marslab/ tests/
mypy

# Isaac runtime (the legacy --usda flag accepts the current Scene USDZ input)
marslab/isaac_python.sh marslab/main.py --usda assets/scene/jezero_plain/jezero_plain.usdz \
  --scenario configs/default.yaml --rover-yaml configs/rover_m2020.yaml --no-ros2
```

## NOTES

- Unit tests use mocks/fakes for Isaac, ROS 2, USD, and `usdrt`; they do not
  require a GPU or Isaac installation.
- CI's lint workflow also names `scripts/`, but that directory is absent. Use the
  documented local commands above unless the CI configuration itself is changed.
- `build/`, `install/`, and `log/` are generated colcon artifacts, not a local
  source build workflow.
