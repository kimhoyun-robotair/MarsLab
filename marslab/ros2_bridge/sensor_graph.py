"""Stage-3 ROS2 OmniGraph orchestrator.

Composes a single action graph that drives:

* ``/clock`` from Isaac Sim simulation time.
* Articulation joint TF on a dedicated ``/tf_raw`` topic, kept
  separate from the rclpy ``odom -> base_link`` broadcaster on ``/tf``
  in :mod:`marslab.ros2_bridge.odometry_publisher`.  Sharing one
  ``/tf`` was tried (Apr-25 fix-up) and rolled back because the two
  publishers produced duplicated / out-of-phase frames in RViz and
  Nav2.  The split is enforced by user feedback (see memory
  ``feedback_no_tf_consolidation``).
* IMU (``sensor_msgs/Imu``).
* Camera RGB + Depth via independent render products.
* 3-D LiDAR point cloud.

The graph path + node names mirror the legacy Stage-1 graph to keep
the debugger / ros2 graph view familiar.

R4-5 (2026-04-22): list-building helpers (``_build_create_nodes`` /
``_build_connections`` / ``_build_set_values``) moved to
:mod:`marslab.ros2_bridge.sensor_graph_builder` so they can be unit
tested without Isaac Sim.  Re-exported below for backward compatibility
with existing tests and callers.

R4-5 extension (2026-04-23): ``GRAPH_PATH`` migrated from a module
constant to ``Ros2BridgeConfig.graph_path`` (see
:mod:`marslab.config.schema.ros2_bridge`).  The module constant is kept
as the canonical default so legacy imports (``from marslab.ros2_bridge
import GRAPH_PATH``) still resolve, but ``build_sensor_graph`` now
reads ``ros2_cfg["graph_path"]`` first and only falls back when the
YAML key is absent.
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


def build_sensor_graph(
    ros2_cfg: Dict[str, Any],
    camera_prim_path: str,
    camera_resolution: Tuple[int, int],
    lidar_3d_prim_path: str,
    imu_prim_path: str,
    articulation_root_prim_path: str,
    parent_anchor_prim_path: str,
    lidar_2d_prim_path: Optional[str] = None,
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
            of ``world -> base_link -> ...``.  S3 fix (2026-04-27).
        lidar_2d_prim_path: Optional USD path of the 2-D RTX LiDAR prim.
            When provided and ``topics["scan"]`` is set in ``ros2_cfg``,
            a ``RPLidar2D``/``Lidar2DHelper`` pair is added with
            ``type="laser_scan"``.

    Returns:
        :class:`SensorGraphHandle`.
    """
    import omni.graph.core as og

    ns = str(ros2_cfg["namespace"])
    topics = dict(ros2_cfg["topics"])
    graph_path = _resolve_graph_path(ros2_cfg)
    sensor_preset, tf_preset = _resolve_qos_presets(ros2_cfg)
    include_2d = lidar_2d_prim_path is not None and "scan" in topics
    include_pcl = _resolve_publish_pointcloud2(ros2_cfg) and "points" in topics

    keys = og.Controller.Keys
    graph_handle, _, _, _ = og.Controller.edit(
        {"graph_path": graph_path, "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: _build_create_nodes(
                include_lidar_2d=include_2d,
                include_pointcloud2=include_pcl,
            ),
            keys.CONNECT: _build_connections(
                include_lidar_2d=include_2d,
                include_pointcloud2=include_pcl,
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
            ),
        },
    )
    return SensorGraphHandle(graph_path=graph_path, graph=graph_handle)


def _resolve_qos_presets(ros2_cfg: Dict[str, Any]) -> Tuple[str, str]:
    """Return ``(sensor_preset, tf_preset)`` Isaac-Sim preset strings.

    The OmniGraph helpers (``ROS2PublishImu``, ``ROS2CameraHelper``,
    ``ROS2RtxLidarHelper``, ``ROS2PublishRawTransformTree``) accept a
    preset *name* on ``inputs:qosProfile`` rather than a structured
    QoSProfile.  This helper reads the matching ``sensor_qos`` and
    ``tf_qos`` YAML blocks (or the schema defaults) and maps each to
    the closest bundled preset via
    :func:`marslab.ros2_bridge.qos.to_omnigraph_qos_json`.

    Reviewer 2 #04 (2026-04-24).  Kept separate from
    :func:`_resolve_graph_path` so tests can exercise it without
    also instantiating pydantic graph-path validation.
    """
    # Local imports mirror the pattern used by ``_resolve_graph_path``
    # so this module stays importable without rclpy / pydantic schema
    # on the path.
    from marslab.config.schema.ros2_bridge import QoSProfileConfig, Ros2BridgeConfig
    from marslab.ros2_bridge.qos import to_omnigraph_qos_json

    defaults = Ros2BridgeConfig()

    def _pick(name: str, fallback: QoSProfileConfig) -> QoSProfileConfig:
        raw = ros2_cfg.get(name) if isinstance(ros2_cfg, dict) else None
        if raw is None:
            return fallback
        return QoSProfileConfig.model_validate(raw)

    sensor_cfg = _pick("sensor_qos", defaults.sensor_qos)
    tf_cfg = _pick("tf_qos", defaults.tf_qos)
    return to_omnigraph_qos_json(sensor_cfg), to_omnigraph_qos_json(tf_cfg)


def _resolve_publish_pointcloud2(ros2_cfg: Dict[str, Any]) -> bool:
    """Return whether to wire the depth-derived ``CamPCL`` helper.

    Reads ``ros2_cfg["publish_pointcloud2"]`` when present (validated via
    :class:`Ros2BridgeConfig`) and falls back to the schema default
    (``True`` -- RealSense-style RGB-D PointCloud2 ON) when absent.

    Day 2 sprint task F (2026-04-25): keeping the resolver parallel to
    :func:`_resolve_graph_path` means the orchestrator never reads the
    raw dict directly -- pydantic enforces the bool type for both ad-hoc
    dict callers and YAML-loaded callers.

    Args:
        ros2_cfg: ``rover.ros2`` block (free-form dict for legacy
            compatibility).

    Returns:
        ``True`` to append the ``CamPCL`` node + edges + values, else
        ``False`` to skip the PointCloud2 publisher entirely.
    """
    from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

    raw = ros2_cfg.get("publish_pointcloud2") if isinstance(ros2_cfg, dict) else None
    if raw is None:
        return Ros2BridgeConfig().publish_pointcloud2
    validated = Ros2BridgeConfig(publish_pointcloud2=bool(raw))
    return validated.publish_pointcloud2


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
    # Local import keeps the schema dependency optional for the rare
    # caller that imports ``sensor_graph`` without the full ``marslab``
    # config tree (e.g. a minimal integration test harness).
    from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

    raw = ros2_cfg.get("graph_path") if isinstance(ros2_cfg, dict) else None
    if raw is None:
        return GRAPH_PATH
    validated = Ros2BridgeConfig(graph_path=str(raw))
    return validated.graph_path


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
]
