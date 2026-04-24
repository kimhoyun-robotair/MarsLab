"""Robot schemas: odometry covariance, skid-steer drive, robot metadata.

Split from marslab.config.schema (R2, 2026-04-22). Intra-file order:
``OdometryCovarianceConfig`` -> ``OdomPublisherConfig`` ->
``SkidSteerDriveConfig`` -> ``RobotConfig`` so the later models reference
the earlier ones without forward-ref strings.

R3 (2026-04-22) added ``OdomPublisherConfig`` (frame_id / child_frame_id /
queue_size migration from ``odometry_publisher.py:45-47``) and
``RobotConfig.prim_path`` (``/World/quadruped`` literal migration from
``quadruped.py:47``).

R2-4a (2026-04-23) promoted ``drive_max_force`` / ``steer_max_force`` /
``suspension_damping`` / ``drive_type`` from dead ``.get(..., literal)``
fallbacks in ``marslab.robots.drive_api_setup`` (L118-123, L189) to
required ``SkidSteerDriveConfig`` fields. ``configs/robots/rover_m2020.yaml``
already declares all four, so making them required catches future robot
YAMLs that omit a value at load time instead of silently shipping Python
literals to PhysX DriveAPI tuning.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

__all__ = [
    "OdometryCovarianceConfig",
    "OdomPublisherConfig",
    "RobotConfig",
    "SkidSteerDriveConfig",
]


class OdometryCovarianceConfig(BaseModel):
    """Diagonal covariance values for the nav_msgs/Odometry publisher.

    ROS2 Odometry carries two 6x6 covariance matrices (pose + twist,
    each laid out in xyz + rpy order). For v1.0 we only populate the
    diagonal — off-diagonal correlations are set to zero by the
    publisher. These variances are placeholders sized from typical
    wheel-encoder / IMU-fusion reference setups; real numbers come
    from the SLAM/Nav2 experiments in Wk3+.

    Wk2 #6 (2026-04-14, task #17) introduced this block so G5 is
    honored — no numeric covariance lives in Python.
    """

    pose_diag: list[float] = Field(
        default=[1e-3, 1e-3, 1e6, 1e6, 1e6, 1e-2],
        min_length=6,
        max_length=6,
        description=(
            "Diagonal of the 6x6 pose covariance matrix in (x, y, z, "
            "roll, pitch, yaw) order. z / roll / pitch entries are "
            "large (1e6) because a planar skid-steer rover has no "
            "direct estimate of them — SLAM/Nav2 should ignore those "
            "axes entirely via the inflated variance."
        ),
    )
    twist_diag: list[float] = Field(
        default=[1e-3, 1e-3, 1e6, 1e6, 1e6, 1e-2],
        min_length=6,
        max_length=6,
        description=(
            "Diagonal of the 6x6 twist covariance matrix in (vx, vy, "
            "vz, wx, wy, wz) order. Same rationale as pose_diag: the "
            "non-planar components are masked with 1e6."
        ),
    )

    @model_validator(mode="after")
    def check_non_negative(self) -> "OdometryCovarianceConfig":
        """Variance must be non-negative for every diagonal entry."""
        for name, values in (
            ("pose_diag", self.pose_diag),
            ("twist_diag", self.twist_diag),
        ):
            for i, v in enumerate(values):
                if v < 0.0:
                    raise ValueError(f"{name}[{i}] must be >= 0, got {v}")
        return self


class OdomPublisherConfig(BaseModel):
    """ROS2 odometry publisher settings (R3 G5 §3.5).

    Before R3 the ``frame_id="odom"`` / ``child_frame_id="base_link"`` /
    ``queue_size=10`` values sat as Python defaults inside
    ``marslab.ros2_bridge.odometry_publisher.create_odometry_publisher``.
    The sole call site (``marslab/ros2_bridge/__init__.py:105-110``)
    never overrode them, so the frame names had to match the slam_toolbox
    and Nav2 YAMLs by convention instead of by configuration. Declaring
    the block here lets the rover's ``drive:`` tree in
    ``configs/mars_env.yaml`` drive all three publishers from one source.
    """

    frame_id: str = Field(
        default="odom",
        description=(
            "TF frame name emitted by the odometry publisher. Must match "
            "``odom_frame`` in ``configs/slam/slam_toolbox_async.yaml`` "
            "and the equivalent parameter in ``configs/nav2/nav2_params.yaml``."
        ),
    )
    child_frame_id: str = Field(
        default="base_link",
        description=(
            "Child TF frame for the nav_msgs/Odometry message. Matches "
            "``base_frame`` in the SLAM config and the Nav2 costmap root."
        ),
    )
    queue_size: int = Field(default=10, ge=1, le=100, description="rclpy publisher QoS depth.")


class SkidSteerDriveConfig(BaseModel):
    """Skid-steer drive geometry and actuation limits.

    Used by ``marslab.ros2_bridge.cmd_vel_subscriber`` to convert
    ``geometry_msgs/Twist`` into per-wheel angular velocities. Wk2 #4
    (2026-04-14) added these fields so G5 (no hardcoded constants) is
    honored: wheel radius, track width, and speed clamps all flow from
    YAML rather than being embedded in Python.

    Wk2 #6 (2026-04-14, task #17) added the ``odom_covariance`` field
    so the ``nav_msgs/Odometry`` publisher can pull its placeholder
    covariance matrices from the same block. The odometry publisher
    itself reads the same wheel-joint names declared here, so the FK
    pipeline and the IK pipeline always agree on the active wheel set.

    R2-A3 (2026-04-22) promoted ``drive_damping`` / ``steer_stiffness`` /
    ``steer_damping`` from dead Python defaults in
    ``marslab/robots/rover.py`` (lines 260-264, 322-324) to required
    schema fields. The pre-R2-A3 Python defaults (100000 / 50000 / 5000)
    never matched the runtime YAML values (1000 / 50000 / 5000 in
    ``configs/robots/rover_m2020.yaml``) — the ``dict.get(..., default)``
    fallback was dead code masking a G5 violation. Required here so any
    future rover config that omits the values fails at load time instead
    of silently shipping Python literals to DriveAPI tuning.
    """

    wheel_radius: float = Field(default=0.15, gt=0.0, description="Wheel radius in meters")
    track_width: float = Field(
        default=0.70, gt=0.0, description="Distance between left/right wheel centers (m)"
    )
    max_linear_vel: float = Field(
        default=1.0, gt=0.0, description="Upper bound on commanded linear velocity (m/s)"
    )
    max_angular_vel: float = Field(
        default=1.5, gt=0.0, description="Upper bound on commanded yaw rate (rad/s)"
    )
    cmd_vel_timeout_s: float = Field(
        default=0.5,
        gt=0.0,
        description=(
            "Safety watchdog timeout in seconds. If no /cmd_vel message has "
            "arrived within this window, the subscriber zeros every wheel "
            "velocity so the rover does not keep cruising at the last "
            "commanded velocity when the Nav2 controller_server drops. "
            "Wk2 #7b / task #18."
        ),
    )
    left_wheel_joints: list[str] = Field(
        default=["joint_fl", "joint_ml", "joint_rl"],
        description="Articulation joint names for left wheel bank",
    )
    right_wheel_joints: list[str] = Field(
        default=["joint_fr", "joint_mr", "joint_rr"],
        description="Articulation joint names for right wheel bank",
    )
    # R2-A3 (2026-04-22): G5 — drive_damping / steer_stiffness /
    # steer_damping required.  Dead Python defaults previously lived at
    # marslab/robots/rover.py:260-264 and 322-324 with values that did
    # NOT match configs/robots/rover_m2020.yaml — leaving them optional
    # here would hide the same mismatch on any future robot YAML.
    drive_damping: float = Field(
        ...,
        gt=0.0,
        description=(
            "PhysX angular DriveAPI damping for velocity-mode wheel joints. "
            "Matches ``control.drive_damping`` in ``configs/robots/rover_m2020.yaml`` "
            "(currently 1000.0 for the M2020 rover). Required since R2-A3 "
            "(2026-04-22); no Python fallback."
        ),
    )
    steer_stiffness: float = Field(
        ...,
        gt=0.0,
        description=(
            "PhysX angular DriveAPI stiffness for position-mode steering joints. "
            "Matches ``control.steer_stiffness`` in ``configs/robots/rover_m2020.yaml`` "
            "(currently 50000.0 for the M2020 rover). Required since R2-A3."
        ),
    )
    steer_damping: float = Field(
        ...,
        gt=0.0,
        description=(
            "PhysX angular DriveAPI damping for position-mode steering joints. "
            "Matches ``control.steer_damping`` in ``configs/robots/rover_m2020.yaml`` "
            "(currently 5000.0 for the M2020 rover). Required since R2-A3."
        ),
    )
    # R2-4a (2026-04-23): the following four fields were previously dead
    # ``control_cfg.get(key, <python-literal>)`` fallbacks inside
    # ``marslab.robots.drive_api_setup`` (L118-123, L189).  rover_m2020.yaml
    # already declares all four (lines 129-135), so promoting them to
    # required catches any future rover config that omits one at load time
    # rather than silently shipping the Python literal to PhysX.
    drive_max_force: float = Field(
        ...,
        gt=0.0,
        description=(
            "Maximum PhysX DriveAPI torque for velocity-mode wheel joints (Nm). "
            "Matches ``control.drive_max_force`` in rover_m2020.yaml (currently "
            "1000000.0). Required since R2-4a (2026-04-23)."
        ),
    )
    steer_max_force: float = Field(
        ...,
        gt=0.0,
        description=(
            "Maximum PhysX DriveAPI torque for position-mode steering joints (Nm). "
            "Matches ``control.steer_max_force`` in rover_m2020.yaml (currently "
            "100000.0). Required since R2-4a."
        ),
    )
    suspension_damping: float = Field(
        ...,
        ge=0.0,
        description=(
            "PhysX DriveAPI damping for passive suspension joints. 0 leaves "
            "suspension undamped; positive values add viscous resistance. "
            "Matches ``control.suspension_damping`` in rover_m2020.yaml "
            "(currently 50.0). Required since R2-4a — no Python fallback."
        ),
    )
    drive_type: Literal["acceleration", "force"] = Field(
        ...,
        description=(
            "PhysX DriveAPI mode. ``acceleration`` (recommended) auto-compensates "
            "for link mass / inertia, yielding consistent wheel response across "
            "rover variants. ``force`` applies raw torque and is sensitive to "
            "URDF inertia tuning. Matches ``control.drive_type`` in "
            "rover_m2020.yaml. Required since R2-4a."
        ),
    )
    odom_covariance: OdometryCovarianceConfig = Field(
        default_factory=OdometryCovarianceConfig,
        description=(
            "Diagonal placeholder covariance for the nav_msgs/Odometry "
            "publisher (Wk2 #6 / task #17)."
        ),
    )
    odom_publisher: OdomPublisherConfig = Field(
        default_factory=OdomPublisherConfig,
        description=(
            "ROS2 odometry publisher settings (frame_id / child_frame_id / "
            "queue_size). Introduced in R3 (2026-04-22) to migrate literals "
            "from ``odometry_publisher.py`` and align the rover YAML with "
            "slam_toolbox / Nav2 frame names."
        ),
    )

    @model_validator(mode="after")
    def check_wheel_joints(self) -> "SkidSteerDriveConfig":
        """Left and right banks must have the same non-zero joint count."""
        if not self.left_wheel_joints or not self.right_wheel_joints:
            # Keep this error message split across two source lines for
            # readability. black would otherwise collapse it into a single
            # 104-char physical line via implicit string concatenation,
            # which is parser-valid but visually confusing.
            # fmt: off
            raise ValueError(
                "left_wheel_joints and right_wheel_joints must each list "
                "at least one joint name"
            )
            # fmt: on
        if len(self.left_wheel_joints) != len(self.right_wheel_joints):
            raise ValueError(
                f"left_wheel_joints ({len(self.left_wheel_joints)}) and "
                f"right_wheel_joints ({len(self.right_wheel_joints)}) must "
                f"have matching lengths for a symmetric skid-steer rover"
            )
        return self


class RobotConfig(BaseModel):
    """Single robot configuration."""

    type: str = Field(description="Robot type identifier (e.g., 'rover', 'quadruped')")
    urdf_path: str | None = Field(default=None, description="Path to custom URDF file")
    usd_asset_path: str | None = Field(default=None, description="Path to built-in USD asset")
    spawn_position: list[float] = Field(
        default=[0.0, 0.0, 0.5], min_length=3, max_length=3, description="[x, y, z] meters"
    )
    sensor_config_paths: list[str] = Field(default_factory=list)
    prim_path: str | None = Field(
        default=None,
        description=(
            "USD prim path for the spawned robot. ``None`` falls back to "
            "``/World/{type}`` so existing single-instance scenarios keep "
            "their historical prim layout. Override when spawning more than "
            "one robot of the same type (e.g. ``/World/quadruped_0``). "
            "Introduced in R3 (2026-04-22) to migrate the ``/World/quadruped``"
            " literal from ``marslab/robots/quadruped.py:47``."
        ),
    )
    drive: SkidSteerDriveConfig | None = Field(
        default=None,
        description=(
            "Skid-steer drive parameters for cmd_vel → wheel control. Required "
            "for rovers that are teleoperable via /cmd_vel (Wk2 #4)."
        ),
    )

    @model_validator(mode="after")
    def check_robot_path(self) -> "RobotConfig":
        """At least one of urdf_path or usd_asset_path must be provided."""
        if self.urdf_path is None and self.usd_asset_path is None:
            raise ValueError("At least one of urdf_path or usd_asset_path must be provided")
        return self
