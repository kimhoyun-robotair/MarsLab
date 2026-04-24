"""Pure (offline-testable) builders for the Stage-3 ROS2 OmniGraph.

Extracted from :mod:`marslab.ros2_bridge.sensor_graph` during R4-5 so
the orchestration (which touches ``omni.graph.core``) stays thin and
the list-building logic can be unit-tested without Isaac Sim.

These helpers return simple Python data structures (lists of tuples)
that the orchestrator then feeds into
``og.Controller.edit(..., {CREATE_NODES, CONNECT, SET_VALUES})``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _ns_topic(ns: str, name: str) -> str:
    """Return ``/<ns>/<name>`` -- topic namespacing helper."""
    return f"/{ns}/{name}"


def _build_create_nodes(include_lidar_2d: bool = False) -> List[Tuple[str, str]]:
    """List of ``(node_name, node_type)`` tuples for the Stage-3 graph.

    Args:
        include_lidar_2d: When True, appends the ``RPLidar2D`` +
            ``Lidar2DHelper`` pair so a 2-D RTX LiDAR sensor can publish
            ``sensor_msgs/LaserScan``.
    """
    nodes: List[Tuple[str, str]] = [
        ("OnTick", "omni.graph.action.OnPlaybackTick"),
        ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
        ("PubClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
        ("PubTF", "isaacsim.ros2.bridge.ROS2PublishRawTransformTree"),
        ("ReadIMU", "isaacsim.sensors.physics.IsaacReadIMU"),
        ("PubIMU", "isaacsim.ros2.bridge.ROS2PublishImu"),
        ("RPCamera", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
        ("CamRGB", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("RPDepth", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
        ("CamDepth", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("RPLidar3D", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
        ("Lidar3DHelper", "isaacsim.ros2.bridge.ROS2RtxLidarHelper"),
    ]
    if include_lidar_2d:
        nodes += [
            ("RPLidar2D", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
            ("Lidar2DHelper", "isaacsim.ros2.bridge.ROS2RtxLidarHelper"),
        ]
    return nodes


def _build_connections(include_lidar_2d: bool = False) -> List[Tuple[str, str]]:
    """List of ``(src_attr, dst_attr)`` pairs describing graph edges."""
    edges: List[Tuple[str, str]] = [
        ("OnTick.outputs:tick", "PubClock.inputs:execIn"),
        ("ReadSimTime.outputs:simulationTime", "PubClock.inputs:timeStamp"),
        ("OnTick.outputs:tick", "PubTF.inputs:execIn"),
        ("ReadSimTime.outputs:simulationTime", "PubTF.inputs:timeStamp"),
        ("OnTick.outputs:tick", "ReadIMU.inputs:execIn"),
        ("ReadIMU.outputs:execOut", "PubIMU.inputs:execIn"),
        ("ReadIMU.outputs:angVel", "PubIMU.inputs:angularVelocity"),
        ("ReadIMU.outputs:linAcc", "PubIMU.inputs:linearAcceleration"),
        ("ReadIMU.outputs:orientation", "PubIMU.inputs:orientation"),
        ("ReadSimTime.outputs:simulationTime", "PubIMU.inputs:timeStamp"),
        ("OnTick.outputs:tick", "RPCamera.inputs:execIn"),
        ("RPCamera.outputs:execOut", "CamRGB.inputs:execIn"),
        ("RPCamera.outputs:renderProductPath", "CamRGB.inputs:renderProductPath"),
        ("OnTick.outputs:tick", "RPDepth.inputs:execIn"),
        ("RPDepth.outputs:execOut", "CamDepth.inputs:execIn"),
        ("RPDepth.outputs:renderProductPath", "CamDepth.inputs:renderProductPath"),
        ("OnTick.outputs:tick", "RPLidar3D.inputs:execIn"),
        ("RPLidar3D.outputs:execOut", "Lidar3DHelper.inputs:execIn"),
        ("RPLidar3D.outputs:renderProductPath", "Lidar3DHelper.inputs:renderProductPath"),
    ]
    if include_lidar_2d:
        edges += [
            ("OnTick.outputs:tick", "RPLidar2D.inputs:execIn"),
            ("RPLidar2D.outputs:execOut", "Lidar2DHelper.inputs:execIn"),
            ("RPLidar2D.outputs:renderProductPath", "Lidar2DHelper.inputs:renderProductPath"),
        ]
    return edges


def _build_set_values(
    ns: str,
    topics: Dict[str, str],
    imu_prim_path: str,
    camera_prim_path: str,
    camera_resolution: Tuple[int, int],
    lidar_3d_prim_path: str,
    lidar_2d_prim_path: Optional[str] = None,
    *,
    sensor_qos_preset: str = "SensorData",
    tf_qos_preset: str = "SystemDefault",
) -> List[Tuple[str, Any]]:
    """List of ``(attr, value)`` pairs applied via SET_VALUES.

    The articulation joint TF is published on ``/tf_raw`` so it does
    not collide with the rclpy ``odom->base_link`` publisher on
    ``/tf`` per user directive.

    When ``lidar_2d_prim_path`` is provided **and** ``topics["scan"]`` is
    defined, the 2-D LiDAR pair is appended (``laser_scan`` type).

    Reviewer 2 #04 (2026-04-24): the ``inputs:qosProfile`` string input
    of every Isaac Sim ROS2 bridge helper (``PubIMU``, ``CamRGB``,
    ``CamDepth``, ``Lidar3DHelper``, ``Lidar2DHelper``, ``PubTF``) is
    now wired from ``sensor_qos_preset`` / ``tf_qos_preset``.  The
    caller should pass the preset returned by
    :func:`marslab.ros2_bridge.qos.to_omnigraph_qos_preset` so the
    OmniGraph side agrees with the rclpy-side QoS whenever a bundled
    preset exists.  Defaults match the rclpy-side defaults
    (``SensorData`` for sensors, ``SystemDefault`` for TF).

    Args:
        sensor_qos_preset: Isaac Sim preset name for IMU / camera /
            LiDAR helpers.  Must be one of the bundled presets
            (``"SystemDefault"``, ``"SensorData"``, ``"ServicesDefault"``,
            ``"ParameterEvents"``).  No validation here because the
            OmniGraph node itself rejects unknown strings at
            ``og.Controller.edit`` time.
        tf_qos_preset: Isaac Sim preset for the TF publisher.
    """
    values: List[Tuple[str, Any]] = [
        ("PubClock.inputs:topicName", "/clock"),
        ("PubTF.inputs:topicName", "/tf_raw"),
        ("PubTF.inputs:qosProfile", tf_qos_preset),
        ("ReadIMU.inputs:imuPrim", [imu_prim_path]),
        ("PubIMU.inputs:topicName", _ns_topic(ns, topics["imu"])),
        ("PubIMU.inputs:frameId", "imu_link"),
        ("PubIMU.inputs:qosProfile", sensor_qos_preset),
        ("RPCamera.inputs:cameraPrim", [camera_prim_path]),
        ("RPCamera.inputs:width", int(camera_resolution[0])),
        ("RPCamera.inputs:height", int(camera_resolution[1])),
        ("CamRGB.inputs:type", "rgb"),
        ("CamRGB.inputs:topicName", _ns_topic(ns, topics["rgb"])),
        ("CamRGB.inputs:frameId", "camera_link"),
        ("CamRGB.inputs:qosProfile", sensor_qos_preset),
        ("RPDepth.inputs:cameraPrim", [camera_prim_path]),
        ("RPDepth.inputs:width", int(camera_resolution[0])),
        ("RPDepth.inputs:height", int(camera_resolution[1])),
        ("CamDepth.inputs:type", "depth"),
        ("CamDepth.inputs:topicName", _ns_topic(ns, topics["depth"])),
        ("CamDepth.inputs:frameId", "camera_link"),
        ("CamDepth.inputs:qosProfile", sensor_qos_preset),
        ("RPLidar3D.inputs:cameraPrim", [lidar_3d_prim_path]),
        ("Lidar3DHelper.inputs:topicName", _ns_topic(ns, topics["lidar"])),
        ("Lidar3DHelper.inputs:frameId", "lidar_link"),
        ("Lidar3DHelper.inputs:type", "point_cloud"),
        ("Lidar3DHelper.inputs:qosProfile", sensor_qos_preset),
    ]
    if lidar_2d_prim_path is not None and "scan" in topics:
        values += [
            ("RPLidar2D.inputs:cameraPrim", [lidar_2d_prim_path]),
            ("Lidar2DHelper.inputs:topicName", _ns_topic(ns, topics["scan"])),
            ("Lidar2DHelper.inputs:frameId", "scan_frame"),
            ("Lidar2DHelper.inputs:type", "laser_scan"),
            ("Lidar2DHelper.inputs:qosProfile", sensor_qos_preset),
        ]
    return values


__all__ = [
    "_build_create_nodes",
    "_build_connections",
    "_build_set_values",
    "_ns_topic",
]
