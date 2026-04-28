"""rclpy-side initialisation for the Stage-3 ROS2 bridge.

Extracted from :mod:`marslab.ros2_bridge.__init__` so that importing
:mod:`marslab.ros2_bridge` does not trigger ``rclpy`` until the
runtime actually needs it.

``init_rclpy_side`` pulls the four QoS profiles (``cmd_vel_qos`` /
``odom_qos`` / ``sensor_qos`` / ``tf_qos``) from the ``rover.ros2``
YAML block via
:class:`marslab.config.schema.ros2_bridge.Ros2BridgeConfig`.  Legacy
scenarios that do not declare QoS fields continue to get the schema
defaults.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple

import numpy as np

from marslab.config.schema.ros2_bridge import QoSProfileConfig, Ros2BridgeConfig
from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber
from marslab.ros2_bridge.context import BridgeContext
from marslab.ros2_bridge.odometry_publisher import create_odometry_publisher
from marslab.ros2_bridge.robot_description_publisher import publish_robot_description
from marslab.ros2_bridge.sensor_graph_builder import _ns_topic
from marslab.ros2_bridge.tf_broadcaster import publish_static_sensor_tfs


def init_rclpy_side(
    ros2_cfg: Dict[str, Any],
    sensor_frames: Iterable[Tuple[str, Any]],
    init_pos_world: np.ndarray,
    init_quat_world: np.ndarray,
    node_name: str = "marslab_stage3_runtime",
    *,
    urdf_path: Optional[str] = None,
) -> BridgeContext:
    """Boot rclpy and wire cmd_vel / static TF / odom publishers.

    Args:
        ros2_cfg: Merged ``rover.ros2`` block (namespace + topic map).
        sensor_frames: Iterable of ``(child_frame_id, local_xyz)``
            pairs for static sensor TFs.
        init_pos_world: Rover initial world position, shape ``(3,)``.
        init_quat_world: Rover initial world orientation (scalar-first).
        node_name: rclpy node name; namespaced by ``ros2_cfg["namespace"]``.
        urdf_path: Absolute filesystem path to the rover URDF, used by
            :func:`publish_robot_description` to populate
            ``/<ns>/robot_description``. Lives on the rover top-level
            (``rover.urdf_source_path``) -- pass it explicitly so the
            ``ros2:`` schema does not have to mirror it. ``None``
            disables the publisher (along with
            ``ros2.publish_robot_description=false``).

    Returns:
        :class:`BridgeContext` holding every handle the main loop
        needs plus the shared ``twist_state`` dict written by the
        cmd_vel subscriber callback.
    """
    import rclpy  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope
    import rclpy.parameter  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    if not rclpy.ok():
        rclpy.init(args=None)

    # Validate the schema-known subset of ``ros2_cfg`` ONCE so every
    # downstream attribute access comes from a single validated source.
    # The raw YAML dict carries free-form keys (``namespace``,
    # ``topics``, ``rates``, ``odom_publisher``) that are NOT declared
    # on :class:`Ros2BridgeConfig`; with ``extra="forbid"`` a direct
    # ``model_validate`` would reject them.  Filter to schema fields
    # first so validation only sees declared keys, while keeping the
    # raw dict around for the remaining free-form access below.  Falls
    # back to a plain ``Ros2BridgeConfig()`` when ``ros2_cfg`` is not
    # dict-shaped so legacy callers passing exotic mapping types keep
    # working.
    if isinstance(ros2_cfg, dict):
        schema_fields = set(Ros2BridgeConfig.model_fields.keys())
        schema_subset = {k: v for k, v in ros2_cfg.items() if k in schema_fields}
        validated_bridge = Ros2BridgeConfig.model_validate(schema_subset, strict=False)
    else:
        validated_bridge = Ros2BridgeConfig()

    ns = str(ros2_cfg["namespace"])
    topics = dict(ros2_cfg["topics"])
    qos_bundle = _resolve_qos_bundle(ros2_cfg)

    node = rclpy.create_node(
        f"{ns}_{node_name}",
        parameter_overrides=[
            rclpy.parameter.Parameter(
                "use_sim_time",
                rclpy.parameter.Parameter.Type.BOOL,
                True,
            )
        ],
    )

    twist_state: Dict[str, float] = {"v": 0.0, "w": 0.0}
    cmd_vel_topic = _ns_topic(ns, topics["cmd_vel"])
    # ``cmd_vel_queue_size`` is a schema field
    # (``Ros2BridgeConfig.cmd_vel_queue_size``) rather than a Python
    # default inside ``create_cmd_vel_subscriber``.  Falls back to the
    # historical constant (10) when the YAML key is absent so existing
    # scenarios keep loading unchanged.
    cmd_vel_queue_size = int(ros2_cfg.get("cmd_vel_queue_size", 10))
    # Pass the resolved QoSProfile so the subscription reliability
    # matches Nav2 controller_server expectations.
    cmd_vel_sub = create_cmd_vel_subscriber(
        node,
        cmd_vel_topic,
        twist_state,
        queue_size=cmd_vel_queue_size,
        qos=qos_bundle["cmd_vel"],
    )

    # ``sensor_parent_frame_id`` is a schema field
    # (``Ros2BridgeConfig.sensor_parent_frame_id``); C1 default is
    # ``"base_link"`` for backwards compatibility with the legacy
    # nameOverride-paired chain.  Override via the rover YAML when the
    # downstream consumer expects a different parent (e.g.
    # ``Body_Chassis`` after C3 disables the URDF rewrite).
    sensor_parent_frame_id = str(validated_bridge.sensor_parent_frame_id)
    static_broadcaster = publish_static_sensor_tfs(
        node,
        sensor_frames,
        parent_frame_id=sensor_parent_frame_id,
        qos=qos_bundle["tf"],
    )

    # Publish URDF on /robot_description for RViz.  ``urdf_path`` is
    # sourced from ``rover.urdf_source_path`` (top-level, not the ros2
    # block) and threaded through as a kwarg by the runtime entry
    # point.  The ``robot_description`` topic key is required in the
    # YAML topic map; a missing key raises ``KeyError`` immediately so
    # a typo cannot fall through to a Python fallback.
    robot_description_ctx = None
    if ros2_cfg.get("publish_robot_description", True) and urdf_path:
        if "robot_description" not in topics:
            raise KeyError(
                "ros2.topics.robot_description must be declared in the rover YAML "
                "(e.g. 'robot_description: \"robot_description\"'); the publisher "
                "refuses to fall back to a Python default."
            )
        rd_topic = _ns_topic(ns, topics["robot_description"])
        # ``rename_root_to_base_link`` is a schema field
        # (``Ros2BridgeConfig.rename_root_to_base_link``); C1 default
        # ``True`` preserves the legacy nameOverride-paired rewrite.
        # C3 flips the default to ``False`` so the URDF link names
        # match the OG-published joint owners verbatim.
        rename_root = bool(validated_bridge.rename_root_to_base_link)
        robot_description_ctx = publish_robot_description(
            node,
            urdf_path,
            topic=rd_topic,
            rename_root_to_base_link=rename_root,
        )

    odom_topic = _ns_topic(ns, topics["odom"])
    # Pull frame_id / child_frame_id / queue_size from YAML when the
    # rover block declares an ``odom_publisher`` sub-map. The sub-map
    # mirrors ``OdomPublisherConfig``
    # (marslab/config/schema/robot.py) so slam_toolbox and Nav2 frame
    # names stay aligned with a single YAML source. Falls back to the
    # historical function defaults when the key is absent so existing
    # scenario YAMLs keep loading unchanged.
    odom_pub_cfg = ros2_cfg.get("odom_publisher", {}) if isinstance(ros2_cfg, dict) else {}
    # Default OFF so the OmniGraph ``ROS2PublishTransformTree`` is the
    # sole TF authority for ``odom -> base_link``.  An external
    # ``ros2 run topic_tools relay /tf_raw /tf`` then merges the
    # OmniGraph chain into the canonical ``/tf`` topic for RViz / Nav2.
    # Setting this ``True`` while the relay runs would give tf2 two
    # parents for ``base_link``.  The schema field
    # ``Ros2BridgeConfig.publish_odom_tf`` is the validated source of
    # truth; it returns ``False`` by default and is overridable via
    # the YAML.
    publish_odom_tf = bool(validated_bridge.publish_odom_tf)
    odom_ctx = create_odometry_publisher(
        node=node,
        topic=odom_topic,
        init_pos_world=init_pos_world,
        init_quat_world=init_quat_world,
        queue_size=int(odom_pub_cfg.get("queue_size", 10)),
        frame_id=str(odom_pub_cfg.get("frame_id", "odom")),
        child_frame_id=str(odom_pub_cfg.get("child_frame_id", "base_link")),
        odom_qos=qos_bundle["odom"],
        tf_qos=qos_bundle["tf"],
        publish_tf=publish_odom_tf,
    )

    return BridgeContext(
        node=node,
        cmd_vel_subscription=cmd_vel_sub,
        static_tf_broadcaster=static_broadcaster,
        odom_ctx=odom_ctx,
        twist_state=twist_state,
        robot_description_ctx=robot_description_ctx,
    )


def _extract_qos_field(ros2_cfg: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    """Return the raw dict for ``ros2_cfg[key]`` if it looks like a QoS block.

    Accepts the YAML form (a nested dict with ``reliability`` /
    ``durability`` / ``history`` / ``depth`` keys).  Returns ``None``
    when the key is absent so the caller can fall back to the schema
    default.  Non-dict values (e.g. an accidental string) are
    rejected by pydantic when the dict is passed to
    :class:`QoSProfileConfig` below, so no defensive check here.
    """
    if not isinstance(ros2_cfg, dict):
        return None
    raw = ros2_cfg.get(key)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        # Pass through so pydantic produces the standard error message;
        # rejecting here would require duplicating the schema validator.
        return raw  # type: ignore[return-value]
    return raw


def _resolve_qos_bundle(ros2_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Build the four rclpy ``QoSProfile`` instances from YAML.

    Returns a dict with keys ``cmd_vel`` / ``odom`` / ``sensor`` /
    ``tf`` so the caller (``init_rclpy_side``) can index cleanly
    without juggling four scalar variables.  Every value is a fully
    constructed ``rclpy.qos.QoSProfile``.

    Absent keys fall back to the :class:`Ros2BridgeConfig` defaults;
    an invalid YAML value (e.g. ``reliability: "kinda_reliable"``) is
    caught by pydantic at this stage, before rclpy is ever touched.
    """
    # Lazy import so tests that import ``rclpy_integration`` without
    # rclpy on the path keep working (see test_ros2_bridge_lazy_import).
    from marslab.ros2_bridge.qos import (
        to_rclpy_qos,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    defaults = Ros2BridgeConfig()

    def _pick(name: str, fallback: QoSProfileConfig) -> QoSProfileConfig:
        raw = _extract_qos_field(ros2_cfg, name)
        if raw is None:
            return fallback
        return QoSProfileConfig.model_validate(raw)

    return {
        "cmd_vel": to_rclpy_qos(_pick("cmd_vel_qos", defaults.cmd_vel_qos)),
        "odom": to_rclpy_qos(_pick("odom_qos", defaults.odom_qos)),
        "sensor": to_rclpy_qos(_pick("sensor_qos", defaults.sensor_qos)),
        "tf": to_rclpy_qos(_pick("tf_qos", defaults.tf_qos)),
    }


__all__ = ["init_rclpy_side"]
