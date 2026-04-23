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
with existing tests and callers.  The original inline definitions are
preserved as DISABLED comments per ``feedback_no_delete_comment``.
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

GRAPH_PATH = "/World/Stage3ROS2Graph"


@dataclass
class SensorGraphHandle:
    """Bundle returned by :func:`build_sensor_graph`."""

    graph_path: str
    graph: Any


# DISABLED R4-5 (2026-04-22): list-building helpers moved to
# marslab.ros2_bridge.sensor_graph_builder. Retained as comments per
# feedback_no_delete_comment to preserve rollback.
#
# def _ns_topic(ns: str, name: str) -> str:
#     return f"/{ns}/{name}"
#
#
# def _build_create_nodes() -> List[Tuple[str, str]]:
#     return [
#         ("OnTick", "omni.graph.action.OnPlaybackTick"),
#         ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
#         ("PubClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
#         ("PubTF", "isaacsim.ros2.bridge.ROS2PublishRawTransformTree"),
#         ("ReadIMU", "isaacsim.sensors.physics.IsaacReadIMU"),
#         ("PubIMU", "isaacsim.ros2.bridge.ROS2PublishImu"),
#         ("RPCamera", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
#         ("CamRGB", "isaacsim.ros2.bridge.ROS2CameraHelper"),
#         ("RPDepth", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
#         ("CamDepth", "isaacsim.ros2.bridge.ROS2CameraHelper"),
#         ("RPLidar3D", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
#         ("Lidar3DHelper", "isaacsim.ros2.bridge.ROS2RtxLidarHelper"),
#     ]
#
#
# def _build_connections() -> List[Tuple[str, str]]:
#     return [
#         ("OnTick.outputs:tick", "PubClock.inputs:execIn"),
#         ("ReadSimTime.outputs:simulationTime", "PubClock.inputs:timeStamp"),
#         ("OnTick.outputs:tick", "PubTF.inputs:execIn"),
#         ("ReadSimTime.outputs:simulationTime", "PubTF.inputs:timeStamp"),
#         ("OnTick.outputs:tick", "ReadIMU.inputs:execIn"),
#         ("ReadIMU.outputs:execOut", "PubIMU.inputs:execIn"),
#         ("ReadIMU.outputs:angVel", "PubIMU.inputs:angularVelocity"),
#         ("ReadIMU.outputs:linAcc", "PubIMU.inputs:linearAcceleration"),
#         ("ReadIMU.outputs:orientation", "PubIMU.inputs:orientation"),
#         ("ReadSimTime.outputs:simulationTime", "PubIMU.inputs:timeStamp"),
#         ("OnTick.outputs:tick", "RPCamera.inputs:execIn"),
#         ("RPCamera.outputs:execOut", "CamRGB.inputs:execIn"),
#         ("RPCamera.outputs:renderProductPath", "CamRGB.inputs:renderProductPath"),
#         ("OnTick.outputs:tick", "RPDepth.inputs:execIn"),
#         ("RPDepth.outputs:execOut", "CamDepth.inputs:execIn"),
#         ("RPDepth.outputs:renderProductPath", "CamDepth.inputs:renderProductPath"),
#         ("OnTick.outputs:tick", "RPLidar3D.inputs:execIn"),
#         ("RPLidar3D.outputs:execOut", "Lidar3DHelper.inputs:execIn"),
#         ("RPLidar3D.outputs:renderProductPath", "Lidar3DHelper.inputs:renderProductPath"),
#     ]
#
#
# def _build_set_values(
#     ns: str,
#     topics: Dict[str, str],
#     imu_prim_path: str,
#     camera_prim_path: str,
#     camera_resolution: Tuple[int, int],
#     lidar_3d_prim_path: str,
# ) -> List[Tuple[str, Any]]:
#     return [
#         ("PubClock.inputs:topicName", "/clock"),
#         ("PubTF.inputs:topicName", "/tf_raw"),
#         ("ReadIMU.inputs:imuPrim", [imu_prim_path]),
#         ("PubIMU.inputs:topicName", _ns_topic(ns, topics["imu"])),
#         ("PubIMU.inputs:frameId", "imu_link"),
#         ("RPCamera.inputs:cameraPrim", [camera_prim_path]),
#         ("RPCamera.inputs:width", int(camera_resolution[0])),
#         ("RPCamera.inputs:height", int(camera_resolution[1])),
#         ("CamRGB.inputs:type", "rgb"),
#         ("CamRGB.inputs:topicName", _ns_topic(ns, topics["rgb"])),
#         ("CamRGB.inputs:frameId", "camera_link"),
#         ("RPDepth.inputs:cameraPrim", [camera_prim_path]),
#         ("RPDepth.inputs:width", int(camera_resolution[0])),
#         ("RPDepth.inputs:height", int(camera_resolution[1])),
#         ("CamDepth.inputs:type", "depth"),
#         ("CamDepth.inputs:topicName", _ns_topic(ns, topics["depth"])),
#         ("CamDepth.inputs:frameId", "camera_link"),
#         ("RPLidar3D.inputs:cameraPrim", [lidar_3d_prim_path]),
#         ("Lidar3DHelper.inputs:topicName", _ns_topic(ns, topics["lidar"])),
#         ("Lidar3DHelper.inputs:frameId", "lidar_link"),
#         ("Lidar3DHelper.inputs:type", "point_cloud"),
#     ]


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

    keys = og.Controller.Keys
    graph_handle, _, _, _ = og.Controller.edit(
        {"graph_path": GRAPH_PATH, "evaluator_name": "execution"},
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
    return SensorGraphHandle(graph_path=GRAPH_PATH, graph=graph_handle)


__all__ = [
    "GRAPH_PATH",
    "SensorGraphHandle",
    "build_sensor_graph",
    "_build_create_nodes",
    "_build_connections",
    "_build_set_values",
    "_ns_topic",
]
