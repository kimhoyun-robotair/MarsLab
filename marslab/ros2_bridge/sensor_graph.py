"""Orchestrate the rover sensor OmniGraph and ROS publishers.
The graph reuses acquisition identities created by sensor spawners.
Isaac graph imports occur only during graph construction."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np

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
    raw_imu_graph_path: str
    raw_imu_graph: Any

    def initialize_raw_imu(self) -> None:
        """Initialize raw IMU publishing after construction or Stop."""
        import omni.graph.core as og

        og.Controller.set(
            og.Controller.attribute(
                f"{self.raw_imu_graph_path}/OnImpulseEvent.state:enableImpulse"
            ),
            True,
        )
        og.Controller.evaluate_sync(self.raw_imu_graph)

    def publish_raw_imu(
        self,
        stamp_seconds: float,
        linear_acceleration: np.ndarray,
        angular_velocity: np.ndarray,
        orientation_xyzw: np.ndarray,
    ) -> None:
        """Publish the same acquired IMU sample supplied to the noisy stream."""
        import omni.graph.core as og

        if not math.isfinite(stamp_seconds) or stamp_seconds < 0.0:
            raise ValueError("IMU acquisition time must be finite and non-negative")
        publisher_path = f"{self.raw_imu_graph_path}/PubIMU"
        og.Controller.edit(
            self.raw_imu_graph,
            {
                og.Controller.Keys.SET_VALUES: [
                    (f"{publisher_path}.inputs:timeStamp", stamp_seconds),
                    (f"{publisher_path}.inputs:linearAcceleration", linear_acceleration.tolist()),
                    (f"{publisher_path}.inputs:angularVelocity", angular_velocity.tolist()),
                    (f"{publisher_path}.inputs:orientation", orientation_xyzw.tolist()),
                    (f"{self.raw_imu_graph_path}/OnImpulseEvent.state:enableImpulse", True),
                ],
            },
        )
        og.Controller.evaluate_sync(self.raw_imu_graph)


def _resolve_ros2_bridge_options(ros2_cfg: Dict[str, Any]) -> Any:
    """Validate the schema-known subset of ``ros2_cfg`` ONCE."""
    from marslab.config.schema.rover_ros2 import (
        Ros2BridgeConfig,
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
    return Ros2BridgeConfig.model_validate(schema_ros2_cfg)


def build_sensor_graph(
    ros2_cfg: Dict[str, Any],
    camera_acquisition: CameraSpawnHandles,
    lidar_3d_acquisition: Lidar3DSpawnHandles,
    imu_acquisition: IMUSpawnHandles,
    articulation_root_prim_path: str,
) -> SensorGraphHandle:
    """Build the rover ROS2 OmniGraph."""
    import omni.graph.core as og  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    ns = str(ros2_cfg["namespace"])
    topics = dict(ros2_cfg["topics"])
    options = _resolve_ros2_bridge_options(ros2_cfg)
    graph_path = options.graph_path
    sensor_preset, joint_state_preset = _build_qos_presets(options)
    camera_render_product_path = camera_acquisition.render_product_path
    if not camera_render_product_path:
        raise ValueError("Camera render-product path must be non-empty")
    if not imu_acquisition.imu_prim_path:
        raise ValueError("IMU prim path must be non-empty")

    keys = og.Controller.Keys
    graph_handle, _, _, _ = og.Controller.edit(
        {"graph_path": graph_path, "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: _build_create_nodes(),
            keys.CONNECT: _build_connections(),
            keys.SET_VALUES: _build_set_values(
                ns=ns,
                topics=topics,
                camera_render_product_path=camera_render_product_path,
                lidar_3d_render_product_path=lidar_3d_acquisition.render_product_path,
                articulation_root_prim_path=articulation_root_prim_path,
                sensor_qos_preset=sensor_preset,
                joint_state_qos_preset=joint_state_preset,
                depth_noise_enabled=camera_acquisition.depth_noise_enabled,
            ),
        },
    )

    raw_imu_graph_path = f"{graph_path}RawIMU"
    raw_imu_graph, _, _, _ = og.Controller.edit(
        {
            "graph_path": raw_imu_graph_path,
            "evaluator_name": "execution",
            "pipeline_stage": og.GraphPipelineStage.GRAPH_PIPELINE_STAGE_ONDEMAND,
        },
        {
            keys.CREATE_NODES: [
                ("OnImpulseEvent", "omni.graph.action.OnImpulseEvent"),
                ("PubIMU", "isaacsim.ros2.bridge.ROS2PublishImu"),
            ],
            keys.CONNECT: [
                ("OnImpulseEvent.outputs:execOut", "PubIMU.inputs:execIn"),
            ],
            keys.SET_VALUES: [
                ("PubIMU.inputs:topicName", _ns_topic(ns, topics["imu"])),
                ("PubIMU.inputs:frameId", "imu_link"),
                ("PubIMU.inputs:qosProfile", sensor_preset),
            ],
        },
    )
    return SensorGraphHandle(
        graph_path=graph_path,
        graph=graph_handle,
        raw_imu_graph_path=raw_imu_graph_path,
        raw_imu_graph=raw_imu_graph,
    )


def _build_qos_presets(options: Any) -> Tuple[str, str]:
    """Map a validated :class:`Ros2BridgeConfig` to OmniGraph QoS JSON strings."""
    from marslab.ros2_bridge.qos import (
        to_omnigraph_qos_json,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    return (
        to_omnigraph_qos_json(options.sensor_qos),
        to_omnigraph_qos_json(options.joint_state_qos),
    )


__all__ = [
    "GRAPH_PATH",
    "SensorGraphHandle",
    "build_sensor_graph",
    "_build_create_nodes",
    "_build_connections",
    "_build_set_values",
    "_ns_topic",
]
