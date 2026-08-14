"""rclpy-side initialisation for the rover ROS2 bridge.

Extracted from :mod:`marslab.ros2_bridge.__init__` so that importing
:mod:`marslab.ros2_bridge` does not trigger ``rclpy`` until the
runtime actually needs it.

``init_rclpy_side`` pulls the four QoS profiles (``cmd_vel_qos`` /
``odom_qos`` / ``sensor_qos`` / ``tf_qos``) from the ``rover.ros2``
YAML block via
:class:`marslab.config.schema.ros2_bridge.Ros2BridgeConfig`.
Scenarios that do not declare QoS fields receive the schema
defaults.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple

import numpy as np

from marslab.config.schema.rover_ros2 import Ros2BridgeConfig
from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber
from marslab.ros2_bridge.context import BridgeContext
from marslab.ros2_bridge.imu_noise_publisher import create_imu_noise_publisher
from marslab.ros2_bridge.odometry_publisher import create_odometry_publisher
from marslab.ros2_bridge.robot_description_publisher import publish_robot_description
from marslab.ros2_bridge.sensor_graph_builder import _ns_topic
from marslab.ros2_bridge.tf_broadcaster import publish_static_sensor_tfs
from marslab.ros2_bridge.wheel_odometry_publisher import create_wheel_odometry_publisher


def init_rclpy_side(
    ros2_cfg: Ros2BridgeConfig,
    sensor_frames: Iterable[Tuple[str, list[float], list[float]]],
    init_pos_world: np.ndarray,
    init_quat_world: np.ndarray,
    node_name: str = "marslab_stage3_runtime",
    *,
    urdf_path: Optional[str] = None,
    wheel_odom_params: Optional[Dict[str, Any]] = None,
    imu_noise_params: Optional[Dict[str, Any]] = None,
) -> BridgeContext:
    """Boot rclpy and wire cmd_vel / static TF / odom publishers.

    Args:
        ros2_cfg: Merged ``rover.ros2`` block (namespace + topic map).
        sensor_frames: Iterable of ``(child_frame_id, local_xyz)``
            pairs for static sensor TFs.
        init_pos_world: Rover initial world position, shape ``(3,)``.
        init_quat_world: Rover initial world orientation (scalar-first).
        node_name: rclpy node name; namespaced by ``ros2_cfg.namespace``.
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

    ns = ros2_cfg.namespace
    topics = ros2_cfg.topics
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
    cmd_vel_topic = _ns_topic(ns, topics.cmd_vel)
    # ``cmd_vel_queue_size`` is a schema field
    # (``Ros2BridgeConfig.cmd_vel_queue_size``) rather than a Python
    # default inside ``create_cmd_vel_subscriber``.  Falls back to the
    # historical constant (10) when the YAML key is absent so existing
    # scenarios keep loading unchanged.
    cmd_vel_queue_size = int(ros2_cfg.cmd_vel_queue_size)
    # Pass the resolved QoSProfile so the subscription reliability
    # matches the upstream controller's expectations.
    cmd_vel_sub = create_cmd_vel_subscriber(
        node,
        cmd_vel_topic,
        twist_state,
        queue_size=cmd_vel_queue_size,
        qos=qos_bundle["cmd_vel"],
    )

    # ``sensor_parent_frame_id`` is a schema field
    # (``Ros2BridgeConfig.sensor_parent_frame_id``).  Default
    # ``"base_link"`` aligns the static sensor TFs with the URDF root
    # link when ``rename_root_to_base_link=True``.  Override via the
    # rover YAML when the downstream consumer expects a different
    # parent (e.g. ``Body_Chassis`` when the URDF rewrite is disabled).
    sensor_parent_frame_id = ros2_cfg.sensor_parent_frame_id
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
    if ros2_cfg.publish_robot_description and urdf_path:
        rd_topic = _ns_topic(ns, topics.robot_description)
        # ``rename_root_to_base_link`` is a schema field
        # (``Ros2BridgeConfig.rename_root_to_base_link``).  Default
        # ``True`` rewrites the URDF root link to ``base_link`` so the
        # OmniGraph PubTF + ``isaac:nameOverride='base_link'`` path
        # publishes a frame the URDF agrees with.  Set ``False`` when
        # the robot_state_publisher workflow reads frame names directly
        # from the URDF (no rewrite required).
        rename_root = ros2_cfg.rename_root_to_base_link
        robot_description_ctx = publish_robot_description(
            node,
            urdf_path,
            topic=rd_topic,
            rename_root_to_base_link=rename_root,
        )

    # GT trajectory publisher: PhysX articulation pose verbatim on
    # ``/<ns>/GT_Trajectory`` (was ``/<ns>/odom`` pre-refactor).  This
    # topic is the GT for ATE comparison and never carries TF authority.
    gt_topic = _ns_topic(ns, topics.gt_trajectory)
    odom_pub_cfg = ros2_cfg.odom_publisher
    # GT publisher emits ABSOLUTE world pose (REP-105 `map` frame) so it
    # matches the world-frame reference trajectory used by PathFollower
    # and serves as the ATE reference directly without alignment offset.
    # Passing identity init makes the publisher's delta computation a no-op:
    # delta = current_world - 0 = current_world.
    _gt_init_pos_abs = np.zeros(3, dtype=np.float32)
    _gt_init_quat_abs = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)  # wxyz identity
    odom_ctx = create_odometry_publisher(
        node=node,
        topic=gt_topic,
        init_pos_world=_gt_init_pos_abs,
        init_quat_world=_gt_init_quat_abs,
        queue_size=int(odom_pub_cfg.queue_size),
        frame_id=odom_pub_cfg.gt_frame_id,
        child_frame_id=odom_pub_cfg.gt_child_frame_id,
        odom_qos=qos_bundle["odom"],
        tf_qos=qos_bundle["tf"],
        publish_tf=False,
    )

    # Wheel-encoder dead-reckoning publisher on ``/<ns>/odom``.  When
    # ``wheel_odom_params`` is ``None`` the publisher is skipped so the
    # legacy ``--no-rover`` path keeps working.
    wheel_odom_ctx = None
    if wheel_odom_params is not None:
        wheel_odom_topic = _ns_topic(ns, topics.odom)
        publish_wheel_odom_tf = ros2_cfg.publish_odom_tf
        wheel_odom_ctx = create_wheel_odometry_publisher(
            node=node,
            topic=wheel_odom_topic,
            left_indices=wheel_odom_params["left_indices"],
            right_indices=wheel_odom_params["right_indices"],
            wheel_radius=float(wheel_odom_params["wheel_radius"]),
            track_width=float(wheel_odom_params["track_width"]),
            slip_left=float(wheel_odom_params.get("slip_left", 0.0)),
            slip_right=float(wheel_odom_params.get("slip_right", 0.0)),
            sigma_omega=float(wheel_odom_params.get("sigma_omega", 0.0)),
            seed=(
                int(wheel_odom_params["seed"])
                if wheel_odom_params.get("seed") is not None
                else None
            ),
            queue_size=int(odom_pub_cfg.queue_size),
            odom_qos=qos_bundle["odom"],
            tf_qos=qos_bundle["tf"],
            frame_id=odom_pub_cfg.frame_id,
            child_frame_id=odom_pub_cfg.child_frame_id,
            publish_tf=publish_wheel_odom_tf,
            pose_diag=wheel_odom_params.get("pose_diag"),
            twist_diag=wheel_odom_params.get("twist_diag"),
        )

    # IMU noise publisher — only created when sigma fields are non-zero.
    # ``imu_noise_params`` carries ``imu_prim_path``, ``sigma_lin_acc``,
    # ``sigma_ang_vel``, and ``seed`` derived from the master sensors.seed.
    imu_noise_ctx = None
    if imu_noise_params is not None:
        sigma_la = float(imu_noise_params.get("sigma_lin_acc", 0.0))
        sigma_av = float(imu_noise_params.get("sigma_ang_vel", 0.0))
        if sigma_la > 0.0 or sigma_av > 0.0:
            # Publish noisy IMU on a dedicated topic to avoid colliding with the
            # OmniGraph PubIMU node, which also publishes to topics["imu"].
            # Downstream SLAM stacks that need repeatable noisy IMU should
            # subscribe to /<ns>/imu_noisy; /<ns>/imu remains the raw OmniGraph stream.
            imu_topic = _ns_topic(ns, topics.imu_noisy)
            imu_noise_ctx = create_imu_noise_publisher(
                node=node,
                topic=imu_topic,
                imu_prim_path=str(imu_noise_params["imu_prim_path"]),
                sigma_lin_acc=sigma_la,
                sigma_ang_vel=sigma_av,
                seed=imu_noise_params.get("seed"),
                queue_size=10,
                sensor_qos=qos_bundle["sensor"],
            )

    return BridgeContext(
        node=node,
        cmd_vel_subscription=cmd_vel_sub,
        static_tf_broadcaster=static_broadcaster,
        odom_ctx=odom_ctx,
        twist_state=twist_state,
        robot_description_ctx=robot_description_ctx,
        wheel_odom_ctx=wheel_odom_ctx,
        imu_noise_ctx=imu_noise_ctx,
    )


def _resolve_qos_bundle(ros2_cfg: Ros2BridgeConfig) -> Dict[str, Any]:
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

    return {
        "cmd_vel": to_rclpy_qos(ros2_cfg.cmd_vel_qos),
        "odom": to_rclpy_qos(ros2_cfg.odom_qos),
        "sensor": to_rclpy_qos(ros2_cfg.sensor_qos),
        "tf": to_rclpy_qos(ros2_cfg.tf_qos),
    }


__all__ = ["init_rclpy_side"]
