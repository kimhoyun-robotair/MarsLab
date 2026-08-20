# Sensor guide

`marslab.sensors` creates the retained Camera, 3-D LiDAR, and IMU acquisition
handles. The supported user launch is:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```

## Contract

- `sensor_spawner.py` is the single coordinator and `SensorHandles` is the
  stable facade for live objects, prim paths, and read helpers.
- Camera RGB, depth, PointCloud2, and CameraInfo share one render product when
  ROS consumers are attached.
- IMU raw and noisy streams and 3-D LiDAR point clouds remain available through
  their existing acquisition paths.
- Sensor frames are children of `Body_Chassis`; the companion launch supplies
  the identity `base_link`→`Body_Chassis` connector.
- Seeded noise and runtime profile/attribute overrides are part of the data
  contract; preserve their deterministic behavior.

## Rules

- Keep `omni`, `isaacsim`, `pxr`, and sensor binding imports deferred to runtime
  functions. CPU-side configuration and negative-path inspection must stay safe.
- Preserve parent-Xform orientation and the Mars-gravity attach assertion; keep
  read-time gravity diagnostics observable.
- Keep Camera, IMU, and 3-D LiDAR acquisition independent of ROS graph setup so
  ROS-off startup still creates the retained handles.
- Do not hardcode profile tuning or duplicate a sensor to satisfy a bridge
  output. Use the typed config and runtime USD overrides.
- Keep comments concise and describe one sensor role or invariant per comment.

Agent verification ends at offline source/config reconciliation. Isaac sensor
creation, frame publication, and output quality are user-only validation using
the canonical command above; do not claim those observations on the user's
behalf.
