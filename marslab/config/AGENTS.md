# Configuration guide

`marslab.config` owns the strict, offline-importable Pydantic v2 boundary for
the integrated MarsLab document. The supported user launch is:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```

## Contract

- `configs/config.yaml` is the sole active runtime document.
- Root sections are `scene`, `runtime`, `mars_env`, `rendering`, `rover`, and
  `wheel_odom`; paths are relative to the declaring config file.
- `rover.sensors` always contains Camera, IMU, and 3-D LiDAR settings. These
  acquisition paths have no feature gate.
- `wheel_odom.publish_tf` explicitly selects the MarsLab dynamic
  `odom`→`base_link` authority; ground truth remains a separate topic-only
  `map`/`base_link_gt` output.
- `rover.ros2.sensor_parent_frame_id` is `Body_Chassis`; the companion launch
  supplies the sole identity `base_link`→`Body_Chassis` connector.

## Where to look

| Task | Location | Notes |
|---|---|---|
| Load the document | `yaml_loader.py` | Resolve paths from the declaring file and return `MarsLabConfig`. |
| Public facade | `__init__.py`, `loader.py` | Keep `MarsLabConfig` and `load_config` as the narrow public surface. |
| Root schema | `schema/root.py` | Compose the six strict root sections. |
| Rover and sensors | `schema/rover.py`, `schema/rover_sensors.py` | Preserve typed physical, control, and retained sensor fields. |
| ROS settings | `schema/rover_ros2.py` | Preserve topic, rate, frame, and QoS contracts. |

## Rules

- Validate once at the configuration boundary; downstream layers consume the
  typed model rather than rebuilding dictionaries.
- Keep unknown-field rejection, path anchoring, units, ranges, defaults, and
  deterministic sensor seed behavior stable unless the runtime contract changes.
- Keep this package free of Isaac, Omni, USD, and live ROS imports so offline
  configuration inspection remains available.
- Keep comments concise and describe the schema role or invariant only.
- User-only Isaac validation uses the canonical command above. Agent checks stop
  at parsing and source/config reconciliation; no agent claims simulator output.
