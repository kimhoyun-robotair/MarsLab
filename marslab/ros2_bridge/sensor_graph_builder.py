"""Pure (offline-testable) builders for the rover ROS2 OmniGraph.

Extracted from :mod:`marslab.ros2_bridge.sensor_graph` so the
orchestration (which touches ``omni.graph.core``) stays thin and the
list-building logic can be unit-tested without Isaac Sim.

These helpers return simple Python data structures (lists of tuples)
that the orchestrator then feeds into
``og.Controller.edit(..., {CREATE_NODES, CONNECT, SET_VALUES})``.

The camera and LiDAR spawners own acquisition.  This graph only publishes from
their existing render-product paths; every camera publisher shares one path.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _ns_topic(ns: str, name: str) -> str:
    """Return ``/<ns>/<name>`` -- topic namespacing helper."""
    return f"/{ns}/{name}"


def _validate_prim_path(name: str, value: str) -> None:
    """Reject prim-path arguments that would crash ``usdrt.Sdf.Path``.

    Rules: non-empty, must start with ``/`` (USD absolute prim path
    convention), no internal whitespace.  Identical rules apply to
    every prim-path kwarg consumed by the OmniGraph helpers so a typo
    fails fast at the call site rather than surfacing as an opaque
    USD error.
    """
    if not value or not value.startswith("/") or len(value.split()) != 1:
        raise ValueError(
            f"{name} must be a non-empty USD path starting with '/' and free "
            f"of whitespace, got {value!r}"
        )


def _build_create_nodes() -> List[Tuple[str, str]]:
    """List of ``(node_name, node_type)`` tuples for the rover graph.

    The articulation always publishes ``sensor_msgs/JointState`` on
    ``<ns>/joint_states`` for the external ``robot_state_publisher``.
    """
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
    """List of ``(src_attr, dst_attr)`` pairs describing graph edges.

    All camera helpers consume the shared render product made by the camera
    spawner.  They run from one tick and use the same render-product path.

    """
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
    tf_qos_preset: str = "SystemDefault",
) -> List[Tuple[str, Any]]:
    """List of ``(attr, value)`` pairs applied via SET_VALUES.

    The ``inputs:qosProfile`` string input of every Isaac Sim ROS2
    bridge helper (``PubIMU``, ``CamRGB``, ``CamDepth``,
    ``Lidar3DHelper``, ``PubJointState``) is wired from
    ``sensor_qos_preset`` / ``tf_qos_preset``.  Callers MUST pass the
    JSON-encoded form produced by
    :func:`marslab.ros2_bridge.qos.to_omnigraph_qos_json`; the bare
    preset-name string defaults (``"SystemDefault"``, ``"SensorData"``)
    are kept only for the offline test fixture and would emit
    ``Parsing error: ... last read: 'S'`` to stderr at runtime if a
    real OmniGraph C++ writer ever consumed them.  The orchestrator
    (:mod:`marslab.ros2_bridge.sensor_graph`) always threads the JSON
    form through.

    Args:
        articulation_root_prim_path: USD path of the rover articulation
            root prim (e.g. ``/World/Rover``), forwarded to
            ``PubJointState.inputs:targetPrim``. Validated via
            :func:`_validate_prim_path` so a typo never reaches
            ``usdrt.Sdf.Path``.
        sensor_qos_preset: JSON-encoded QoS dict for IMU / camera /
            LiDAR helpers.  Build via
            :func:`marslab.ros2_bridge.qos.to_omnigraph_qos_json`.
            Default ``"SensorData"`` is a bare preset-name string kept
            only for offline test fixture compatibility.
        tf_qos_preset: JSON-encoded QoS dict for the TF publisher.
            Default ``"SystemDefault"`` carries the same offline-only
            caveat as ``sensor_qos_preset``.
    """
    _validate_prim_path("articulation_root_prim_path", articulation_root_prim_path)
    # Lazy import: ``usdrt`` ships with Isaac Sim, not the system
    # Python.  Importing at module top would break the offline unit
    # tests under ``tests/unit/``.  The tests monkeypatch
    # ``sys.modules["usdrt"]`` with a fake module, mirroring the
    # ``geometry_msgs`` pattern at
    # ``tests/unit/test_tf_broadcaster.py:14-27``.
    import usdrt  # type: ignore[import-not-found]  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    values: List[Tuple[str, Any]] = [
        ("PubClock.inputs:topicName", "/clock"),
    ]
    joint_state_topic = topics["joint_states"]
    values += [
        ("PubJointState.inputs:topicName", _ns_topic(ns, joint_state_topic)),
        ("PubJointState.inputs:qosProfile", tf_qos_preset),
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
        # Camera RGB / Depth / PointCloud2 messages carry coordinates
        # in the **optical frame convention** (Z forward, X right, Y
        # down -- REP-105) because Isaac Sim's ``ROS2CameraHelper``
        # outputs in that convention regardless of the camera prim's
        # mount orientation.  The static TF
        # ``camera_link -> camera_optical_frame`` is published by
        # ``marslab.ros2_bridge.tf_broadcaster.publish_static_sensor_tfs``;
        # frame_id here references that child frame so RViz /
        # image_pipeline / depth_image_proc see correct geometry.
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
        # NOTE: ``inputs:fullScan`` defaults to ``False`` on
        # ``ROS2RtxLidarHelper``, which means a partial sweep (only the
        # angular slice covered since the previous tick) is published
        # every simulation frame.  This is fine when the YAML
        # ``rotation_rate_hz`` roughly matches the sim tick rate (e.g.
        # 30 Hz LiDAR + 30 Hz sim = one full revolution per tick), but
        # it breaks kinematic-icp / kiss-icp / kindr-style registrators
        # for slower LiDARs (e.g. Ouster OS1 at 10 Hz on a 30 Hz sim
        # tick yields ~36 deg azimuth slices per message, which
        # de-stabilises the adaptive threshold and voxel map).
        # fullScan=True accumulates one full revolution per message —
        # enabled 2026-06-13 after kiss-icp diverged (3 m median step
        # jumps) and kinematic-icp under-estimated rotation on the
        # sector slices; see SlamRunner round-4 notes.
        ("Lidar3DHelper.inputs:fullScan", True),
        # See ``README.md`` (SLAM integration notes) for the matching
        # ``configs/rover_m2020.yaml`` knob (``lidar_3d.rotation_rate_hz``).
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
