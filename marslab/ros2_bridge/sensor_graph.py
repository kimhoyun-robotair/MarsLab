"""Stage-3 ROS2 OmniGraph orchestrator.

Composes a single action graph that drives:

* ``/clock`` from Isaac Sim simulation time.
* Articulation joint TF on ``/tf_raw`` (kept separate from the rclpy
  ``odom->base_link`` publisher on ``/tf`` per user directive).
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
from typing import Any, Dict, Tuple

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

    Returns:
        :class:`SensorGraphHandle`.
    """
    import omni.graph.core as og

    ns = str(ros2_cfg["namespace"])
    topics = dict(ros2_cfg["topics"])
    graph_path = _resolve_graph_path(ros2_cfg)

    keys = og.Controller.Keys
    graph_handle, _, _, _ = og.Controller.edit(
        {"graph_path": graph_path, "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: _build_create_nodes(),
            keys.CONNECT: _build_connections(),
            keys.SET_VALUES: _build_set_values(
                ns=ns,
                topics=topics,
                imu_prim_path=imu_prim_path,
                camera_prim_path=camera_prim_path,
                camera_resolution=camera_resolution,
                lidar_3d_prim_path=lidar_3d_prim_path,
            ),
        },
    )
    return SensorGraphHandle(graph_path=graph_path, graph=graph_handle)


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
]
