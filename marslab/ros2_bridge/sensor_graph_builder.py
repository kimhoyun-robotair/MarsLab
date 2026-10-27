"""Build pure node, edge, and value data for the sensor graph.
Helpers validate USD paths and preserve shared render-product wiring.
No Isaac graph binding is imported at module load."""

from __future__ import annotations

from collections.abc import Mapping
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


def _disabled_sensor_nodes(lidar_enabled: bool, depth_enabled: bool) -> set[str]:
    return (set() if lidar_enabled else {"Lidar3DHelper"}) | (
        set() if depth_enabled else {"CamDepth", "CamPCL"}
    )


def _build_additional_camera_graph(
    namespace: str,
    camera_render_products: Mapping[str, str],
    sensor_qos_preset: str,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, Any]]]:
    """Publish each named camera from its existing shared render product.

    These camera optical frames are authored by ``build_sensor_frames`` and
    ``publish_static_sensor_tfs``. The selected primary camera remains on the
    existing configurable primary topics and is not duplicated here.
    """
    nodes: list[tuple[str, str]] = []
    edges: list[tuple[str, str]] = []
    values: list[tuple[str, Any]] = []
    for name, product_path in camera_render_products.items():
        if not name.isidentifier() or not name.isascii():
            raise ValueError(f"Invalid camera graph identifier: {name!r}")
        _validate_prim_path(f"camera {name} render product", product_path)
        rgb = f"Camera_{name}_RGB"
        info = f"Camera_{name}_Info"
        nodes.extend(
            [
                (rgb, "isaacsim.ros2.bridge.ROS2CameraHelper"),
                (info, "isaacsim.ros2.bridge.ROS2CameraInfoHelper"),
            ]
        )
        values.append((f"{rgb}.inputs:type", "rgb"))
        for node, topic in ((rgb, "image_raw"), (info, "camera_info")):
            edges.append(("OnTick.outputs:tick", f"{node}.inputs:execIn"))
            values.extend(
                [
                    (f"{node}.inputs:topicName", _ns_topic(namespace, f"cameras/{name}/{topic}")),
                    (f"{node}.inputs:frameId", f"{name}_camera_optical_frame"),
                    (f"{node}.inputs:qosProfile", sensor_qos_preset),
                    (f"{node}.inputs:renderProductPath", product_path),
                    (f"{node}.inputs:resetSimulationTimeOnStop", True),
                ]
            )
    return nodes, edges, values


def _build_create_nodes(
    *, lidar_enabled: bool = True, depth_enabled: bool = True
) -> List[Tuple[str, str]]:
    """List of ``(node_name, node_type)`` tuples for the rover graph."""
    nodes: List[Tuple[str, str]] = [
        ("OnTick", "omni.graph.action.OnPlaybackTick"),
        ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
        ("PubClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
    ]
    nodes.append(("PubJointState", "isaacsim.ros2.bridge.ROS2PublishJointState"))
    nodes += [
        ("CamRGB", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("CamDepth", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("CamPCL", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("CamInfo", "isaacsim.ros2.bridge.ROS2CameraInfoHelper"),
        ("Lidar3DHelper", "isaacsim.ros2.bridge.ROS2RtxLidarHelper"),
    ]
    disabled = _disabled_sensor_nodes(lidar_enabled, depth_enabled)
    return [node for node in nodes if node[0] not in disabled]


def _build_connections(
    *, lidar_enabled: bool = True, depth_enabled: bool = True
) -> List[Tuple[str, str]]:
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
        ("OnTick.outputs:tick", "CamRGB.inputs:execIn"),
        ("OnTick.outputs:tick", "CamDepth.inputs:execIn"),
        ("OnTick.outputs:tick", "CamPCL.inputs:execIn"),
        ("OnTick.outputs:tick", "CamInfo.inputs:execIn"),
        ("OnTick.outputs:tick", "Lidar3DHelper.inputs:execIn"),
    ]
    disabled = _disabled_sensor_nodes(lidar_enabled, depth_enabled)
    return [edge for edge in edges if edge[1].split(".", 1)[0] not in disabled]


def _build_set_values(
    ns: str,
    topics: Dict[str, str],
    camera_render_product_path: str,
    lidar_3d_render_product_path: str | None,
    *,
    articulation_root_prim_path: str,
    sensor_qos_preset: str = "SensorData",
    joint_state_qos_preset: str = "SystemDefault",
    depth_noise_enabled: bool = False,
    depth_output_enabled: bool = True,
) -> List[Tuple[str, Any]]:
    """List of ``(attr, value)`` pairs applied via SET_VALUES."""
    _validate_prim_path("articulation_root_prim_path", articulation_root_prim_path)
    import usdrt  # pyright: ignore[reportMissingImports]  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    values: List[Tuple[str, Any]] = [
        ("ReadSimTime.inputs:resetOnStop", True),
        ("PubClock.inputs:topicName", "/clock"),
    ]
    joint_state_topic = topics["joint_states"]
    values += [
        ("PubJointState.inputs:topicName", _ns_topic(ns, joint_state_topic)),
        ("PubJointState.inputs:qosProfile", joint_state_qos_preset),
        ("PubJointState.inputs:targetPrim", [usdrt.Sdf.Path(articulation_root_prim_path)]),
    ]
    values += [
        ("CamDepth.inputs:enabled", not depth_noise_enabled),
        ("CamPCL.inputs:enabled", not depth_noise_enabled),
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
    disabled = _disabled_sensor_nodes(
        lidar_3d_render_product_path is not None, depth_output_enabled
    )
    return [value for value in values if value[0].split(".", 1)[0] not in disabled]


__all__ = [
    "_build_additional_camera_graph",
    "_build_create_nodes",
    "_build_connections",
    "_build_set_values",
    "_ns_topic",
]
