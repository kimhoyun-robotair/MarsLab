# Runtime guide

`marslab.runtime` owns preflight, atmosphere preparation, post-reset setup,
live-handle assembly, and the simulation tick loop. The supported user launch
is:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```

## Lifecycle

1. Load and validate the integrated config and required asset paths.
2. Compute the offline atmosphere snapshot before Kit creation.
3. Create `SimulationApp` and the Mars-gravity world.
4. Spawn the rover and retained Camera, IMU, and 3-D LiDAR handles.
5. Optionally attach the ROS 2 graph and rclpy publishers.
6. Build one `LoopContext`, run control/physics/publishing, and clean up in
   reverse ownership order.

`AtmospherePanel` remains part of the GUI atmosphere path. It is created only
when the runtime settings permit GUI atmosphere control and is closed with the
same lifecycle owner.

## Where to look

| Task | Location | Notes |
|---|---|---|
| Preflight | `precheck.py`, `prepare.py` | Stay importable without Isaac and fail before Kit. |
| Atmosphere | `atmosphere_boot.py` | Prepare deterministic initial atmosphere values. |
| Dependencies | `loop_context.py`, `assembly.py` | Assemble live handles and callbacks once. |
| Tick behavior | `main_loop.py` | Control, odometry, sensor reads, and publishing. |
| Post-reset state | `articulation_setup.py`, `post_reset.py` | Preserve reset and drive ordering. |
| Sensor frames | `sensor_frames.py` | Keep sensor children under `Body_Chassis`. |
| Isaac boundary | `../sim/` | Create and close Kit resources at the runtime edge. |

## Output and frame rules

Ground truth and wheel odometry are independent outputs. Ground truth publishes
the absolute `map`/`base_link_gt` evaluation topic and never owns TF. Wheel
odometry publishes `odom`/`base_link`; `wheel_odom.publish_tf` controls whether
it owns the dynamic transform.

The companion launch owns the one identity `base_link`→`Body_Chassis` static
connector. The external articulation publisher owns descendants below
`Body_Chassis`, and MarsLab owns only retained sensor static frames there.

## Boundaries

- Build all live dependencies once; do not reach into global application state
  from the loop.
- Keep Isaac and ROS imports deferred until their runtime boundary.
- Keep cleanup explicit in `marslab/main.py` for bridge, rclpy, and
  `SimulationApp` resources.
- Agent verification is offline only. Isaac GUI/headless behavior, physics,
  sensor streams, ROS topics, TF, AtmospherePanel, and cleanup are user-only
  validation and must remain unclaimed until observed by the user.
- Keep comments concise: document lifecycle ownership and ordering only.
