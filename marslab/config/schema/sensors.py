"""Sensor schemas: IMU probe + sensor subsystem wrapper.

Split from marslab.config.schema (R2, 2026-04-22). Intra-file order:
``SensorImuConfig`` -> ``SensorsConfig``.
"""

from pydantic import BaseModel, Field

__all__ = ["SensorImuConfig", "SensorsConfig"]


class SensorImuConfig(BaseModel):
    """Wk1 IMU live-gravity probe parameters (Phase B #23 / B4).

    Read by ``marslab.sensors.imu_probe.run_live_gravity_probe`` to
    drive the THE critical test (PLAN.md §6.2): spawn the rover under
    Mars gravity, settle, sample the attached IMU, and assert that the
    measured z-axis acceleration matches ``target_gz`` within
    ``tolerance``. No numeric Mars physics value lives in Python -- all
    four fields flow from ``configs/mars_env.yaml`` via this block.
    """

    sample_count: int = Field(
        default=20,
        ge=1,
        description="Number of IMU samples averaged for the gravity verdict.",
    )
    settle_steps: int = Field(
        default=50,
        ge=0,
        description=(
            "Physics steps to advance before sampling begins, so wheel "
            "contact oscillations damp out before the accelerometer is "
            "read."
        ),
    )
    target_gz: float = Field(
        default=3.72,
        ge=0.0,
        le=15.0,
        description=(
            "Expected downward accelerometer magnitude in m/s^2. Defaults "
            "to Mars surface gravity -- keep synchronised with "
            "mars_env.gravity unless the probe is deliberately tuned for "
            "a different body."
        ),
    )
    tolerance: float = Field(
        default=0.05,
        gt=0.0,
        description=(
            "Absolute tolerance on |mean_z - target_gz| AND on |mean_x| "
            "and |mean_y| for the probe to report pass=True."
        ),
    )
    stddev_z_max: float = Field(
        default=0.10,
        gt=0.0,
        description=(
            "Upper bound on per-sample stddev of the z acceleration "
            "before the reading is rejected as 'rover still bouncing'. "
            "Catches the settle_steps-too-low failure mode where "
            "mean_z is on target but the probe averaged a noisy "
            "contact oscillation."
        ),
    )
    mount_link: str = Field(
        default="imu_link",
        min_length=1,
        description=(
            "URDF link name to mount the probe IMU on. Override when a "
            "different rover URDF uses a non-REP-145 link identifier. "
            "Not a physical constant -- the value is a string label "
            "that identifies a prim path under the rover root, so G5 is "
            "honored via this YAML-overridable field."
        ),
    )
    fallback_link: str = Field(
        default="base_link",
        min_length=1,
        description=(
            "Backup link name used when ``mount_link`` is absent on the "
            "imported USD stage. The URDF importer occasionally drops "
            "empty links, and the probe falls back here instead of "
            "raising so the gate can still run on legacy URDFs."
        ),
    )
    # Phase C2 (#34, 2026-04-15): IMU ROS2 publisher fields.
    # Wired into marslab.ros2_bridge.imu_node.IMUPublisher so the
    # interactive GUI scene exposes /<robot_name>/imu/data and the
    # SLAM/Nav stack can consume it. Phase B's run_live_gravity_probe
    # is now disabled (the probe was a one-shot offline gate); the
    # gate now runs against the live ROS2 topic during a manual
    # `ros2 topic echo` after the user launches scripts/run_scene_interactive.py.
    publish_rate_hz: float = Field(
        default=100.0,
        gt=0.0,
        le=1000.0,
        description=(
            "ROS2 publish rate in Hz for the IMU sensor_msgs/Imu topic. "
            "Defaults to 100 Hz which matches the cmd_vel/odometry "
            "watchdog budget at physics_dt=1/200 s. The publisher timer "
            "fires at 1/publish_rate_hz seconds."
        ),
    )
    frame_id: str = Field(
        default="imu_link",
        min_length=1,
        description=(
            "REP-105 ``header.frame_id`` for the published Imu msg. "
            "Must match a TF frame broadcast by tf_broadcaster.py so "
            "downstream consumers can resolve the IMU pose against "
            "base_link."
        ),
    )
    topic_name: str = Field(
        default="/{robot_name}/imu/data",
        min_length=1,
        description=(
            "ROS2 topic template. ``{robot_name}`` is substituted with "
            "the rover instance name (e.g. ``rover_0``) at publisher "
            "construction time. Override to escape the templating by "
            "passing a literal path that does not contain ``{robot_name}``."
        ),
    )


class SensorsConfig(BaseModel):
    """Sensor-subsystem configuration container (Phase B #23 / B4).

    Thin wrapper that nests the per-sensor-kind config blocks under a
    single top-level ``sensors`` YAML key. Today only the Wk1 IMU probe
    lives here; additional subsystems (stereo calibration, LiDAR noise
    models) can join without re-flattening the schema.
    """

    imu: SensorImuConfig = Field(default_factory=SensorImuConfig)
