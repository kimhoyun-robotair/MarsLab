# SENSOR GUIDE

## OVERVIEW

`sensor_spawner.py` is the single supported camera, RTX LiDAR, and IMU
orchestrator. `SensorHandles` carries live handles, prim paths, and read helpers.

## CONVENTIONS

- Keep Isaac imports deferred and preserve CPU-safe negative-path tests.
- Use the canonical schema and retain tested legacy alias normalization; raw Omni
  attribute names and sensor prim paths are API contracts.
- Preserve parent-Xform orientation, gravity assertion at attach time, and
  read-time gravity warning behavior.
- Retain one shared camera render product when bridge outputs need synchronized
  RGB/depth/point-cloud/camera-info data.

## ANTI-PATTERNS

- Do not reintroduce or export deprecated `camera`, `imu`, or `lidar` modules;
  only `SensorHandles` and `spawn_sensors` are public exports.
- Do not bypass profile resolution or runtime USD overrides with hardcoded tuning.

## CHECKS

```bash
pytest tests/unit/test_sensor_spawner.py tests/unit/test_sensor_spawner_unified.py -q
pytest tests/unit/test_lidar_runtime_override.py tests/unit/test_camera_single_render_product.py -q
```

## NOTES

`sensors/__init__.py` intentionally exposes only the unified facade. Preserve
that boundary when restructuring sensor implementation details.
