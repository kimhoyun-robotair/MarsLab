"""Orchestrate the rover sensor OmniGraph and ROS publishers.
The graph reuses acquisition identities created by sensor spawners.
Isaac graph imports occur only during graph construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from marslab.ros2_bridge.sensor_graph_builder import (
    _build_connections,
    _build_create_nodes,
    _build_set_values,
    _ns_topic,
)
from marslab.sensors.camera_spawner import CameraSpawnHandles
from marslab.sensors.imu_spawner import IMUSpawnHandles
from marslab.sensors.lidar_3d_spawner import Lidar3DSpawnHandles

GRAPH_PATH = "/World/Stage3ROS2Graph"


@dataclass
class SensorGraphHandle:
    """Bundle returned by :func:`build_sensor_graph`."""

    graph_path: str
    graph: Any


def _resolve_ros2_bridge_options(ros2_cfg: Dict[str, Any]) -> Any:
    """Validate the schema-known subset of ``ros2_cfg`` ONCE."""
    from marslab.config.schema.rover_ros2 import (
        Ros2BridgeConfig,
        RosRatesConfig,
        RosTopicsConfig,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    schema_ros2_cfg = {
        key: value for key, value in ros2_cfg.items() if key in Ros2BridgeConfig.model_fields
    }
    schema_ros2_cfg["topics"] = {
        key: value
        for key, value in dict(ros2_cfg["topics"]).items()
        if key in RosTopicsConfig.model_fields
    }
    schema_ros2_cfg["rates"] = {
        key: value
        for key, value in dict(ros2_cfg["rates"]).items()
        if key in RosRatesConfig.model_fields
    }
    return Ros2BridgeConfig.model_validate(schema_ros2_cfg)


def build_sensor_graph(
    ros2_cfg: Dict[str, Any],
    camera_acquisition: CameraSpawnHandles,
    lidar_3d_acquisition: Lidar3DSpawnHandles,
    imu_acquisition: IMUSpawnHandles,
    articulation_root_prim_path: str,
    depth_sensor_cfg: Optional[Dict[str, Any]] = None,
) -> SensorGraphHandle:
    """Build the rover ROS2 OmniGraph."""
    import omni.graph.core as og  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    ns = str(ros2_cfg["namespace"])
    topics = dict(ros2_cfg["topics"])
    options = _resolve_ros2_bridge_options(ros2_cfg)
    graph_path = options.graph_path
    sensor_preset, tf_preset = _build_qos_presets(options)
    camera_render_product_path = camera_acquisition.render_product_path
    if not camera_render_product_path:
        raise ValueError("Camera render-product path must be non-empty")

    keys = og.Controller.Keys
    graph_handle, _, _, _ = og.Controller.edit(
        {"graph_path": graph_path, "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: _build_create_nodes(),
            keys.CONNECT: _build_connections(),
            keys.SET_VALUES: _build_set_values(
                ns=ns,
                topics=topics,
                imu_prim_path=imu_acquisition.imu_prim_path,
                camera_render_product_path=camera_render_product_path,
                lidar_3d_render_product_path=lidar_3d_acquisition.render_product_path,
                articulation_root_prim_path=articulation_root_prim_path,
                sensor_qos_preset=sensor_preset,
                tf_qos_preset=tf_preset,
            ),
        },
    )

    if depth_sensor_cfg is not None and bool(depth_sensor_cfg.get("enabled")):
        try:
            _apply_depth_sensor_schema(camera_render_product_path, depth_sensor_cfg)
        except (
            RuntimeError,
            AttributeError,
            ImportError,
        ) as exc:  # pragma: no cover - runtime-only fallback
            import logging  # noqa: PLC0415  -- defer until needed

            logging.getLogger(__name__).warning(
                "Depth-sensor schema apply skipped: %s.  Falling back to "
                "the renderer's raw DistanceToImagePlane AOV.",
                exc,
            )

    return SensorGraphHandle(graph_path=graph_path, graph=graph_handle)


_DEPTH_SENSOR_SCHEMA_ATTRS: Dict[str, str] = {
    "baseline_mm": "omni:rtx:post:depthSensor:baselineMM",
    "min_distance_m": "omni:rtx:post:depthSensor:minDistance",
    "max_distance_m": "omni:rtx:post:depthSensor:maxDistance",
    "noise_mean": "omni:rtx:post:depthSensor:noiseMean",
    "noise_sigma": "omni:rtx:post:depthSensor:noiseSigma",
    "confidence_threshold": "omni:rtx:post:depthSensor:confidenceThreshold",
    "max_disparity_pixel": "omni:rtx:post:depthSensor:maxDisparityPixel",
}


def _apply_depth_sensor_schema(
    camera_render_product_path: str,
    depth_sensor_cfg: Dict[str, Any],
) -> None:
    """Apply ``OmniSensorDepthSensorSingleViewAPI`` to the shared render product."""
    from isaacsim.core.utils.prims import (
        get_prim_at_path,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    rp_prim = get_prim_at_path(camera_render_product_path)
    if rp_prim is None or not rp_prim.IsValid():
        raise RuntimeError(
            f"Render product prim at {camera_render_product_path!r} is invalid; cannot apply "
            "OmniSensorDepthSensorSingleViewAPI"
        )

    rp_prim.ApplyAPI("OmniSensorDepthSensorSingleViewAPI")
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
    """Map a validated :class:`Ros2BridgeConfig` to OmniGraph QoS JSON strings."""
    from marslab.ros2_bridge.qos import (
        to_omnigraph_qos_json,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    return to_omnigraph_qos_json(options.sensor_qos), to_omnigraph_qos_json(options.tf_qos)


__all__ = [
    "GRAPH_PATH",
    "SensorGraphHandle",
    "build_sensor_graph",
    "_build_create_nodes",
    "_build_connections",
    "_build_set_values",
    "_ns_topic",
]
