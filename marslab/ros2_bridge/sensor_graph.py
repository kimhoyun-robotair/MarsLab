"""Stage-3 ROS2 OmniGraph orchestrator.

Composes a single action graph that drives:

* ``/clock`` from Isaac Sim simulation time.
* Articulation joint TF on a dedicated ``/tf_raw`` topic, kept
  separate from the rclpy ``odom -> base_link`` broadcaster on ``/tf``
  in :mod:`marslab.ros2_bridge.odometry_publisher`.  Sharing one
  ``/tf`` was tried and rolled back because the two publishers
  produced duplicated / out-of-phase frames in RViz and Nav2.  The
  split is enforced by user policy: never merge OmniGraph PubTF and
  rclpy TransformBroadcaster onto the same ``/tf`` topic.
* IMU (``sensor_msgs/Imu``).
* Camera RGB + Depth via independent render products.
* 3-D LiDAR point cloud.

The graph path + node names mirror the legacy Stage-1 graph to keep
the debugger / ros2 graph view familiar.

The list-building helpers (``_build_create_nodes`` /
``_build_connections`` / ``_build_set_values``) live in
:mod:`marslab.ros2_bridge.sensor_graph_builder` so they can be unit
tested without Isaac Sim.  They are re-exported below for backward
compatibility with existing tests and callers.

``GRAPH_PATH`` is the canonical default for the action-graph prim
path.  It is also the default for ``Ros2BridgeConfig.graph_path``
(see :mod:`marslab.config.schema.ros2_bridge`).  The module constant
is kept as the canonical default so legacy imports
(``from marslab.ros2_bridge import GRAPH_PATH``) still resolve, but
``build_sensor_graph`` reads ``ros2_cfg["graph_path"]`` first and
only falls back when the YAML key is absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from marslab.ros2_bridge.sensor_graph_builder import (
    _build_connections,
    _build_create_nodes,
    _build_set_values,
    _ns_topic,
)

# Canonical default for the Stage-3 action graph prim path.  Also the
# default for ``Ros2BridgeConfig.graph_path`` -- keep the two in sync.
GRAPH_PATH = "/World/Stage3ROS2Graph"


@dataclass
class SensorGraphHandle:
    """Bundle returned by :func:`build_sensor_graph`."""

    graph_path: str
    graph: Any


def _resolve_ros2_bridge_options(ros2_cfg: Dict[str, Any]) -> Any:
    """Validate the schema-known subset of ``ros2_cfg`` ONCE.

    The raw ``rover.ros2`` YAML dict carries free-form keys that are
    NOT declared on :class:`Ros2BridgeConfig` (``namespace``,
    ``topics``, ``rates``, ``odom_publisher``, etc.).  Filtering to
    schema fields before validation lets the orchestrator and every
    legacy resolver wrapper pull defaults from a single validated
    model without a ``model_validate`` per attribute.

    Args:
        ros2_cfg: ``rover.ros2`` block (free-form dict for legacy
            compatibility).

    Returns:
        A :class:`Ros2BridgeConfig` instance carrying the merged
        view of schema-declared fields (YAML overrides + pydantic
        defaults).
    """
    # Local import keeps the schema dependency optional for the rare
    # caller that imports ``sensor_graph`` without the full ``marslab``
    # config tree (e.g. a minimal integration test harness).
    from marslab.config.schema.ros2_bridge import (
        Ros2BridgeConfig,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    if not isinstance(ros2_cfg, dict):
        return Ros2BridgeConfig()
    schema_fields = set(Ros2BridgeConfig.model_fields.keys())
    schema_subset = {k: v for k, v in ros2_cfg.items() if k in schema_fields}
    return Ros2BridgeConfig.model_validate(schema_subset)


def build_sensor_graph(
    ros2_cfg: Dict[str, Any],
    camera_prim_path: str,
    camera_resolution: Tuple[int, int],
    lidar_3d_prim_path: str,
    imu_prim_path: str,
    articulation_root_prim_path: str,
    parent_anchor_prim_path: str,
    lidar_2d_prim_path: Optional[str] = None,
    depth_sensor_cfg: Optional[Dict[str, Any]] = None,
) -> SensorGraphHandle:
    """Build the Stage-3 ROS2 OmniGraph.

    Args:
        ros2_cfg: ``rover.ros2`` block from the merged scenario config.
            May include an optional ``graph_path`` key -- if present,
            it overrides the module default :data:`GRAPH_PATH` and is
            validated the same way :class:`Ros2BridgeConfig` validates
            it (non-empty, ``/``-prefixed, no whitespace).  When absent
            the legacy constant is used so existing scenario YAMLs keep
            loading unchanged.
        camera_prim_path: USD path of the Camera prim.
        camera_resolution: ``(width, height)`` tuple.
        lidar_3d_prim_path: USD path of the 3-D RTX LiDAR prim.
        imu_prim_path: USD path of the IMU prim.
        articulation_root_prim_path: USD path of the rover articulation
            root prim (typically ``spawned.prim_path`` returned by
            :func:`marslab.robots.rover.spawn_rover`).  Forwarded to
            ``PubTF.inputs:targetPrims`` so the non-Raw
            ``ROS2PublishTransformTree`` auto-walks the articulation
            chain.  See ``OgnROS2PublishTransformTree.rst:45``.
        parent_anchor_prim_path: USD path of the stationary ``odom``
            anchor prim (typically
            :data:`marslab.ros2_bridge.tf_nameoverrides.DEFAULT_ODOM_ANCHOR_PATH`).
            Forwarded to ``PubTF.inputs:parentPrim`` so the published
            chain reads ``odom -> base_link -> ...`` (REP-105) instead
            of ``world -> base_link -> ...``.
        lidar_2d_prim_path: Optional USD path of the 2-D RTX LiDAR prim.
            When provided and ``topics["scan"]`` is set in ``ros2_cfg``,
            a ``RPLidar2D``/``Lidar2DHelper`` pair is added with
            ``type="laser_scan"``.
        depth_sensor_cfg: Optional ``rover.sensors.camera.depth_sensor``
            block.  When ``enabled=True`` the orchestrator applies the
            ``OmniSensorDepthSensorSingleViewAPI`` schema to the camera
            render product so the depth output simulates a stereo
            disparity camera (RealSense-style noise + occlusion holes +
            confidence map) instead of the renderer's noiseless
            ``DistanceToImagePlane`` AOV.  See
            ``isaacsim/exts/isaacsim.sensors.camera/isaacsim/sensors/
            camera/single_view_depth_sensor.py:46-503`` for the schema
            attribute names (``omni:rtx:post:depthSensor:<field>``).
            When the schema or the extension is unavailable at runtime
            the apply step is a no-op and the graph falls back to the
            renderer's raw depth (Path-1-only behaviour).

    Returns:
        :class:`SensorGraphHandle`.
    """
    import omni.graph.core as og  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    ns = str(ros2_cfg["namespace"])
    topics = dict(ros2_cfg["topics"])
    options = _resolve_ros2_bridge_options(ros2_cfg)
    graph_path = options.graph_path
    sensor_preset, tf_preset = _build_qos_presets(options)
    include_2d = lidar_2d_prim_path is not None and "scan" in topics
    include_pcl = options.publish_pointcloud2 and "points" in topics
    include_caminfo = options.publish_camera_info and "camera_info" in topics
    publish_joint_states = bool(options.publish_joint_states)

    keys = og.Controller.Keys
    graph_handle, _, _, _ = og.Controller.edit(
        {"graph_path": graph_path, "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: _build_create_nodes(
                include_lidar_2d=include_2d,
                include_pointcloud2=include_pcl,
                include_camera_info=include_caminfo,
                publish_joint_states=publish_joint_states,
            ),
            keys.CONNECT: _build_connections(
                include_lidar_2d=include_2d,
                include_pointcloud2=include_pcl,
                include_camera_info=include_caminfo,
                publish_joint_states=publish_joint_states,
            ),
            keys.SET_VALUES: _build_set_values(
                ns=ns,
                topics=topics,
                imu_prim_path=imu_prim_path,
                camera_prim_path=camera_prim_path,
                camera_resolution=camera_resolution,
                lidar_3d_prim_path=lidar_3d_prim_path,
                articulation_root_prim_path=articulation_root_prim_path,
                parent_anchor_prim_path=parent_anchor_prim_path,
                lidar_2d_prim_path=lidar_2d_prim_path if include_2d else None,
                sensor_qos_preset=sensor_preset,
                tf_qos_preset=tf_preset,
                include_pointcloud2=include_pcl,
                include_camera_info=include_caminfo,
                publish_joint_states=publish_joint_states,
            ),
        },
    )

    # Optional Path 2: apply the depth-sensor schema to the shared
    # camera render product.  Wrapped in try/except so a missing
    # extension or an older Isaac Sim release falls back gracefully to
    # the renderer's raw ``DistanceToImagePlane`` depth (Path-1-only
    # behaviour).  ``depth_sensor_cfg`` is the YAML block validated
    # earlier as :class:`marslab.config.schema.robot.DepthSensorConfig`.
    if depth_sensor_cfg is not None and bool(depth_sensor_cfg.get("enabled")):
        try:
            _apply_depth_sensor_schema(graph_path, depth_sensor_cfg)
        except Exception as exc:  # pragma: no cover - runtime-only fallback
            import logging  # noqa: PLC0415  -- defer until needed

            logging.getLogger(__name__).warning(
                "Depth-sensor schema apply skipped: %s.  Falling back to "
                "the renderer's raw DistanceToImagePlane AOV (Path-1-only "
                "behaviour).",
                exc,
            )

    return SensorGraphHandle(graph_path=graph_path, graph=graph_handle)


# ``omni:rtx:post:depthSensor:<field>`` USD attribute names for the
# ``OmniSensorDepthSensorSingleViewAPI`` schema.  Pinned in one place so
# YAML field renames don't silently desync from the schema.  Source:
# ``isaacsim/extscache/omni.usd.schema.omni_sensors-0.0.0+69cbf6ad/
# usd_plugins/generatedSchema.usda`` (OmniSensorDepthSensorSingleViewAPI).
_DEPTH_SENSOR_SCHEMA_ATTRS: Dict[str, str] = {
    "baseline_mm": "omni:rtx:post:depthSensor:baselineMM",
    "min_distance_m": "omni:rtx:post:depthSensor:minDistance",
    "max_distance_m": "omni:rtx:post:depthSensor:maxDistance",
    "noise_mean": "omni:rtx:post:depthSensor:noiseMean",
    "noise_sigma": "omni:rtx:post:depthSensor:noiseSigma",
    "confidence_threshold": "omni:rtx:post:depthSensor:confidenceThreshold",
    "max_disparity_pixel": "omni:rtx:post:depthSensor:maxDisparityPixel",
}


def _apply_depth_sensor_schema(graph_path: str, depth_sensor_cfg: Dict[str, Any]) -> None:
    """Apply ``OmniSensorDepthSensorSingleViewAPI`` to the shared render product.

    Reads the actual render product prim path from the ``RPCamera``
    node's ``outputs:renderProductPath`` attribute (resolved by the
    OmniGraph during :func:`og.Controller.edit`), then applies the
    depth-sensor schema and writes every YAML-driven attribute through
    the canonical ``omni:rtx:post:depthSensor:*`` names.

    Args:
        graph_path: USD path of the Stage-3 action graph (``RPCamera``
            lives at ``{graph_path}/RPCamera``).
        depth_sensor_cfg: ``rover.sensors.camera.depth_sensor`` block
            (validated upstream as
            :class:`marslab.config.schema.robot.DepthSensorConfig`).

    The function is intentionally tolerant of older Isaac Sim builds
    that do not bundle the schema -- the caller wraps it in
    try/except so a missing API surfaces as a warning, not a runtime
    crash.
    """
    import omni.graph.core as og  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope
    from isaacsim.core.utils.prims import (
        get_prim_at_path,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    rp_path_attr = og.Controller.attribute(f"{graph_path}/RPCamera.outputs:renderProductPath")
    rp_prim_path = rp_path_attr.get()
    if not rp_prim_path:
        raise RuntimeError(
            f"RPCamera.outputs:renderProductPath at {graph_path}/RPCamera resolved "
            "to an empty value; cannot apply OmniSensorDepthSensorSingleViewAPI"
        )

    rp_prim = get_prim_at_path(str(rp_prim_path))
    if rp_prim is None or not rp_prim.IsValid():
        raise RuntimeError(
            f"Render product prim at {rp_prim_path!r} is invalid; cannot apply "
            "OmniSensorDepthSensorSingleViewAPI"
        )

    rp_prim.ApplyAPI("OmniSensorDepthSensorSingleViewAPI")
    # Always enable the depth sensor when the YAML enabled it -- the
    # schema's default is False which would silently do nothing.
    enabled_attr = rp_prim.GetAttribute("omni:rtx:post:depthSensor:enabled")
    if enabled_attr:
        enabled_attr.Set(True)

    for yaml_field, attr_name in _DEPTH_SENSOR_SCHEMA_ATTRS.items():
        if yaml_field not in depth_sensor_cfg:
            continue
        value = depth_sensor_cfg[yaml_field]
        attr = rp_prim.GetAttribute(attr_name)
        if attr:
            attr.Set(float(value))


def _build_qos_presets(options: Any) -> Tuple[str, str]:
    """Map a validated :class:`Ros2BridgeConfig` to OmniGraph QoS JSON strings.

    The OmniGraph helpers (``ROS2PublishImu``, ``ROS2CameraHelper``,
    ``ROS2RtxLidarHelper``, ``ROS2PublishRawTransformTree``) accept a
    JSON-encoded QoS dict on ``inputs:qosProfile`` (see
    :func:`marslab.ros2_bridge.qos.to_omnigraph_qos_json`).
    """
    from marslab.ros2_bridge.qos import (
        to_omnigraph_qos_json,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    return to_omnigraph_qos_json(options.sensor_qos), to_omnigraph_qos_json(options.tf_qos)


def _resolve_qos_presets(ros2_cfg: Dict[str, Any]) -> Tuple[str, str]:
    """Return ``(sensor_preset, tf_preset)`` Isaac-Sim JSON-encoded QoS strings.

    Thin wrapper that delegates to :func:`_resolve_ros2_bridge_options`
    so the validated schema is the single source of truth.  Preserved
    so external test suites that import the helper by name keep
    working.
    """
    options = _resolve_ros2_bridge_options(ros2_cfg)
    return _build_qos_presets(options)


def _resolve_publish_camera_info(ros2_cfg: Dict[str, Any]) -> bool:
    """Return whether to wire the RGB-derived ``CamInfo`` helper.

    Reads ``ros2_cfg["publish_camera_info"]`` when present (validated via
    :class:`Ros2BridgeConfig`) and falls back to the schema default
    (``True`` -- monocular ``CameraInfo`` publication ON) when absent.
    Mirrors :func:`_resolve_publish_pointcloud2` so the orchestrator
    reaches both knobs through a single validation source.

    Args:
        ros2_cfg: ``rover.ros2`` block (free-form dict for legacy
            compatibility).

    Returns:
        ``True`` to append the ``CamInfo`` node + edges + values, else
        ``False`` to skip the CameraInfo publisher entirely.
    """
    return bool(_resolve_ros2_bridge_options(ros2_cfg).publish_camera_info)


def _resolve_publish_pointcloud2(ros2_cfg: Dict[str, Any]) -> bool:
    """Return whether to wire the depth-derived ``CamPCL`` helper.

    Reads ``ros2_cfg["publish_pointcloud2"]`` when present (validated via
    :class:`Ros2BridgeConfig`) and falls back to the schema default
    (``True`` -- RealSense-style RGB-D PointCloud2 ON) when absent.

    Args:
        ros2_cfg: ``rover.ros2`` block (free-form dict for legacy
            compatibility).

    Returns:
        ``True`` to append the ``CamPCL`` node + edges + values, else
        ``False`` to skip the PointCloud2 publisher entirely.
    """
    return bool(_resolve_ros2_bridge_options(ros2_cfg).publish_pointcloud2)


def _resolve_publish_joint_states(ros2_cfg: Dict[str, Any]) -> bool:
    """Return whether to wire ``ROS2PublishJointState`` instead of ``PubTF``.

    Reads ``ros2_cfg["publish_joint_states"]`` when present (validated
    via :class:`Ros2BridgeConfig`) and falls back to the schema default
    (C2+: ``True`` -- robot_state_publisher pattern; legacy: ``False``
    -- ``/tf_raw`` PubTF + ``topic_tools relay`` pattern).  Mirrors
    :func:`_resolve_publish_camera_info` so the orchestrator reaches
    every publisher knob through one validation source.

    Args:
        ros2_cfg: ``rover.ros2`` block (free-form dict for legacy
            compatibility).

    Returns:
        ``True`` to wire the ``PubJointState`` node, ``False`` to wire
        the legacy ``PubTF`` node.
    """
    return bool(_resolve_ros2_bridge_options(ros2_cfg).publish_joint_states)


def _resolve_graph_path(ros2_cfg: Dict[str, Any]) -> str:
    """Return the action-graph prim path for the Stage-3 bridge.

    Reads ``ros2_cfg["graph_path"]`` when present (validated via
    :class:`Ros2BridgeConfig` for consistency with schema-loaded
    configs) and otherwise falls back to :data:`GRAPH_PATH`.  Routing
    through :class:`Ros2BridgeConfig` keeps a single validation source
    so ad-hoc dict-shaped callers and YAML-loaded callers reject the
    same invalid inputs.

    Args:
        ros2_cfg: ``rover.ros2`` block (free-form dict for legacy
            compatibility).

    Returns:
        The validated prim path string.
    """
    return str(_resolve_ros2_bridge_options(ros2_cfg).graph_path)


__all__ = [
    "GRAPH_PATH",
    "SensorGraphHandle",
    "build_sensor_graph",
    "_build_create_nodes",
    "_build_connections",
    "_build_set_values",
    "_ns_topic",
    "_resolve_graph_path",
    "_resolve_publish_pointcloud2",
    "_resolve_publish_camera_info",
    "_resolve_publish_joint_states",
]
