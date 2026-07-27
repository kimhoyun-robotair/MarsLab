# CONFIGURATION GUIDE

## OVERVIEW

`marslab.config` is a mixed raw-dict/Pydantic v2 pipeline for layered YAML. It
is deliberately offline-importable; runtime selectively validates its typed blocks.

## WHERE TO LOOK

| Task | Location | Notes |
|---|---|---|
| Load/merge YAML | `yaml_loader.py` | Root and rover `base_config` use deep-merge semantics. |
| Propagate deterministic seeds | `loader.py` | `mars_env.seed` drives terrain seed (`seed + 1`). |
| Root scenario model | `schema/root.py` | The rover subtree is intentionally opaque here. |
| Rover/sensor schema | `schema/robot.py` | Large nested model, validators, and legacy migration. |
| ROS bridge schema | `schema/ros2_bridge.py` | QoS and bridge configuration. |
| Default inputs | `../../configs/default.yaml`, `../../configs/rover_m2020.yaml` | Keep ownership boundaries intact. |

## CONVENTIONS

- Use Pydantic schemas at the configuration boundary; downstream code consumes
  validated data.
- Preserve existing `base_config` ordering and recursive merge behavior.
- Preserve path resolution, list replacement, and legacy `sensors.lidar` to
  `lidar_3d` normalization in the loader.
- Schemas forbid unknown fields; update migration tests when changing aliases,
  ranges, units, defaults, or list-length validation.
- Keep this package free of Isaac/Omni/USD imports so its tests stay CPU-only.
- Mypy coverage explicitly includes `marslab/config`; keep annotations meaningful.

## ANTI-PATTERNS

- Do not move per-scenario values into `configs/rover_m2020.yaml`; use scenario
  YAML or a CLI override.
- Do not treat the root rover dictionary as a replacement for the specialized
  rover schema.
- Do not silently change validation defaults, legacy migrations, or merge order.

## CHECKS

```bash
pytest tests/unit/test_config_schema.py -q
pytest tests/unit/test_robot_schema.py -q
pytest tests/unit/test_loader.py tests/unit/test_sensor_seed.py -q
mypy marslab/config
```
