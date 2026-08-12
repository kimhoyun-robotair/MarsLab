"""ROS2 bridge schema: OmniGraph prim path + rclpy subscription tuning.

Two literals that would otherwise sit as module constants / Python
defaults inside the ROS2 bridge are surfaced here as pydantic fields on
``Ros2BridgeConfig``:

* ``GRAPH_PATH = "/World/Stage3ROS2Graph"`` previously declared in
  ``marslab/ros2_bridge/sensor_graph.py``.  As a bare module-level
  constant the only way to relocate the action graph was a source
  edit.
* ``queue_size=10`` previously hardcoded in
  ``marslab/ros2_bridge/cmd_vel_subscriber.create_cmd_vel_subscriber``.
  The caller (rclpy_integration) never overrode it, so a noisy
  upstream controller could not back-pressure through YAML.

Both are declared here.  ``configs/rover_m2020.yaml``
(``rover.ros2`` block) gains an optional ``graph_path`` +
``cmd_vel_queue_size`` pair.  Absent values fall back to the
historical constants via the pydantic defaults so existing scenarios
keep loading.

The schema enforces prim-path hygiene (non-empty, ``/``-prefixed, no
internal whitespace) with ``model_validator`` so a typo like
``" /World/Graph"`` fails at load time rather than surfacing as an
opaque ``omni.graph.core`` failure inside Isaac Sim.

QoS profiles for every topic are also surfaced into the schema.
Without these fields ``marslab/ros2_bridge/*.py`` would not import
``rclpy.qos`` at all and every publisher/subscriber would be created
with the rclpy default profile (``RELIABLE`` + ``VOLATILE`` +
``KEEP_LAST`` depth=10).  Those defaults mismatch real-world ROS2
pipelines and cause silent message drop in mixed RELIABLE /
BEST_EFFORT environments:

* ``/cmd_vel``: ``teleop_twist_keyboard`` ships ``BEST_EFFORT``; a
  ``RELIABLE`` subscriber drops every keypress.  Default ``reliable``
  here (REP-2003 SystemDefault), surfaced in YAML so a teleop-heavy
  scenario can flip to ``best_effort``.
* ``/odom``: ``nav_msgs/Odometry`` is REP-2003 SystemDefault =
  ``RELIABLE``.  Kept reliable.  Depth stays at 10 (one odom per
  control cycle is sufficient).
* ``/imu``, ``/camera/*``, ``/lidar/*``: Sensor streams follow the
  ROS 2 ``sensor_data`` convention (``BEST_EFFORT`` + depth 5).
  RViz default LaserScan displays use ``BEST_EFFORT``; shipping
  ``RELIABLE`` here would silently drop every scan.
* ``/tf`` + ``/tf_static``: TF broadcasters are ``RELIABLE`` with
  ``TRANSIENT_LOCAL`` durability so late-joining subscribers still
  latch the static sensor frames.  Depth 100 matches ``tf2_ros``
  defaults.

The ``QoSProfileConfig`` model is reused by all four fields; values
are mapped to ``rclpy.qos.QoSProfile`` at runtime via
:mod:`marslab.ros2_bridge.qos` (lazy import so unit tests run without
rclpy on the path).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["QoSProfileConfig", "Ros2BridgeConfig"]


# Both models below pin ``extra="forbid"`` so a misspelled QoS policy
# string (``"best_efforts"``) or a stray ``graph_path_override`` key
# fails at YAML load time rather than being silently dropped by
# pydantic v2's default ``extra="ignore"``.


class QoSProfileConfig(BaseModel):
    """rclpy QoS profile -- YAML-facing view of ``rclpy.qos.QoSProfile``.

    Mirrors the four fields that matter for SLAM round-tripping:
    ``reliability``, ``durability``, ``history``, ``depth``.  Liveliness
    / deadline are intentionally omitted -- v1.0 does not exercise them
    and exposing unused knobs in YAML invites drift.

    The string enums match the rclpy policy names (lower-cased) so a
    reader familiar with rclpy docs can map YAML to code without a
    lookup table.  Invalid strings raise ``pydantic.ValidationError``
    at config load time -- the whole point of surfacing QoS in YAML is
    to fail loudly before Isaac Sim boots.
    """

    model_config = ConfigDict(extra="forbid")

    reliability: Literal["reliable", "best_effort"] = Field(
        default="reliable",
        description=(
            "rclpy ReliabilityPolicy. ``reliable`` = retry until ACK "
            "(matches REP-2003 SystemDefault). ``best_effort`` = fire "
            "and forget (the sensor_data convention; required by "
            "LaserScan subscribers that default to BEST_EFFORT)."
        ),
    )
    durability: Literal["volatile", "transient_local"] = Field(
        default="volatile",
        description=(
            "rclpy DurabilityPolicy. ``volatile`` drops undelivered "
            "samples at shutdown. ``transient_local`` latches the "
            "latest sample for late-joining subscribers and is the "
            "required setting for ``/tf_static``; without it a "
            "subscriber that boots after the bridge never receives "
            "the camera / LiDAR / IMU transforms."
        ),
    )
    history: Literal["keep_last", "keep_all"] = Field(
        default="keep_last",
        description=(
            "rclpy HistoryPolicy. ``keep_last`` truncates to ``depth``. "
            "``keep_all`` tries to deliver every sample (DDS-limited). "
            "v1.0 uses ``keep_last`` everywhere."
        ),
    )
    depth: int = Field(
        default=10,
        ge=1,
        le=1000,
        description=(
            "rclpy QoS history depth. Upper bound 1000 prevents runaway "
            "queues that would swamp rclpy / FastDDS. sensor_data "
            "convention is 5; REP-2003 SystemDefault is 10."
        ),
    )


def _cmd_vel_qos_default() -> QoSProfileConfig:
    """``/cmd_vel`` default: RELIABLE + KEEP_LAST(10).

    Matches REP-2003 SystemDefault.
    Declared as a module-level factory (not an inline lambda) so the
    rationale is attached to the function name and the pydantic
    ``default_factory`` signature stays readable.
    """
    return QoSProfileConfig(reliability="reliable", durability="volatile", depth=10)


def _odom_qos_default() -> QoSProfileConfig:
    """``/odom`` default: RELIABLE + KEEP_LAST(10).

    ``nav_msgs/Odometry`` REP-2003 SystemDefault.  Kept shallow (10)
    because consumers only read the latest pose per cycle — deeper
    queues just add latency on recovery.
    """
    return QoSProfileConfig(reliability="reliable", durability="volatile", depth=10)


def _sensor_qos_default() -> QoSProfileConfig:
    """``/imu``, ``/camera/*``, ``/lidar/*`` default: BEST_EFFORT + KEEP_LAST(5).

    ROS 2 ``sensor_data`` convention (``rclpy.qos.qos_profile_sensor_data``).
    LaserScan subscribers default to BEST_EFFORT; shipping RELIABLE
    would mean 0 messages received on any Stage-3 run.  Depth 5 is
    the rclpy sensor_data default.
    """
    return QoSProfileConfig(reliability="best_effort", durability="volatile", depth=5)


def _tf_qos_default() -> QoSProfileConfig:
    """``/tf`` + ``/tf_static`` default: RELIABLE + TRANSIENT_LOCAL + KEEP_LAST(100).

    Matches ``tf2_ros::StaticTransformBroadcaster`` defaults.
    Transient-local durability is mandatory for ``/tf_static`` — it is
    the whole reason static TFs survive a late-joining subscriber.
    Depth 100 tracks the tf2 library default.
    """
    return QoSProfileConfig(reliability="reliable", durability="transient_local", depth=100)


class Ros2BridgeConfig(BaseModel):
    """Configuration for the Stage-3 ROS2 bridge plumbing.

    Mirrors the ``rover.ros2`` YAML sub-block.  Only the keys that
    used to live as Python constants are declared here; the existing
    free-form ``namespace`` / ``topics`` / ``rates`` /
    ``odom_publisher`` keys continue to flow through ``init_rclpy_side``
    as an untyped dict because they are already covered by legacy
    tests.  A later pass may promote the remaining dict keys.
    """

    model_config = ConfigDict(extra="forbid")

    graph_path: str = Field(
        default="/World/Stage3ROS2Graph",
        description=(
            "USD prim path for the Stage-3 OmniGraph action graph.  The Isaac Sim stage "
            "must not already contain a prim at this path.  Surfaces what would otherwise "
            "be a hardcoded ``GRAPH_PATH`` constant in "
            "``marslab/ros2_bridge/sensor_graph.py``, so scenarios with unusual stage "
            "layouts (multi-robot, custom Stage layouts) can relocate the graph without "
            "a source edit."
        ),
    )
    cmd_vel_queue_size: int = Field(
        default=10,
        ge=1,
        le=1000,
        description=(
            "rclpy subscription queue depth for ``/<ns>/cmd_vel``.  Surfaces what would "
            "otherwise be a hardcoded ``queue_size=10`` in "
            "``marslab/ros2_bridge/cmd_vel_subscriber.py`` so tuning that needs a "
            "deeper buffer (bursty upstream controller output) can be expressed in YAML.  "
            "Upper bound 1000 prevents misconfigurations that would swamp rclpy with "
            "unbounded queues."
        ),
    )
    publish_pointcloud2: bool = Field(
        default=True,
        description=(
            "When ``True`` the Stage-3 OmniGraph appends a second "
            "``isaacsim.ros2.bridge.ROS2CameraHelper`` node fed off the depth "
            "render product with ``inputs:type='depth_pcl'`` so the RGB-D "
            "camera publishes a ``sensor_msgs/PointCloud2`` topic at the "
            "depth camera rate (RealSense D435/D455-style behaviour). The public "
            "ROS2CameraHelper API routes the ``depth_pcl`` token through "
            "``ROS2PublishPointCloud`` with "
            "``DistanceToImagePlane`` as the source render variable, so depth "
            "+ camera intrinsics are converted into XYZ points inside the "
            "writer.  Topic name comes from ``rover.ros2.topics.points`` "
            "(default ``depth/points``); ``frameId`` reuses ``camera_link`` so "
            "the publisher joins the existing static TF chain instead of "
            "introducing an unattached optical frame.  Default ``True`` "
            "matches the RealSense convention -- flip to ``False`` for "
            "headless data-gen scenarios where the extra bandwidth is not "
            "wanted."
        ),
    )
    publish_camera_info: bool = Field(
        default=True,
        description=(
            "When ``True`` the Stage-3 OmniGraph appends a "
            "``isaacsim.ros2.bridge.ROS2CameraInfoHelper`` node fed off the "
            "RGB render product so the camera publishes a "
            "``sensor_msgs/CameraInfo`` topic alongside ``rgb/image_raw``.  "
            "The helper auto-derives K / P / R / D matrices and width / "
            "height from the USD ``Camera`` prim's focal length, aperture, "
            "and clipping range -- intrinsics are NOT authored in YAML, "
            "the camera prim is the single source of truth. The public "
            "ROS2CameraInfoHelper API automates the CameraInfo pipeline for "
            "monocular and stereo cameras. Topic name comes from "
            "``rover.ros2.topics.camera_info`` (default ``rgb/camera_info``); "
            "``frameId`` reuses ``camera_optical_frame`` so consumers like "
            "``image_proc``, ``depth_image_proc``, RTAB-Map and ORB-SLAM3 "
            "see geometry consistent with the RGB / Depth / PointCloud2 "
            "headers (REP-105 optical convention).  Default ``True`` "
            "matches the canonical RGB-D ROS workflow -- visual SLAM and "
            "image rectification packages refuse to run without "
            "``CameraInfo``.  Flip to ``False`` for headless data-gen "
            "scenarios that consume raw images via Replicator instead of "
            "the ROS image pipeline.  Reuses the existing ``RPCamera`` "
            "render product so the GPU cost is one extra encode pass per "
            "frame, not a second render."
        ),
    )
    publish_robot_description: bool = Field(
        default=True,
        description=(
            "When ``True`` the Stage-3 bridge publishes the rover URDF on "
            "``/<ns>/robot_description`` with TRANSIENT_LOCAL + RELIABLE + "
            "KEEP_LAST(1) so a late-joining RViz subscriber latches it.  "
            "Default ``True`` matches the canonical ROS workflow; flip to "
            "``False`` for headless data-gen scenarios that do not need "
            "RViz RobotModel display."
        ),
    )
    publish_odom_tf: bool = Field(
        default=False,
        description=(
            "When ``True`` the rclpy-side odometry publisher broadcasts "
            "``odom -> <base_frame>`` on ``/tf``.  Default ``False`` "
            "leaves ``odom -> <base_frame>`` to a downstream visual SLAM "
            "stack (RTAB-Map ``rgbd_odometry``, ORB-SLAM3, etc.) so the "
            "rover's PhysX ground-truth pose does not collide with the "
            "SLAM stack's pose estimate on the same transform.  Flip to "
            "``True`` for wheel-only configurations (no visual SLAM) or "
            "for debugging where ground-truth odom is desired.  Running "
            "two publishers on ``odom -> <base_frame>`` yields jitter "
            "that breaks downstream consumers; pick exactly one."
        ),
    )
    # Defaults below match the current runtime behaviour: the rover
    # publishes ``sensor_msgs/JointState`` on ``<ns>/joint_states`` and
    # a ROS-side ``robot_state_publisher`` derives ``/tf`` from URDF
    # link declarations (no Isaac-side nameOverride / rename).
    publish_joint_states: bool = Field(
        default=True,
        description=(
            "When ``True`` (default) the OmniGraph wires "
            "``isaacsim.ros2.bridge.ROS2PublishJointState`` so the rover "
            "articulation publishes ``sensor_msgs/JointState`` on "
            "``<ns>/joint_states``.  A ROS-side ``robot_state_publisher`` "
            "consuming this topic + the latched ``/robot_description`` "
            "produces the full link-tree TF on the canonical ``/tf`` "
            "topic, replacing the prior ``ROS2PublishTransformTree`` "
            "(``PubTF``) + ``topic_tools relay`` workflow.  Set "
            "``False`` to restore the legacy ``/tf_raw`` PubTF wiring "
            "(e.g. for a v0.7 scenario that relies on the relay).  "
            "Topic name comes from ``rover.ros2.topics.joint_states`` "
            "(default ``joint_states``)."
        ),
    )
    enable_isaac_nameoverride: bool = Field(
        default=False,
        description=(
            "When ``True`` the runtime applies "
            "``isaac:nameOverride='base_link'`` to the rover articulation "
            "root prim and creates an ``odom`` anchor prim with "
            "``isaac:nameOverride='odom'``.  Required ONLY when the "
            "OmniGraph ``ROS2PublishTransformTree`` (``PubTF``) is the "
            "TF authority (``publish_joint_states=False``) -- in that "
            "mode PubTF reads the override to produce ``odom -> "
            "base_link`` frames.  C3+ default ``False`` because the "
            "C2 ``robot_state_publisher`` workflow reads frame names "
            "directly from the URDF link declarations and never "
            "consults ``isaac:nameOverride``.  The SLAM stack's "
            "``base_frame`` parameter accepts any frame name "
            "(``Body_Chassis``, ``base_link``, etc.) so frame-name "
            "aliasing is handled at the SLAM launch layer, not in USD."
        ),
    )
    rename_root_to_base_link: bool = Field(
        default=False,
        description=(
            "When ``True`` the URDF published on ``/robot_description`` "
            "is rewritten so the root link name becomes ``base_link`` "
            "(the JPL m2020 URDF root is ``Body_Chassis``).  C3+ "
            "default ``False`` keeps the URDF link names verbatim so "
            "the URDF and the OmniGraph-published joint names share a "
            "single source of truth.  Downstream stacks (SLAM, "
            "RTAB-Map) accept any base frame name via launch parameter "
            "(``base_frame: Body_Chassis``), so renaming is no longer "
            "necessary.  Set ``True`` when integrating a third-party "
            "ROS package that hardcodes the ``base_link`` literal."
        ),
    )
    sensor_parent_frame_id: str = Field(
        default="Body_Chassis",
        description=(
            "Parent frame_id used when broadcasting the static sensor "
            "TFs (camera_link / lidar_link / scan_frame / imu_link).  "
            "C3+ default ``Body_Chassis`` matches the URDF root link "
            "name so the rclpy-published sensor offsets attach to the "
            "``robot_state_publisher``-published articulation chain "
            "(``Body_Chassis -> Body_Wheel*``).  Override to "
            "``base_link`` when running the legacy "
            "``rename_root_to_base_link=True`` rewrite path or any "
            "third-party stack that hardcodes the ``base_link`` "
            "literal.  SLAM launch params (``base_frame``) must "
            "agree with the value chosen here."
        ),
        min_length=1,
    )
    cmd_vel_qos: QoSProfileConfig = Field(
        default_factory=_cmd_vel_qos_default,
        description=(
            "QoS profile for the ``/<ns>/cmd_vel`` subscription.  Default matches "
            "REP-2003 SystemDefault (RELIABLE + KEEP_LAST depth=10).  Flip to "
            "``best_effort`` when driving the rover primarily with "
            "``teleop_twist_keyboard`` (ships BEST_EFFORT)."
        ),
    )
    odom_qos: QoSProfileConfig = Field(
        default_factory=_odom_qos_default,
        description=(
            "QoS profile for the ``/<ns>/odom`` publisher.  ``nav_msgs/Odometry`` "
            "REP-2003 SystemDefault (RELIABLE + KEEP_LAST depth=10).  Kept shallow "
            "because consumers only read the latest pose per control cycle."
        ),
    )
    sensor_qos: QoSProfileConfig = Field(
        default_factory=_sensor_qos_default,
        description=(
            "QoS profile for sensor streams (``/imu``, ``/camera/*``, "
            "``/lidar/*``, ``/scan``).  Matches the ROS 2 ``sensor_data`` "
            "convention (BEST_EFFORT + KEEP_LAST depth=5).  LaserScan "
            "subscribers default to BEST_EFFORT -- shipping RELIABLE "
            "here would yield 0 messages received."
        ),
    )
    tf_qos: QoSProfileConfig = Field(
        default_factory=_tf_qos_default,
        description=(
            "QoS profile for ``/tf`` and ``/tf_static``.  RELIABLE + "
            "TRANSIENT_LOCAL + KEEP_LAST depth=100 matches ``tf2_ros`` "
            "defaults and is required for late-joining subscribers to "
            "latch static sensor frames."
        ),
    )

    @model_validator(mode="after")
    def check_graph_path(self) -> "Ros2BridgeConfig":
        """Enforce USD prim-path hygiene on ``graph_path``.

        Rules: non-empty, must start with ``/`` (USD absolute prim path convention),
        no internal whitespace (whitespace in USD prim paths is a syntax error
        downstream inside ``omni.graph.core``).
        """
        value = self.graph_path
        if not value:
            raise ValueError("graph_path must be a non-empty string")
        if not value.startswith("/"):
            raise ValueError(
                f"graph_path must start with '/' (USD absolute prim path); got {value!r}"
            )
        if any(ch.isspace() for ch in value):
            raise ValueError(f"graph_path must not contain whitespace; got {value!r}")
        return self
