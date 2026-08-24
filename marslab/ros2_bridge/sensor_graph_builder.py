"""Build pure node, edge, and value data for the sensor graph.
Helpers validate USD paths and preserve shared render-product wiring.
No Isaac graph binding is imported at module load."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from marslab.config.schema.rover_ros2 import resolve_ros_topic


def _ns_topic(ns: str, name: str) -> str:
    """Return ``/<ns>/<name>`` -- topic namespacing helper."""
    return resolve_ros_topic(ns, name)


def _validate_prim_path(name: str, value: str) -> None:
    """Reject prim-path arguments that would crash ``usdrt.Sdf.Path``."""
    if not value or not value.startswith("/") or len(value.split()) != 1:
        raise ValueError(
            f"{name} must be a non-empty USD path starting with '/' and free "
            f"of whitespace, got {value!r}"
        )


def _build_create_nodes() -> List[Tuple[str, str]]:
    """List of ``(node_name, node_type)`` tuples for the rover graph."""
    nodes: List[Tuple[str, str]] = [
        ("OnTick", "omni.graph.action.OnPlaybackTick"),
        ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
        ("PubClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
    ]
    nodes.append(("PubJointState", "isaacsim.ros2.bridge.ROS2PublishJointState"))
    nodes += [
        ("ReadIMU", "isaacsim.sensors.physics.IsaacReadIMU"),
        ("PubIMU", "isaacsim.ros2.bridge.ROS2PublishImu"),
        ("CamRGB", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("CamDepth", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("CamPCL", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("CamInfo", "isaacsim.ros2.bridge.ROS2CameraInfoHelper"),
        ("Lidar3DHelper", "isaacsim.ros2.bridge.ROS2RtxLidarHelper"),
    ]
    return nodes


def _build_connections() -> List[Tuple[str, str]]:
    """List of ``(src_attr, dst_attr)`` pairs describing graph edges."""
    edges: List[Tuple[str, str]] = [
        ("OnTick.outputs:tick", "PubClock.inputs:execIn"),
        ("ReadSimTime.outputs:simulationTime", "PubClock.inputs:timeStamp"),
    ]
    edges += [
        ("OnTick.outputs:tick", "PubJointState.inputs:execIn"),
        ("ReadSimTime.outputs:simulationTime", "PubJointState.inputs:timeStamp"),
    ]
    edges += [
        ("OnTick.outputs:tick", "ReadIMU.inputs:execIn"),
        ("ReadIMU.outputs:execOut", "PubIMU.inputs:execIn"),
        ("ReadIMU.outputs:angVel", "PubIMU.inputs:angularVelocity"),
        ("ReadIMU.outputs:linAcc", "PubIMU.inputs:linearAcceleration"),
        ("ReadIMU.outputs:orientation", "PubIMU.inputs:orientation"),
        ("ReadSimTime.outputs:simulationTime", "PubIMU.inputs:timeStamp"),
        ("OnTick.outputs:tick", "CamRGB.inputs:execIn"),
        ("OnTick.outputs:tick", "CamDepth.inputs:execIn"),
        ("OnTick.outputs:tick", "CamPCL.inputs:execIn"),
        ("OnTick.outputs:tick", "CamInfo.inputs:execIn"),
        ("OnTick.outputs:tick", "Lidar3DHelper.inputs:execIn"),
    ]
    return edges


def _build_set_values(
    ns: str,
    topics: Dict[str, str],
    imu_prim_path: str,
    camera_render_product_path: str,
    lidar_3d_render_product_path: str,
    *,
    articulation_root_prim_path: str,
    sensor_qos_preset: str = "SensorData",
    joint_state_qos_preset: str = "SystemDefault",
) -> List[Tuple[str, Any]]:
    """List of ``(attr, value)`` pairs applied via SET_VALUES."""
    _validate_prim_path("articulation_root_prim_path", articulation_root_prim_path)
    import usdrt  # pyright: ignore[reportMissingImports]  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    values: List[Tuple[str, Any]] = [
        ("PubClock.inputs:topicName", "/clock"),
    ]
    joint_state_topic = topics["joint_states"]
    values += [
        ("PubJointState.inputs:topicName", _ns_topic(ns, joint_state_topic)),
        ("PubJointState.inputs:qosProfile", joint_state_qos_preset),
        ("PubJointState.inputs:targetPrim", [usdrt.Sdf.Path(articulation_root_prim_path)]),
    ]
    values += [
        ("ReadIMU.inputs:imuPrim", [imu_prim_path]),
        ("PubIMU.inputs:topicName", _ns_topic(ns, topics["imu"])),
        ("PubIMU.inputs:frameId", "imu_link"),
        ("PubIMU.inputs:qosProfile", sensor_qos_preset),
        ("CamRGB.inputs:resetSimulationTimeOnStop", True),
        ("CamDepth.inputs:resetSimulationTimeOnStop", True),
        ("CamPCL.inputs:resetSimulationTimeOnStop", True),
        ("CamInfo.inputs:resetSimulationTimeOnStop", True),
        ("Lidar3DHelper.inputs:resetSimulationTimeOnStop", True),
        ("CamRGB.inputs:type", "rgb"),
        ("CamRGB.inputs:topicName", _ns_topic(ns, topics["rgb"])),
        ("CamRGB.inputs:frameId", "camera_optical_frame"),
        ("CamRGB.inputs:qosProfile", sensor_qos_preset),
        ("CamRGB.inputs:renderProductPath", camera_render_product_path),
        ("CamDepth.inputs:type", "depth"),
        ("CamDepth.inputs:topicName", _ns_topic(ns, topics["depth"])),
        ("CamDepth.inputs:frameId", "camera_optical_frame"),
        ("CamDepth.inputs:qosProfile", sensor_qos_preset),
        ("CamDepth.inputs:renderProductPath", camera_render_product_path),
        ("CamPCL.inputs:type", "depth_pcl"),
        ("CamPCL.inputs:topicName", _ns_topic(ns, topics["points"])),
        ("CamPCL.inputs:frameId", "camera_optical_frame"),
        ("CamPCL.inputs:qosProfile", sensor_qos_preset),
        ("CamPCL.inputs:renderProductPath", camera_render_product_path),
        ("CamInfo.inputs:topicName", _ns_topic(ns, topics["camera_info"])),
        ("CamInfo.inputs:frameId", "camera_optical_frame"),
        ("CamInfo.inputs:qosProfile", sensor_qos_preset),
        ("CamInfo.inputs:renderProductPath", camera_render_product_path),
        ("Lidar3DHelper.inputs:topicName", _ns_topic(ns, topics["lidar"])),
        ("Lidar3DHelper.inputs:frameId", "lidar_link"),
        ("Lidar3DHelper.inputs:type", "point_cloud"),
        ("Lidar3DHelper.inputs:fullScan", True),
        ("Lidar3DHelper.inputs:qosProfile", sensor_qos_preset),
        ("Lidar3DHelper.inputs:renderProductPath", lidar_3d_render_product_path),
    ]
    return values


__all__ = [
    "_build_create_nodes",
    "_build_connections",
    "_build_set_values",
    "_ns_topic",
]
