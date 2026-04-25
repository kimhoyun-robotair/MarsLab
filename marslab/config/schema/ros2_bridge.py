"""ROS2 bridge schema: OmniGraph prim path + rclpy subscription tuning.

R4-5 extension (2026-04-23) promoted two literals that had been sitting
as module constants / Python defaults inside the ROS2 bridge into a
pydantic ``Ros2BridgeConfig`` block:

* ``GRAPH_PATH = "/World/Stage3ROS2Graph"`` in
  ``marslab/ros2_bridge/sensor_graph.py:35`` was a bare module-level
  constant — every scenario shipped the same prim path and the only
  way to relocate the action graph was a source edit.
* ``queue_size=10`` in
  ``marslab/ros2_bridge/cmd_vel_subscriber.create_cmd_vel_subscriber``
  was a Python default that the caller (rclpy_integration) never
  overrode, so a noisy Nav2 controller_server could not back-pressure
  through YAML.

Both are now declared here.  ``configs/robots/rover_m2020.yaml``
(``rover.ros2`` block) gains an optional ``graph_path`` +
``cmd_vel_queue_size`` pair.  Absent values fall back to the historical
constants via the pydantic defaults so existing scenarios keep loading.

The schema enforces prim-path hygiene (non-empty, ``/``-prefixed, no
internal whitespace) with ``model_validator`` so a typo like
``" /World/Graph"`` fails at load time rather than surfacing as an
opaque ``omni.graph.core`` failure inside Isaac Sim.

Reviewer 2 #04 (2026-04-24) promoted **QoS profiles** for every topic
into the schema.  Before this change ``marslab/ros2_bridge/*.py`` did
not import ``rclpy.qos`` at all; every publisher and subscriber was
created with the rclpy default profile (``RELIABLE`` + ``VOLATILE`` +
``KEEP_LAST`` depth=10).  The defaults mismatch real-world SLAM/Nav2
pipelines and caused silent message drop in mixed RELIABLE /
BEST_EFFORT environments:

* ``/cmd_vel``: ``teleop_twist_keyboard`` ships ``BEST_EFFORT``; a
  ``RELIABLE`` subscriber on our side drops every keypress.  We keep
  the profile ``reliable`` here (Nav2 ``controller_server`` default)
  but surface it as YAML so a teleop-heavy scenario can flip to
  ``best_effort``.
* ``/odom``: ``nav_msgs/Odometry`` is REP-2003 SystemDefault =
  ``RELIABLE``.  Kept reliable.  Depth stays at 10 because Nav2
  accepts one odom per control cycle.
* ``/imu``, ``/camera/*``, ``/lidar/*``: Sensor streams follow the
  ROS 2 ``sensor_data`` convention (``BEST_EFFORT`` + depth 5).
  slam_toolbox and RViz default LaserScan displays use
  ``BEST_EFFORT``; shipping ``RELIABLE`` here would silently drop
  every scan.
* ``/tf`` + ``/tf_static``: TF broadcasters are ``RELIABLE`` with
  ``TRANSIENT_LOCAL`` durability so late-joining subscribers (a
  slam_toolbox that starts after the bridge) still latch the static
  sensor frames.  Depth 100 matches ``tf2_ros`` defaults.

The ``QoSProfileConfig`` model is reused by all four fields; values
are mapped to ``rclpy.qos.QoSProfile`` at runtime via
:mod:`marslab.ros2_bridge.qos` (lazy import so unit tests run without
rclpy on the path).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["QoSProfileConfig", "Ros2BridgeConfig"]


# Reviewer 2 #12 (2026-04-24): both models below pin ``extra="forbid"``
# so a misspelled QoS policy string (``"best_efforts"``) or a stray
# ``graph_path_override`` key fails at YAML load time rather than being
# silently dropped by pydantic v2's default ``extra="ignore"``.


class QoSProfileConfig(BaseModel):
    """rclpy QoS profile -- YAML-facing view of ``rclpy.qos.QoSProfile``.

    Mirrors the four fields that matter for SLAM/Nav2 round-tripping:
    ``reliability``, ``durability``, ``history``, ``depth``.  Liveliness
    / deadline are intentionally omitted — v1.0 does not exercise them
    and exposing unused knobs in YAML invites drift.

    The string enums match the rclpy policy names (lower-cased) so a
    reader familiar with rclpy docs can map YAML to code without a
    lookup table.  Invalid strings raise ``pydantic.ValidationError``
    at config load time — the whole point of surfacing QoS in YAML is
    to fail loudly before Isaac Sim boots.
    """

    model_config = ConfigDict(extra="forbid")

    reliability: Literal["reliable", "best_effort"] = Field(
        default="reliable",
        description=(
            "rclpy ReliabilityPolicy. ``reliable`` = retry until ACK "
            "(matches REP-2003 SystemDefault). ``best_effort`` = fire "
            "and forget (the sensor_data convention; required by "
            "slam_toolbox LaserScan subscribers that default to "
            "BEST_EFFORT)."
        ),
    )
    durability: Literal["volatile", "transient_local"] = Field(
        default="volatile",
        description=(
            "rclpy DurabilityPolicy. ``volatile`` drops undelivered "
            "samples at shutdown. ``transient_local`` latches the "
            "latest sample for late-joining subscribers and is the "
            "required setting for ``/tf_static``; without it a "
            "slam_toolbox that boots after the bridge never receives "
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

    Matches Nav2 ``controller_server`` output and REP-2003 SystemDefault.
    Declared as a module-level factory (not an inline lambda) so the
    rationale is attached to the function name and the pydantic
    ``default_factory`` signature stays readable.
    """
    return QoSProfileConfig(reliability="reliable", durability="volatile", depth=10)


def _odom_qos_default() -> QoSProfileConfig:
    """``/odom`` default: RELIABLE + KEEP_LAST(10).

    ``nav_msgs/Odometry`` REP-2003 SystemDefault.  Kept shallow (10)
    because Nav2 ``amcl`` / costmap layers only consume the latest
    pose per cycle — deeper queues just add latency on recovery.
    """
    return QoSProfileConfig(reliability="reliable", durability="volatile", depth=10)


def _sensor_qos_default() -> QoSProfileConfig:
    """``/imu``, ``/camera/*``, ``/lidar/*`` default: BEST_EFFORT + KEEP_LAST(5).

    ROS 2 ``sensor_data`` convention (``rclpy.qos.qos_profile_sensor_data``).
    slam_toolbox subscribes to ``sensor_msgs/LaserScan`` with
    BEST_EFFORT; shipping RELIABLE would mean 0 messages received on
    any Stage-3 run.  Depth 5 is the rclpy sensor_data default.
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
    free-form ``namespace`` / ``topics`` / ``rates`` / ``odom_publisher``
    keys continue to flow through ``init_rclpy_side`` as an untyped
    dict because they are already covered by legacy tests.  A later
    pass (R4-6+) may promote the remaining dict keys.
    """

    model_config = ConfigDict(extra="forbid")

    graph_path: str = Field(
        default="/World/Stage3ROS2Graph",
        description=(
            "USD prim path for the Stage-3 OmniGraph action graph.  The Isaac Sim stage "
            "must not already contain a prim at this path.  Previously hardcoded as "
            "``GRAPH_PATH`` in ``marslab/ros2_bridge/sensor_graph.py``.  Promoted to "
            "schema in R4-5 (2026-04-23) so scenarios with unusual stage layouts "
            "(e.g. multi-robot Stage-4) can relocate the graph without a source edit."
        ),
    )
    cmd_vel_queue_size: int = Field(
        default=10,
        ge=1,
        le=1000,
        description=(
            "rclpy subscription queue depth for ``/<ns>/cmd_vel``.  Previously hardcoded "
            "as ``queue_size=10`` in ``marslab/ros2_bridge/cmd_vel_subscriber.py``.  "
            "Promoted in R4-5 (2026-04-23) so Nav2 tuning that needs a deeper buffer "
            "(bursty controller_server output) can be expressed in YAML.  Upper bound "
            "1000 prevents misconfigurations that would swamp rclpy with unbounded queues."
        ),
    )
    publish_pointcloud2: bool = Field(
        default=True,
        description=(
            "When ``True`` the Stage-3 OmniGraph appends a second "
            "``isaacsim.ros2.bridge.ROS2CameraHelper`` node fed off the depth "
            "render product with ``inputs:type='depth_pcl'`` so the RGB-D "
            "camera publishes a ``sensor_msgs/PointCloud2`` topic at the "
            "depth camera rate (RealSense D435/D455-style behaviour).  "
            "Source: ``isaacsim/exts/isaacsim.ros2.bridge/isaacsim/ros2/bridge/"
            "ogn/python/nodes/OgnROS2CameraHelper.py:141-155`` -- the "
            "``depth_pcl`` token routes through ``ROS2PublishPointCloud`` with "
            "``DistanceToImagePlane`` as the source render variable, so depth "
            "+ camera intrinsics are converted into XYZ points inside the "
            "writer.  Topic name comes from ``rover.ros2.topics.points`` "
            "(default ``depth/points``); ``frameId`` reuses ``camera_link`` so "
            "the publisher joins the existing static TF chain instead of "
            "introducing an unattached optical frame.  Default ``True`` "
            "matches the RealSense convention -- flip to ``False`` for "
            "headless data-gen scenarios where the extra bandwidth is not "
            "wanted.  Added on Day 2 of the MarsLab v1.0 sprint (2026-04-25)."
        ),
    )
    cmd_vel_qos: QoSProfileConfig = Field(
        default_factory=_cmd_vel_qos_default,
        description=(
            "QoS profile for the ``/<ns>/cmd_vel`` subscription.  Default matches "
            "Nav2 ``controller_server`` output (REP-2003 SystemDefault = RELIABLE + "
            "KEEP_LAST depth=10).  Flip to ``best_effort`` when driving the rover "
            "primarily with ``teleop_twist_keyboard`` (ships BEST_EFFORT)."
        ),
    )
    odom_qos: QoSProfileConfig = Field(
        default_factory=_odom_qos_default,
        description=(
            "QoS profile for the ``/<ns>/odom`` publisher.  ``nav_msgs/Odometry`` "
            "REP-2003 SystemDefault (RELIABLE + KEEP_LAST depth=10).  Kept shallow "
            "because Nav2 only reads the latest pose per control cycle."
        ),
    )
    sensor_qos: QoSProfileConfig = Field(
        default_factory=_sensor_qos_default,
        description=(
            "QoS profile for sensor streams (``/imu``, ``/camera/*``, "
            "``/lidar/*``, ``/scan``).  Matches the ROS 2 ``sensor_data`` "
            "convention (BEST_EFFORT + KEEP_LAST depth=5).  slam_toolbox "
            "LaserScan subscribers default to BEST_EFFORT — shipping "
            "RELIABLE here would yield 0 messages received."
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
