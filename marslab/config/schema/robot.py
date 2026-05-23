"""Robot schemas: odometry covariance, skid-steer drive, robot metadata.

Intra-file order: ``OdometryCovarianceConfig`` -> ``OdomPublisherConfig``
-> ``SkidSteerDriveConfig`` -> ``RobotConfig`` so the later models
reference the earlier ones without forward-ref strings.

Sensor configs (``CameraConfig`` / ``Lidar3DConfig`` / ``Lidar2DConfig``
/ ``IMUConfig``) flow through pydantic so every sensor parameter
(range, FOV, rotation rate, USD profile) is validated at load time
instead of hiding inside Isaac Sim's bundled JSON profiles.  All
configurable sensor parameters live in YAML, not in Python literals.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "CameraConfig",
    "ChassisConfig",
    "DepthSensorConfig",
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


# ``extra="forbid"`` is attached to every robot-schema BaseModel.  See
# ``marslab/config/schema/mars_env.py`` for the global rationale.  A
# typo like ``wheel_radious`` (sic) in a rover YAML would otherwise
# persist through scenario YAML loading because pydantic v2 defaults to
# ``extra="ignore"`` -- PhysX would then receive whatever Python literal
# the runtime happened to fall back to.


class OdometryCovarianceConfig(BaseModel):
    """Diagonal covariance values for the nav_msgs/Odometry publisher.

    ROS2 Odometry carries two 6x6 covariance matrices (pose + twist,
    each laid out in xyz + rpy order). Only the diagonal is populated
    here -- off-diagonal correlations are set to zero by the publisher.
    These variances are placeholders sized from typical wheel-encoder /
    IMU-fusion reference setups.

    All numeric covariance lives in YAML (no Python literals).
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
            "direct estimate of them -- SLAM should ignore those "
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
    """ROS2 odometry publisher settings.

    Without this block the ``frame_id="odom"`` / ``child_frame_id="base_link"``
    / ``queue_size=10`` values would sit as Python defaults inside
    ``marslab.ros2_bridge.odometry_publisher.create_odometry_publisher``.
    Declaring them here lets the rover's ``drive:`` tree drive all
    three publishers from one source, so the frame names stay aligned
    with the SLAM stack YAML by configuration instead of by convention.
    """

    model_config = ConfigDict(extra="forbid")

    frame_id: str = Field(
        default="odom",
        description=(
            "TF frame name emitted by the odometry publisher. Must match "
            "the SLAM stack's ``odom_frame`` parameter."
        ),
    )
    child_frame_id: str = Field(
        default="base_link",
        description=(
            "Child TF frame for the nav_msgs/Odometry message. Matches "
            "the SLAM stack's ``base_frame``."
        ),
    )
    queue_size: int = Field(default=10, ge=1, le=100, description="rclpy publisher QoS depth.")


# --- M2020 ballpark physics blocks -----------------------------------
# Three small models pin chassis mass / wheel mass / friction / inertia
# at the YAML layer so PhysX never sees the URDF auto-computed
# placeholders.  The rover spawn pipeline reads these blocks and applies
# them via ``UsdPhysics.MassAPI`` (chassis/wheel mass + diagonal inertia
# tensor) and ``UsdPhysics.MaterialAPI`` (wheel friction).  Default
# values are M2020 Perseverance ballpark (NOT exact) -- see
# ``configs/rover_m2020.yaml`` inline comments for citations.
# Override these defaults when configuring a different rover.


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
        ...,
        min_length=3,
        max_length=3,
        description=(
            "Chassis bounding box (length, width, height) in meters.  "
            "Documentation only -- the unit test recomputes the inertia "
            "tensor from this and asserts agreement with ``inertia_xx/yy/zz`` "
            "to 1 percent so a future YAML edit cannot silently desync "
            "the two.  Required; override per rover (M2020 Perseverance "
            "ballpark = [3.0, 2.7, 2.2])."
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
        ...,
        gt=0.0,
        description=(
            "Reference wheel diameter (metres). Documentation only -- "
            "does NOT replace the URDF-derived radius. Required; "
            "override per rover (M2020 Perseverance ballpark = 0.525 m, "
            "Heverly et al. 2013)."
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
    ``geometry_msgs/Twist`` into per-wheel angular velocities. Wheel
    radius, track width, and speed clamps all flow from YAML rather
    than being embedded in Python.

    The ``odom_covariance`` field lets the ``nav_msgs/Odometry``
    publisher pull its placeholder covariance matrices from the same
    block. The odometry publisher itself reads the same wheel-joint
    names declared here, so the FK pipeline and the IK pipeline always
    agree on the active wheel set.

    ``drive_damping`` / ``steer_stiffness`` / ``steer_damping`` are
    required schema fields rather than Python defaults so any rover
    config that omits a value fails at load time instead of silently
    shipping Python literals to DriveAPI tuning.
    """

    model_config = ConfigDict(extra="forbid")

    wheel_radius: float = Field(default=0.15, gt=0.0, description="Wheel radius in meters")
    track_width: float = Field(
        default=0.70, gt=0.0, description="Distance between left/right wheel centers (m)"
    )
    # The field names ``max_linear_velocity`` / ``max_angular_velocity``
    # match the YAML keys declared in ``configs/rover_m2020.yaml``
    # so a future ``SkidSteerDriveConfig.model_validate(control_cfg)``
    # call does not silently drop the speed clamps to the historical
    # ``max_linear_vel`` / ``max_angular_vel`` aliases.
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
            "commanded velocity when the upstream controller drops."
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
    # ``drive_damping`` / ``steer_stiffness`` / ``steer_damping`` are
    # required so any rover YAML that omits a value fails at load time
    # instead of silently shipping a Python literal to PhysX DriveAPI
    # tuning.
    drive_damping: float = Field(
        ...,
        gt=0.0,
        description=(
            "PhysX angular DriveAPI damping for velocity-mode wheel joints. "
            "Matches ``control.drive_damping`` in ``configs/rover_m2020.yaml`` "
            "(currently 1000.0 for the M2020 rover). Required; no Python fallback."
        ),
    )
    steer_stiffness: float = Field(
        ...,
        gt=0.0,
        description=(
            "PhysX angular DriveAPI stiffness for position-mode steering joints. "
            "Matches ``control.steer_stiffness`` in ``configs/rover_m2020.yaml`` "
            "(currently 50000.0 for the M2020 rover). Required."
        ),
    )
    steer_damping: float = Field(
        ...,
        gt=0.0,
        description=(
            "PhysX angular DriveAPI damping for position-mode steering joints. "
            "Matches ``control.steer_damping`` in ``configs/rover_m2020.yaml`` "
            "(currently 5000.0 for the M2020 rover). Required."
        ),
    )
    # The following four fields are required so any rover config that
    # omits one fails at load time rather than silently shipping a
    # Python literal to PhysX.
    drive_max_force: float = Field(
        ...,
        gt=0.0,
        description=(
            "Maximum PhysX DriveAPI torque for velocity-mode wheel joints (Nm). "
            "Matches ``control.drive_max_force`` in rover_m2020.yaml (currently "
            "1000000.0). Required."
        ),
    )
    steer_max_force: float = Field(
        ...,
        gt=0.0,
        description=(
            "Maximum PhysX DriveAPI torque for position-mode steering joints (Nm). "
            "Matches ``control.steer_max_force`` in rover_m2020.yaml (currently "
            "100000.0). Required."
        ),
    )
    suspension_damping: float = Field(
        ...,
        ge=0.0,
        description=(
            "PhysX DriveAPI damping for passive suspension joints. 0 leaves "
            "suspension undamped; positive values add viscous resistance. "
            "Matches ``control.suspension_damping`` in rover_m2020.yaml "
            "(currently 50.0). Required -- no Python fallback."
        ),
    )
    drive_type: Literal["acceleration", "force"] = Field(
        ...,
        description=(
            "PhysX DriveAPI mode. ``acceleration`` (recommended) auto-compensates "
            "for link mass / inertia, yielding consistent wheel response across "
            "rover variants. ``force`` applies raw torque and is sensitive to "
            "URDF inertia tuning. Matches ``control.drive_type`` in "
            "rover_m2020.yaml. Required."
        ),
    )
    odom_covariance: OdometryCovarianceConfig = Field(
        default_factory=OdometryCovarianceConfig,
        description=("Diagonal placeholder covariance for the nav_msgs/Odometry " "publisher."),
    )
    odom_publisher: OdomPublisherConfig = Field(
        default_factory=OdomPublisherConfig,
        description=(
            "ROS2 odometry publisher settings (frame_id / child_frame_id / "
            "queue_size).  Aligns the rover YAML with the SLAM stack "
            "frame names instead of relying on Python literal defaults in "
            "``odometry_publisher.py``."
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
# Sensor configs
#
# Every numeric sensor parameter (range, FOV, scan rate, USD profile)
# flows through pydantic.  Without these schemas,
# ``configs/rover_m2020.yaml`` would reference Isaac Sim bundled
# profile *names* only (``"Example_Rotary"``) while the numeric content
# of those profiles (range_min, horizontal_fov_deg, ...) sat hidden
# inside Isaac Sim's JSON files -- un-discoverable from the MarsLab repo
# and impossible to override at the YAML layer without forking the JSON.
#
# All configurable sensor parameters live in YAML, not Python literals.
#
# Backward compat: the old ``profile: "Example_Rotary"`` key is migrated
# to the new ``profile_name`` field by a ``mode="before"`` validator on
# each Lidar*Config so existing scenario YAMLs (cave_lava_tube etc.)
# continue to load without edits.  See ``_migrate_legacy_profile``.
# ---------------------------------------------------------------------------


class DepthSensorConfig(BaseModel):
    """Optional realistic depth simulation parameters.

    When present on the camera config and ``enabled=True``, the runtime
    applies the ``OmniSensorDepthSensorSingleViewAPI`` schema to the
    camera's render product, simulating a stereo pair from a single
    camera view (depth reprojected to the LEFT imager position).  This
    provides RealSense-style RGB-D alignment with realistic disparity
    noise, occlusion holes, and a confidence map that masks
    low-confidence pixels.  When absent or ``enabled=False``, the
    runtime falls back to the renderer's raw ``DistanceToImagePlane``
    AOV, which is noiseless and bypasses the stereo simulation.

    Schema source: ``isaacsim/extscache/
    omni.usd.schema.omni_sensors-0.0.0+69cbf6ad/usd_plugins/
    generatedSchema.usda`` (``OmniSensorDepthSensorSingleViewAPI``).
    The Python wrapper that documents each attribute is at
    ``isaacsim/exts/isaacsim.sensors.camera/isaacsim/sensors/camera/
    single_view_depth_sensor.py:46-503``.

    Default values mirror Intel RealSense D455 ballpark parameters
    (baseline 55 mm, max disparity 110 px) so a freshly-enabled config
    behaves like a stock RealSense without requiring per-rover tuning.
    For larger stereo rigs (M2020 Navcam baseline = 420 mm) override
    ``baseline_mm`` per scenario.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=False,
        description=(
            "Master switch.  ``False`` (default) preserves the v0.7 / v1.0 "
            "Path-1-only behaviour where depth comes from the renderer's "
            "noiseless ``DistanceToImagePlane`` AOV.  Set to ``True`` to "
            "enable the stereo-disparity simulation -- the runtime then "
            "applies the ``OmniSensorDepthSensorSingleViewAPI`` schema to "
            "the camera render product."
        ),
    )
    baseline_mm: float = Field(
        default=55.0,
        ge=1.0,
        le=500.0,
        description=(
            "Stereo baseline in millimetres.  RealSense D455 baseline = 55 "
            "mm; M2020 Navcam baseline ~ 420 mm.  Maps to USD attribute "
            "``omni:rtx:post:depthSensor:baselineMM``."
        ),
    )
    min_distance_m: float = Field(
        default=0.3,
        ge=0.0,
        description=(
            "Minimum reliable depth range in metres (samples below this "
            "are clamped to invalid).  Maps to ``omni:rtx:post:depthSensor:"
            "minDistance``."
        ),
    )
    max_distance_m: float = Field(
        default=10.0,
        gt=0.0,
        description=(
            "Maximum reliable depth range in metres (samples above this "
            "are clamped to invalid).  Maps to ``omni:rtx:post:depthSensor:"
            "maxDistance``."
        ),
    )
    noise_mean: float = Field(
        default=0.0,
        description=(
            "Gaussian noise mean (depth-relative) added to the simulated "
            "disparity.  Maps to ``omni:rtx:post:depthSensor:noiseMean``."
        ),
    )
    noise_sigma: float = Field(
        default=0.005,
        ge=0.0,
        description=(
            "Gaussian noise sigma (depth-relative).  RealSense literature "
            "places D435/D455 depth noise std-dev around 0.5 percent of "
            "range at typical distances, so 0.005 is a reasonable starting "
            "point.  Maps to ``omni:rtx:post:depthSensor:noiseSigma``."
        ),
    )
    confidence_threshold: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence threshold in [0, 1] for hole rejection -- samples "
            "with disparity confidence below this are dropped (NaN in the "
            "depth output).  Higher values yield sparser but cleaner "
            "depth.  Maps to ``omni:rtx:post:depthSensor:"
            "confidenceThreshold``."
        ),
    )
    max_disparity_pixel: float = Field(
        default=110.0,
        gt=0.0,
        description=(
            "Maximum disparity in pixels.  Caps the stereo search range so "
            "the simulator does not produce non-physical near-field depth.  "
            "RealSense D455 default = 110.  Maps to ``omni:rtx:post:"
            "depthSensor:maxDisparityPixel``."
        ),
    )

    @model_validator(mode="after")
    def check_distance_range(self) -> "DepthSensorConfig":
        """``max_distance_m`` must exceed ``min_distance_m``."""
        if self.max_distance_m <= self.min_distance_m:
            raise ValueError(
                f"max_distance_m ({self.max_distance_m}) must exceed "
                f"min_distance_m ({self.min_distance_m})"
            )
        return self


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

    Optional ``depth_sensor`` block toggles realistic stereo-disparity
    depth simulation via :class:`DepthSensorConfig`.
    """

    model_config = ConfigDict(extra="forbid")

    parent_link: str = Field(
        default="Body_Chassis",
        description=(
            "URDF link name the camera xform attaches to.  Used by the "
            "scenario loader to root ``camera_xform`` underneath the "
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
            "parent Xform -- placing xformOps on the Camera prim itself "
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
    depth_sensor: Optional[DepthSensorConfig] = Field(
        default=None,
        description=(
            "Optional stereo-disparity depth simulation block.  When "
            "present and ``enabled=True``, the runtime applies the "
            "``OmniSensorDepthSensorSingleViewAPI`` schema to the camera "
            "render product so depth output simulates a stereo pair "
            "(RealSense-style noise + occlusion holes + confidence map) "
            "instead of the renderer's noiseless ``DistanceToImagePlane`` "
            "AOV.  Defaults to ``None`` so existing scenarios preserve "
            "v0.7 / v1.0 behaviour without edits."
        ),
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
    """Internal base class for the spinning lidar configs; not part of
    the public surface.

    Concrete subclasses (:class:`Lidar3DConfig`, :class:`Lidar2DConfig`)
    add the dimension-specific FOV / resolution fields.  The shared
    backward-compat migration (legacy ``profile`` -> ``profile_name``)
    lives on the subclasses so each one logs an unambiguous source
    class name when it fires.

    Field semantics: the five core YAML fields below
    (``range_min``, ``range_max``, ``horizontal_fov_deg``,
    ``vertical_fov_deg``, ``rotation_rate_hz``) are
    **runtime-applied** via Isaac Sim 5.1's
    ``OmniSensorGenericLidarCoreAPI`` schema -- after the bundled
    profile JSON loads through ``LidarRtx(config_file_name=...)``,
    :func:`marslab.sensors.sensor_spawner._apply_lidar_runtime_overrides`
    writes the YAML values directly onto the OmniLidar prim's USD
    attributes (``omni:sensor:Core:nearRangeM`` / ``farRangeM`` /
    ``scanRateBaseHz`` / ``validStartAzimuthDeg`` /
    ``validEndAzimuthDeg`` / ``emitterState:s001:elevationDeg``).
    The two resolution fields (``horizontal_resolution_deg``,
    ``vertical_resolution_deg``) remain documentation-only because the
    underlying schema derives them from ``reportRateBaseHz`` and the
    emitter table layout; per-emitter regeneration from a single
    angular-spacing scalar is left as a v1.5+ follow-up.

    Centering policy is fixed: ``horizontal_fov_deg`` < 360 yields a
    front-centered partial sweep (azimuth ``[360 - fov/2, fov/2]``);
    ``vertical_fov_deg`` linearly remaps the existing emitter
    elevation array around its current centre, so a 16-beam Velodyne
    bundled profile keeps its 16 channels but compresses or expands
    the vertical span uniformly.
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
            "**Runtime-applied** via OmniSensorGenericLidarCoreAPI schema: "
            "written to ``omni:sensor:Core:nearRangeM`` on the OmniLidar prim "
            "after the bundled profile loads.  Must satisfy "
            "``range_min < range_max``."
        ),
    )
    range_max: float = Field(
        ...,
        gt=0.0,
        description=(
            "Maximum reportable range in meters.  **Runtime-applied** via "
            "OmniSensorGenericLidarCoreAPI schema: written to "
            "``omni:sensor:Core:farRangeM`` on the OmniLidar prim."
        ),
    )
    horizontal_fov_deg: float = Field(
        ...,
        gt=0.0,
        le=360.0,
        description=(
            "Horizontal field of view in degrees.  360 = full rotary scan; "
            "values < 360 yield a front-centered partial sweep (azimuth "
            "``[360 - fov/2, fov/2]``).  **Runtime-applied** via "
            "OmniSensorGenericLidarCoreAPI schema: written to "
            "``omni:sensor:Core:validStartAzimuthDeg`` and "
            "``validEndAzimuthDeg`` on the OmniLidar prim."
        ),
    )
    horizontal_resolution_deg: float = Field(
        ...,
        gt=0.0,
        description=(
            "Angular spacing between horizontal samples in degrees.  "
            "**Descriptive only** — Isaac Sim derives the actual sample "
            "spacing from ``reportRateBaseHz`` and the bundled profile's "
            "per-emitter tables; per-emitter regeneration from this "
            "scalar is a v1.5+ follow-up."
        ),
    )
    rotation_rate_hz: float = Field(
        ...,
        gt=0.0,
        description=(
            "Sensor rotation rate in Hz.  **Runtime-applied** via "
            "OmniSensorGenericLidarCoreAPI schema: cast to ``uint`` and "
            "written to ``omni:sensor:Core:scanRateBaseHz`` on the "
            "OmniLidar prim."
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
            "Name of an Isaac-Sim bundled RTX-LiDAR USD asset to use for "
            "the lidar prim (e.g. ``Example_Rotary``).  Defaults to "
            "``profile_name`` when unset.  Set to a different value (e.g. "
            "``Velodyne_VLP16``) to swap the LiDAR model without editing "
            "Python.  Verify the asset name against Isaac Sim 5.1's "
            "bundled asset list -- see ``configs/sensors/`` for the "
            "curated presets."
        ),
    )
    variant: Optional[str] = Field(
        default=None,
        description=(
            "Optional variant selection within a USD asset that bundles "
            "multiple LiDAR specs (e.g. Ouster ``OS1.usd`` carries "
            "``OS1_REV6_128ch10hz1024res`` etc.).  Forwarded to "
            "``IsaacSensorCreateRtxLidar(variant=...)``; ``None`` selects "
            "the asset default."
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

    Legacy YAMLs declared ``sensors.lidar_3d.profile: "Example_Rotary"``;
    the field is now named ``profile_name`` so the symmetry with
    ``profile_json_path`` and ``usd_profile`` is obvious in the schema.
    Backward compat is preserved with this ``mode="before"`` shim -- a
    ``profile`` key is renamed to ``profile_name`` only when
    ``profile_name`` is not also present, so a YAML that already
    migrated wins over a stale ``profile`` field.
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
    The default values in ``configs/rover_m2020.yaml`` mirror
    Isaac Sim's ``Example_Rotary`` JSON profile (16-beam, 30 deg
    vertical FOV, 1.875 deg vertical step) so migrating from name-only
    to fully-declared YAML is behaviour-preserving.

    See :class:`_LidarBaseConfig` for the runtime-application policy
    of every numeric field on this model.
    """

    vertical_fov_deg: float = Field(
        ...,
        gt=0.0,
        le=180.0,
        description=(
            "Vertical field of view in degrees.  **Runtime-applied** via "
            "OmniSensorGenericLidarCoreAPI schema: linearly remaps the "
            "existing ``omni:sensor:Core:emitterState:s001:elevationDeg`` "
            "array around its current centre so the bundled profile's "
            "channel count is preserved while the vertical span "
            "expands or compresses to match this value."
        ),
    )
    vertical_resolution_deg: float = Field(
        ...,
        gt=0.0,
        description=(
            "Angular spacing between vertical beams in degrees.  "
            "**Descriptive only** — derived implicitly from "
            "``vertical_fov_deg`` and the bundled profile's emitter "
            "count; explicit per-emitter regeneration is a v1.5+ "
            "follow-up."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_profile_key(cls, data: object) -> object:
        return _migrate_legacy_profile(data)


class Lidar2DConfig(_LidarBaseConfig):
    """2D LaserScan LiDAR configuration (single-ring planar scan).

    Inherits the shared mount + range + horizontal-FOV + USD-profile
    fields.  No vertical fields because a 2D planar scanner has a
    single beam.

    See :class:`_LidarBaseConfig` for the descriptive-only nature of
    every numeric field on this model.
    """

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_profile_key(cls, data: object) -> object:
        return _migrate_legacy_profile(data)


class IMUConfig(BaseModel):
    """IMU sensor mount + frame configuration.

    The IMU does NOT carry any range / sample-rate fields here -- its
    publish rate is driven by ``ros2.rates.imu`` (see
    ``configs/rover_m2020.yaml``) which is also the IMUSensor's
    ``frequency`` parameter.  Keeping those two values in one place
    avoids the Mars-gravity drift that surfaces when the schema and the
    runtime defaults disagree.
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

    Mirrors the ``sensors:`` block in ``configs/rover_m2020.yaml``.
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
            "the 3D LiDAR for SLAM."
        ),
    )
    lidar_2d: Optional[Lidar2DConfig] = Field(
        default=None,
        description=(
            "Optional 2D LaserScan LiDAR for SLAM / costmap consumers.  "
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

    type: str = Field(description="Robot type identifier (e.g., 'rover')")
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
            "one robot of the same type (e.g. ``/World/rover_0``)."
        ),
    )
    drive: SkidSteerDriveConfig | None = Field(
        default=None,
        description=(
            "Skid-steer drive parameters for cmd_vel -> wheel control. "
            "Required for rovers that are teleoperable via /cmd_vel."
        ),
    )

    @model_validator(mode="after")
    def check_robot_path(self) -> "RobotConfig":
        """At least one of urdf_path or usd_asset_path must be provided."""
        if self.urdf_path is None and self.usd_asset_path is None:
            raise ValueError("At least one of urdf_path or usd_asset_path must be provided")
        return self
