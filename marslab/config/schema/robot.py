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

Sprint Day 2 Task D + E (2026-04-25) added ``CameraConfig`` /
``Lidar3DConfig`` / ``Lidar2DConfig`` / ``IMUConfig`` plus the
``SensorsConfig`` parent so every sensor parameter (range, FOV, rotation
rate, USD profile) flows through pydantic instead of hiding inside Isaac
Sim's bundled JSON profiles.  G5 strict: zero numeric sensor constants
survive in Python.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "CameraConfig",
    "ChassisConfig",
    "IMUConfig",
    "Lidar2DConfig",
    "Lidar3DConfig",
    "OdometryCovarianceConfig",
    "OdomPublisherConfig",
    "RobotConfig",
    "SensorsConfig",
    "SkidSteerDriveConfig",
    "SuspensionConfig",
    "WheelsConfig",
]


# Reviewer 2 #12 (2026-04-24): ``extra="forbid"`` attached to every
# robot-schema BaseModel.  See ``marslab/config/schema/mars_env.py`` for
# the global rationale.  A typo like ``wheel_radious`` (sic) in a rover
# YAML previously persisted through ``load_and_validate`` because
# pydantic v2 defaulted to ``extra="ignore"`` — PhysX then received
# whatever Python literal the runtime happened to fall back to.


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

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

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


# --- Day 2 Task B (2026-04-26): M2020 ballpark physics blocks ---------
# Three small models pin chassis mass / wheel mass / friction / inertia at
# the YAML layer so PhysX never sees the URDF auto-computed placeholders.
# The rover spawn pipeline reads these blocks and applies them via
# ``UsdPhysics.MassAPI`` (chassis/wheel mass + diagonal inertia tensor)
# and ``UsdPhysics.MaterialAPI`` (wheel friction).  Values are M2020
# ballpark (NOT exact) — see ``configs/robots/rover_m2020.yaml`` inline
# comments for citations.


class ChassisConfig(BaseModel):
    """Chassis mass + diagonal inertia override (M2020 ballpark).

    The URDF emits an auto-computed inertia tensor that does NOT reflect
    the real M2020 mass distribution; this block replaces it with values
    derived from the chassis bounding box (3.0 m x 2.7 m x 2.2 m at
    1025 kg).  The runtime override is applied via
    ``UsdPhysics.MassAPI.GetMassAttr().Set(mass)`` and the three diagonal
    inertia entries via ``GetDiagonalInertiaAttr().Set(Vec3f(ixx, iyy, izz))``
    in ``marslab.robots.rover.apply_chassis_physics``.

    Validation bounds:
        * ``mass`` in (0, 5000] kg — M2020 is 1025 kg; cap at 5 t leaves
          headroom for future heavier rovers without admitting absurd
          values.
        * Inertia entries must all be > 0 (PhysX rejects zero-inertia
          articulation roots).
    """

    model_config = ConfigDict(extra="forbid")

    mass: float = Field(
        ...,
        gt=0.0,
        le=5000.0,
        description=(
            "Chassis dry mass in kilograms.  M2020 actual = 1025 kg "
            "(NASA fact sheet, mars.nasa.gov/mars2020/spacecraft/rover/)."
        ),
    )
    inertia_xx: float = Field(
        ...,
        gt=0.0,
        description=(
            "Principal moment of inertia about the body X axis (kg*m^2).  "
            "Computed from chassis bounding box (W^2 + H^2) * mass / 12."
        ),
    )
    inertia_yy: float = Field(
        ...,
        gt=0.0,
        description=(
            "Principal moment of inertia about the body Y axis (kg*m^2).  "
            "Computed from (L^2 + H^2) * mass / 12."
        ),
    )
    inertia_zz: float = Field(
        ...,
        gt=0.0,
        description=(
            "Principal moment of inertia about the body Z axis (kg*m^2).  "
            "Computed from (L^2 + W^2) * mass / 12."
        ),
    )
    bbox_lwh: list[float] = Field(
        default=[3.0, 2.7, 2.2],
        min_length=3,
        max_length=3,
        description=(
            "Chassis bounding box (length, width, height) in meters.  "
            "Documentation only — the unit test recomputes the inertia "
            "tensor from this and asserts agreement with ``inertia_xx/yy/zz`` "
            "to 1 % so a future YAML edit cannot silently desync the two."
        ),
    )


class WheelsConfig(BaseModel):
    """Per-wheel mass / inertia / friction override.

    Applied to every wheel link discovered under the chassis articulation.
    Friction lands on a PhysX material attached to the wheel collider; mass
    + inertia land on the wheel ``RigidBodyAPI`` via ``MassAPI``.

    Validation bounds:
        * ``radius`` and ``width`` strictly positive.
        * Friction coefficients in [0, 2] (Mars regolith literature
          rarely exceeds 1.0; cap at 2 to allow experimental values
          without admitting nonsense).
        * Inertia entries strictly positive.
        * ``friction_static`` >= ``friction_dynamic`` so the rover does
          not creep on slope hold.
    """

    model_config = ConfigDict(extra="forbid")

    radius: float = Field(
        ...,
        gt=0.0,
        description=(
            "Wheel rolling radius in meters.  Must match "
            "``control.wheel_radius``; the runtime IK pipeline reads "
            "the latter, this block exists for the dynamics overrides."
        ),
    )
    diameter_reference: float = Field(
        default=0.525,
        gt=0.0,
        description=(
            "M2020 actual wheel diameter (0.525 m, Heverly et al. 2013).  "
            "Documentation only — does NOT replace the URDF-derived radius."
        ),
    )
    mass: float = Field(
        ...,
        gt=0.0,
        le=100.0,
        description=("Per-wheel mass in kilograms (M2020 ballpark estimate " "= 9.0 kg)."),
    )
    width: float = Field(
        ...,
        gt=0.0,
        description="Wheel width / cylinder height in meters (M2020 ballpark = 0.40 m).",
    )
    inertia_spin: float = Field(
        ...,
        gt=0.0,
        description=(
            "Inertia about the wheel spin axis (kg*m^2).  m * r^2 / 2 for "
            "a uniform solid cylinder."
        ),
    )
    inertia_transverse: float = Field(
        ...,
        gt=0.0,
        description=(
            "Inertia about the two transverse axes (kg*m^2).  "
            "m * (3 r^2 + h^2) / 12 for a uniform solid cylinder."
        ),
    )
    friction_static: float = Field(
        ...,
        ge=0.0,
        le=2.0,
        description=(
            "Static friction coefficient between wheel and terrain.  "
            "Mars regolith literature midpoint = 0.6 (Sullivan et al. 2017, "
            "Heverly et al. 2013).  Must be >= friction_dynamic."
        ),
    )
    friction_dynamic: float = Field(
        ...,
        ge=0.0,
        le=2.0,
        description=(
            "Dynamic / sliding friction coefficient.  Lower than static "
            "so the rover does not creep on a slope hold (typical "
            "0.5 for Mars regolith)."
        ),
    )
    restitution: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Coefficient of restitution.  0 = no bounce on regolith.",
    )

    @model_validator(mode="after")
    def check_friction_ordering(self) -> "WheelsConfig":
        """Static friction must be >= dynamic friction."""
        if self.friction_static < self.friction_dynamic:
            raise ValueError(
                f"friction_static ({self.friction_static}) must be >= "
                f"friction_dynamic ({self.friction_dynamic}) so the rover "
                f"does not creep on slope hold"
            )
        return self


class SuspensionConfig(BaseModel):
    """Rocker-bogie passive joint damping override.

    The pre-existing ``control.suspension_damping`` covered every rocker /
    bogie joint with a single number (50 N*m*s/rad).  This block separates
    the two so the differential beam can be tuned independently of the
    bogie pivot — the rocker carries the long arm and benefits from
    higher viscous damping than the bogie.  Both still default to passive
    viscous damping (no spring component) since v1.0 sticks with rigid
    rocker-bogie kinematics (no terramechanics until v3.0).
    """

    model_config = ConfigDict(extra="forbid")

    rocker_damping: float = Field(
        ...,
        ge=0.0,
        description=(
            "Passive viscous damping on the primary rocker arm joints "
            "(N*m*s/rad).  M2020 ballpark = 75."
        ),
    )
    bogie_damping: float = Field(
        ...,
        ge=0.0,
        description=(
            "Passive viscous damping on the bogie sub-arm joints "
            "(N*m*s/rad).  M2020 ballpark = 50; matches the legacy "
            "``control.suspension_damping`` value."
        ),
    )


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

    model_config = ConfigDict(extra="forbid")

    wheel_radius: float = Field(default=0.15, gt=0.0, description="Wheel radius in meters")
    track_width: float = Field(
        default=0.70, gt=0.0, description="Distance between left/right wheel centers (m)"
    )
    # Reviewer 2 finding (A2, Day 1, 2026-04-25): the legacy field names
    # ``max_linear_vel`` / ``max_angular_vel`` did NOT match the YAML
    # keys ``max_linear_velocity`` / ``max_angular_velocity`` declared in
    # ``configs/robots/rover_m2020.yaml`` (lines 107-108).  ``run_stage4.py``
    # (L295-296) read the YAML keys via raw ``dict.get`` and bypassed the
    # schema entirely (``~/MarsLab/tmp/schema_bypass_finding.md``).  The
    # rename below realigns schema + YAML so a future
    # ``SkidSteerDriveConfig.model_validate(control_cfg)`` call no longer
    # silently drops the speed clamps.
    max_linear_velocity: float = Field(
        default=1.0, gt=0.0, description="Upper bound on commanded linear velocity (m/s)"
    )
    max_angular_velocity: float = Field(
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


# ---------------------------------------------------------------------------
# Sensor configs (Sprint Day 2 Task D + E, 2026-04-25)
#
# Goal: every numeric sensor parameter (range, FOV, scan rate, USD profile)
# flows through pydantic.  Before this commit, ``configs/robots/rover_m2020.yaml``
# referenced Isaac Sim bundled profile *names* (``"Example_Rotary"``) and the
# numeric content of those profiles (range_min, horizontal_fov_deg, ...) was
# hidden inside Isaac Sim's JSON files — un-discoverable from the MarsLab repo
# and impossible to override at the YAML layer without forking the JSON.
#
# G5 strict: zero hardcoded sensor numerics in Python after this change.
#
# Backward compat: the old ``profile: "Example_Rotary"`` key is migrated to
# the new ``profile_name`` field by a ``mode="before"`` validator on each
# Lidar*Config so existing scenario YAMLs (cave_lava_tube etc.) continue to
# load without edits.  See ``Lidar3DConfig._migrate_legacy_profile``.
# ---------------------------------------------------------------------------


class CameraConfig(BaseModel):
    """RGB-D camera mount + RTX optics parameters.

    Mount pose follows the same ``parent_link`` / ``local_translation`` /
    ``local_orientation_rpy_deg`` (ZYX intrinsic, degrees) convention as the
    LiDAR and IMU configs so the YAML is uniform across sensors.
    Optical parameters (``resolution`` / ``focal_length`` / ``clipping_range``)
    were previously read directly out of the rover YAML by
    :func:`marslab.sensors.sensor_spawner.spawn_sensors` without schema
    validation; promoting them here lets ``extra="forbid"`` reject typos and
    out-of-range values at load time.
    """

    model_config = ConfigDict(extra="forbid")

    parent_link: str = Field(
        default="Body_Chassis",
        description=(
            "URDF link name the camera xform attaches to.  Used by the "
            "scenario loader to root ``stage1_camera_xform`` underneath the "
            "rigid-body prim path; not consumed directly by ``spawn_sensors``."
        ),
    )
    local_translation: list[float] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="[x, y, z] camera offset in parent-link frame, meters.",
    )
    local_orientation_rpy_deg: list[float] = Field(
        default=[0.0, 0.0, 0.0],
        min_length=3,
        max_length=3,
        description=(
            "[roll, pitch, yaw] in degrees (ZYX intrinsic).  Applied via a "
            "parent Xform — placing xformOps on the Camera prim itself "
            "corrupts the RTX depth pipeline (see "
            "``marslab/sensors/sensor_spawner.py`` docstring)."
        ),
    )
    resolution: list[int] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="[width, height] in pixels.",
    )
    focal_length: float = Field(
        ...,
        gt=0.0,
        description=(
            "Focal length in millimetres (Isaac Sim Camera API expects cm "
            "internally; ``spawn_sensors`` divides by 10 before calling "
            "``camera.set_focal_length``)."
        ),
    )
    clipping_range: list[float] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="[near, far] camera clip planes in meters.",
    )

    @model_validator(mode="after")
    def check_clipping_range(self) -> "CameraConfig":
        near, far = self.clipping_range
        if near <= 0.0:
            raise ValueError(f"clipping_range near plane must be > 0, got {near}")
        if far <= near:
            raise ValueError(f"clipping_range far ({far}) must exceed near ({near})")
        return self


class _LidarBaseConfig(BaseModel):
    """Shared mount + range + USD-profile fields for 2D / 3D LiDAR configs.

    Concrete subclasses (:class:`Lidar3DConfig`, :class:`Lidar2DConfig`) add
    the dimension-specific FOV / resolution fields.  The shared backward-compat
    migration (legacy ``profile`` -> ``profile_name``) lives on the subclasses
    so each one logs an unambiguous source class name when it fires.

    Field categories (Sprint Day 3 Task H1, 2026-04-25):

    * **Runtime-overridable** — these YAML values are written into a
      runtime-generated JSON copy of the bundled profile by
      :func:`marslab.sensors.sensor_spawner._write_runtime_lidar_profile`
      and reach Isaac Sim via ``LidarRtx(config_file_name=...)``:

      - ``range_min``         -> ``profile.nearRangeM``
      - ``range_max``         -> ``profile.farRangeM``
      - ``rotation_rate_hz``  -> ``profile.scanRateBaseHz``

    * **Descriptive only** — these YAML values document the bundled
      profile's behaviour and are validated by pydantic, but they do
      NOT flow into Isaac Sim at runtime because the bundled JSON
      encodes per-emitter azimuth / elevation tables that cannot be
      regenerated from two scalars:

      - ``horizontal_fov_deg``
      - ``vertical_fov_deg`` (3D only)
      - ``horizontal_resolution_deg``
      - ``vertical_resolution_deg`` (3D only)

      To actually change those four values at runtime, swap to a
      different bundled profile via ``profile_name`` (e.g. ``Velodyne_VLS128``
      for higher channel count) or supply a custom JSON via
      ``profile_json_path`` (escape hatch).  Auto-generation of
      ``emitterStates`` from FOV+resolution is a v1.5 follow-up.
    """

    model_config = ConfigDict(extra="forbid")

    parent_link: str = Field(
        default="Body_Chassis",
        description="URDF link name the LiDAR xform attaches to.",
    )
    local_translation: list[float] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="[x, y, z] LiDAR offset in parent-link frame, meters.",
    )
    local_orientation_rpy_deg: list[float] = Field(
        default=[0.0, 0.0, 0.0],
        min_length=3,
        max_length=3,
        description="[roll, pitch, yaw] in degrees (ZYX intrinsic).",
    )
    range_min: float = Field(
        ...,
        gt=0.0,
        description=(
            "Minimum reportable range in meters (returns < this are dropped). "
            "**Runtime-overridable** — written into ``profile.nearRangeM`` of "
            "a runtime JSON copy of the bundled profile by "
            "``marslab.sensors.sensor_spawner._write_runtime_lidar_profile`` "
            "and forwarded to Isaac Sim via ``LidarRtx.config_file_name``."
        ),
    )
    range_max: float = Field(
        ...,
        gt=0.0,
        description=(
            "Maximum reportable range in meters.  **Runtime-overridable** — "
            "patched into ``profile.farRangeM`` at runtime (see ``range_min``)."
        ),
    )
    horizontal_fov_deg: float = Field(
        ...,
        gt=0.0,
        le=360.0,
        description=(
            "Horizontal field of view in degrees.  360 = full rotary scan; "
            "values < 360 model a forward-facing fan.  **Descriptive only** — "
            "this YAML field documents the bundled profile's coverage but is "
            "NOT injected into Isaac Sim at runtime.  The bundled JSON "
            "encodes per-emitter azimuth tables that cannot be regenerated "
            "from this scalar; to actually change horizontal FOV swap to a "
            "different ``profile_name`` or supply a custom ``profile_json_path``."
        ),
    )
    horizontal_resolution_deg: float = Field(
        ...,
        gt=0.0,
        description=(
            "Angular spacing between horizontal samples in degrees.  "
            "**Descriptive only** — see ``horizontal_fov_deg`` note above; "
            "auto-generation of per-emitter tables is v1.5 follow-up."
        ),
    )
    rotation_rate_hz: float = Field(
        ...,
        gt=0.0,
        description=(
            "Sensor rotation rate in Hz (also referred to as ``scanRateBaseHz`` "
            "in Isaac Sim's bundled JSON profiles).  Drives the ROS2 scan "
            "publish rate when the LiDAR is forwarded through the sensor "
            "graph.  **Runtime-overridable** — patched into "
            "``profile.scanRateBaseHz`` at runtime."
        ),
    )
    profile_name: Optional[str] = Field(
        default=None,
        description=(
            "Name of an Isaac-Sim bundled RTX-LiDAR JSON profile "
            "(e.g. ``Example_Rotary``).  Passed to "
            "``LidarRtx(config_file_name=...)``.  Mutually exclusive with "
            "``profile_json_path`` (escape hatch below)."
        ),
    )
    profile_json_path: Optional[str] = Field(
        default=None,
        description=(
            "Optional escape hatch: filesystem path to a custom RTX-LiDAR "
            "JSON profile.  When set, ``spawn_sensors`` passes this path to "
            "``LidarRtx(config_file_name=...)`` instead of ``profile_name``.  "
            "For power users only — the canonical config-driven workflow is "
            "to expose every parameter as YAML and reference a stock profile "
            "name."
        ),
    )
    usd_profile: Optional[str] = Field(
        default=None,
        description=(
            "Task E (2026-04-25): name of an Isaac-Sim bundled RTX-LiDAR "
            "USD asset to use for the lidar prim (e.g. "
            "``Example_Rotary``).  Defaults to ``profile_name`` when unset, "
            "matching pre-Task-E behaviour.  Set to a different value (e.g. "
            "``Velodyne_VLP16``) to swap the LiDAR model without editing "
            "Python.  Verify the asset name against Isaac Sim 5.1's bundled "
            "asset list — see ``configs/sensors/`` for the curated presets."
        ),
    )

    @model_validator(mode="after")
    def check_range_and_profile(self) -> "_LidarBaseConfig":
        if self.range_max <= self.range_min:
            raise ValueError(
                f"range_max ({self.range_max}) must exceed range_min ({self.range_min})"
            )
        if self.profile_name is None and self.profile_json_path is None:
            raise ValueError(
                "Lidar config requires either ``profile_name`` (bundled JSON "
                "profile) or ``profile_json_path`` (custom escape hatch). "
                "Both are absent — set at least one."
            )
        if self.profile_name is not None and self.profile_json_path is not None:
            raise ValueError(
                "Lidar config has both ``profile_name`` and "
                "``profile_json_path``; pick one. The runtime cannot pass two "
                "config_file_name values to ``LidarRtx``."
            )
        return self


def _migrate_legacy_profile(data: object) -> object:
    """Map the legacy ``profile`` key onto ``profile_name``.

    Pre-Task-D YAMLs declared ``sensors.lidar_3d.profile: "Example_Rotary"``;
    Task D renamed the field to ``profile_name`` so the symmetry with
    ``profile_json_path`` and ``usd_profile`` is obvious in the schema.
    Backward compat is preserved with this ``mode="before"`` shim — a
    ``profile`` key is renamed to ``profile_name`` only when ``profile_name``
    is not also present, so a YAML that already migrated wins over a stale
    ``profile`` field.
    """
    if not isinstance(data, dict):
        return data
    if "profile" in data and "profile_name" not in data:
        data = dict(data)
        data["profile_name"] = data.pop("profile")
    return data


class Lidar3DConfig(_LidarBaseConfig):
    """3D rotary LiDAR (Velodyne / Ouster style) configuration.

    Adds vertical FOV + vertical angular resolution to the shared base.
    The default values in ``configs/robots/rover_m2020.yaml`` mirror Isaac
    Sim's ``Example_Rotary`` JSON profile (16-beam, 30 deg vertical FOV,
    1.875 deg vertical step) so the migration from name-only to fully-
    declared YAML is behaviour-preserving.

    See :class:`_LidarBaseConfig` for the runtime-overridable vs
    descriptive-only field categorisation (Sprint Day 3 Task H1).
    """

    vertical_fov_deg: float = Field(
        ...,
        gt=0.0,
        le=180.0,
        description=(
            "Vertical field of view in degrees.  **Descriptive only** — "
            "the bundled JSON encodes per-emitter elevation tables; to "
            "actually change vertical FOV swap to a different "
            "``profile_name`` or supply a custom ``profile_json_path``."
        ),
    )
    vertical_resolution_deg: float = Field(
        ...,
        gt=0.0,
        description=(
            "Angular spacing between vertical beams in degrees.  "
            "**Descriptive only** — see ``vertical_fov_deg`` note above."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_profile_key(cls, data: object) -> object:
        return _migrate_legacy_profile(data)


class Lidar2DConfig(_LidarBaseConfig):
    """2D LaserScan LiDAR configuration (single-ring planar scan).

    Inherits the shared mount + range + horizontal-FOV + USD-profile fields.
    No vertical fields because a 2D planar scanner has a single beam.

    See :class:`_LidarBaseConfig` for the runtime-overridable vs
    descriptive-only field categorisation (Sprint Day 3 Task H1).
    """

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_profile_key(cls, data: object) -> object:
        return _migrate_legacy_profile(data)


class IMUConfig(BaseModel):
    """IMU sensor mount + frame configuration.

    The IMU does NOT carry any range / sample-rate fields here — its publish
    rate is driven by ``ros2.rates.imu`` (see ``configs/robots/rover_m2020.yaml``
    line 54) which is also the IMUSensor's ``frequency`` parameter.  Keeping
    those two values in one place avoids the Mars-gravity drift that
    Reviewer 2 caught when the schema and the runtime defaults disagreed.
    """

    model_config = ConfigDict(extra="forbid")

    parent_link: str = Field(
        default="Body_Chassis",
        description="URDF link name the IMU attaches to.",
    )
    local_translation: list[float] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="[x, y, z] IMU offset in parent-link frame, meters.",
    )
    local_orientation_rpy_deg: list[float] = Field(
        default=[0.0, 0.0, 0.0],
        min_length=3,
        max_length=3,
        description="[roll, pitch, yaw] in degrees (ZYX intrinsic).",
    )


class SensorsConfig(BaseModel):
    """Aggregate of camera + 3D LiDAR + 2D LiDAR + IMU sensor configs.

    Mirrors the ``sensors:`` block in ``configs/robots/rover_m2020.yaml``.
    ``lidar_2d`` is optional because some scenarios (e.g. the spacecraft
    landing scene where the 2D scan is replaced by a different sensor) may
    legitimately omit it; the runtime guards on ``sensors_cfg.get("lidar_2d")``
    accordingly.
    """

    model_config = ConfigDict(extra="forbid")

    camera: CameraConfig = Field(
        ...,
        description="RGB-D camera mount + optics.",
    )
    lidar_3d: Lidar3DConfig = Field(
        ...,
        description=(
            "3D rotary RTX LiDAR.  Required because every v1.0 scenario uses "
            "the 3D LiDAR for SLAM/Nav2."
        ),
    )
    lidar_2d: Optional[Lidar2DConfig] = Field(
        default=None,
        description=(
            "Optional 2D LaserScan LiDAR for slam_toolbox / Nav2 costmap.  "
            "Cave / canyon scenarios that rely on the 2D scan declare it; "
            "scenarios that don't may omit the block."
        ),
    )
    imu: IMUConfig = Field(
        ...,
        description="IMU mount + frame.",
    )


class RobotConfig(BaseModel):
    """Single robot configuration."""

    model_config = ConfigDict(extra="forbid")

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
