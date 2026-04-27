"""Pure (offline-testable) builders for the Stage-3 ROS2 OmniGraph.

Extracted from :mod:`marslab.ros2_bridge.sensor_graph` so the
orchestration (which touches ``omni.graph.core``) stays thin and the
list-building logic can be unit-tested without Isaac Sim.

These helpers return simple Python data structures (lists of tuples)
that the orchestrator then feeds into
``og.Controller.edit(..., {CREATE_NODES, CONNECT, SET_VALUES})``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


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


def _build_create_nodes(
    include_lidar_2d: bool = False,
    include_pointcloud2: bool = False,
    include_camera_info: bool = False,
) -> List[Tuple[str, str]]:
    """List of ``(node_name, node_type)`` tuples for the Stage-3 graph.

    Args:
        include_lidar_2d: When True, appends the ``RPLidar2D`` +
            ``Lidar2DHelper`` pair so a 2-D RTX LiDAR sensor can publish
            ``sensor_msgs/LaserScan``.
        include_pointcloud2: When True, appends a second
            ``isaacsim.ros2.bridge.ROS2CameraHelper`` node (``CamPCL``)
            wired off the existing depth render product (``RPDepth``)
            with ``inputs:type='depth_pcl'`` so the RGB-D camera publishes
            a ``sensor_msgs/PointCloud2`` topic at the depth-camera rate.
            Source: ``isaacsim/exts/isaacsim.ros2.bridge/isaacsim/ros2/
            bridge/ogn/python/nodes/OgnROS2CameraHelper.py:141-155`` --
            the ``depth_pcl`` token routes through ``ROS2PublishPointCloud``
            with ``DistanceToImagePlane`` as the source render variable.
        include_camera_info: When True, appends a
            ``isaacsim.ros2.bridge.ROS2CameraInfoHelper`` node (``CamInfo``)
            fed off the RGB render product (``RPCamera``) so the camera
            publishes ``sensor_msgs/CameraInfo`` (intrinsics K / P / R /
            D, width, height) alongside ``rgb/image_raw``.  Source:
            ``isaacsim/exts/isaacsim.ros2.bridge/docs/ogn/
            OgnROS2CameraInfoHelper.rst:21`` -- the helper auto-derives
            the projection matrices from the USD ``Camera`` prim's focal
            length / aperture / clipping range, so YAML never duplicates
            them.
    """
    nodes: List[Tuple[str, str]] = [
        ("OnTick", "omni.graph.action.OnPlaybackTick"),
        ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
        ("PubClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
        # The *non-Raw* publisher auto-enumerates the rover articulation
        # chain when the articulation root prim is wired via
        # ``inputs:targetPrims``.  The Raw variant only emits a single
        # user-supplied transform per tick (its design, not a misuse).
        # Citations: ``OgnROS2PublishTransformTree.rst:21,45``; canonical
        # wiring at ``isaacsim/.../tests/test_pose_tree.py:72``.
        ("PubTF", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
        ("ReadIMU", "isaacsim.sensors.physics.IsaacReadIMU"),
        ("PubIMU", "isaacsim.ros2.bridge.ROS2PublishImu"),
        ("RPCamera", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
        ("CamRGB", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("RPDepth", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
        ("CamDepth", "isaacsim.ros2.bridge.ROS2CameraHelper"),
        ("RPLidar3D", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
        ("Lidar3DHelper", "isaacsim.ros2.bridge.ROS2RtxLidarHelper"),
    ]
    if include_pointcloud2:
        # Re-uses the RPDepth render product, no new IsaacCreateRenderProduct.
        # The helper consumes depth + camera intrinsics internally so only
        # a second ROS2CameraHelper sibling to ``CamDepth`` is needed.
        nodes.append(("CamPCL", "isaacsim.ros2.bridge.ROS2CameraHelper"))
    if include_camera_info:
        # Re-uses the RPCamera render product (RGB) -- no extra
        # IsaacCreateRenderProduct.  The helper extracts intrinsics from
        # the underlying USD camera prim every tick.
        nodes.append(("CamInfo", "isaacsim.ros2.bridge.ROS2CameraInfoHelper"))
    if include_lidar_2d:
        nodes += [
            ("RPLidar2D", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
            ("Lidar2DHelper", "isaacsim.ros2.bridge.ROS2RtxLidarHelper"),
        ]
    return nodes


def _build_connections(
    include_lidar_2d: bool = False,
    include_pointcloud2: bool = False,
    include_camera_info: bool = False,
) -> List[Tuple[str, str]]:
    """List of ``(src_attr, dst_attr)`` pairs describing graph edges.

    Args:
        include_lidar_2d: Append 2-D LiDAR edges when the
            ``Lidar2DHelper`` pair is present.
        include_pointcloud2: Append the ``CamPCL`` edges so the
            depth-derived PointCloud2 helper triggers off ``OnTick`` and
            shares the existing ``RPDepth`` render product.
        include_camera_info: Append the ``CamInfo`` edges so the
            CameraInfo helper triggers off ``OnTick`` and shares the
            existing ``RPCamera`` (RGB) render product.
    """
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
    if include_pointcloud2:
        # Trigger ``CamPCL`` off the same ``OnTick`` pulse so the depth
        # helper and the PointCloud2 helper run in lock-step on the same
        # render product.  Re-using ``RPDepth.outputs:renderProductPath``
        # avoids a second ``IsaacCreateRenderProduct`` (which would double
        # the rendering cost) -- the OmniGraph allows multiple
        # ``ROS2CameraHelper`` consumers per render product.
        edges += [
            ("OnTick.outputs:tick", "CamPCL.inputs:execIn"),
            ("RPDepth.outputs:renderProductPath", "CamPCL.inputs:renderProductPath"),
        ]
    if include_camera_info:
        # Trigger ``CamInfo`` off the same ``OnTick`` pulse and reuse
        # ``RPCamera`` (RGB) render product so intrinsics ship in
        # lock-step with ``rgb/image_raw``.  ``image_proc`` /
        # ``depth_image_proc`` / RTAB-Map all expect timestamp-aligned
        # ``CameraInfo`` per RGB frame.
        edges += [
            ("OnTick.outputs:tick", "CamInfo.inputs:execIn"),
            ("RPCamera.outputs:renderProductPath", "CamInfo.inputs:renderProductPath"),
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
    *,
    articulation_root_prim_path: str,
    parent_anchor_prim_path: str,
    lidar_2d_prim_path: Optional[str] = None,
    sensor_qos_preset: str = "SensorData",
    tf_qos_preset: str = "SystemDefault",
    include_pointcloud2: bool = False,
    include_camera_info: bool = False,
) -> List[Tuple[str, Any]]:
    """List of ``(attr, value)`` pairs applied via SET_VALUES.

    The articulation joint TF is published on ``/tf_raw`` while the
    rclpy side publishes ``odom -> base_link`` on the canonical ``/tf``.
    The two topics are deliberately kept separate: empirically, sharing
    one ``/tf`` between an OmniGraph ``PubTF`` and an rclpy
    ``TransformBroadcaster`` produces duplicated frames in RViz and
    Nav2's TF buffer (the two backends serialise identical frames out
    of phase, and downstream consumers see ``/tf`` jitter that breaks
    SLAM / localisation).  The split mirrors the historical Stage-1
    layout; do not propose merging them again unless the user
    explicitly asks.

    Consumers that need the joint chain (RViz ``RobotModel`` display,
    debug tools) can run a one-line ``tf2_ros static_transform_publisher``
    style relay or subscribe to ``/tf_raw`` directly.

    When ``lidar_2d_prim_path`` is provided **and** ``topics["scan"]`` is
    defined, the 2-D LiDAR pair is appended (``laser_scan`` type).

    The ``inputs:qosProfile`` string input of every Isaac Sim ROS2
    bridge helper (``PubIMU``, ``CamRGB``, ``CamDepth``,
    ``Lidar3DHelper``, ``Lidar2DHelper``, ``PubTF``) is wired from
    ``sensor_qos_preset`` / ``tf_qos_preset``.  Production callers
    MUST pass the JSON-encoded form produced by
    :func:`marslab.ros2_bridge.qos.to_omnigraph_qos_json`; the bare
    preset-name defaults (``"SystemDefault"``, ``"SensorData"``) are
    legacy fixture values retained only so existing offline tests keep
    passing -- the C++ writer parses them as JSON and emits
    ``Parsing error: ... last read: 'S'`` to stderr at runtime, so
    relying on the defaults is a regression of the JSON-format fix.
    The orchestrator (:mod:`marslab.ros2_bridge.sensor_graph`) always
    threads the JSON form through, so production paths are safe.

    Args:
        articulation_root_prim_path: USD path of the rover articulation
            root prim (e.g. ``/World/Rover``).  Required: forwarded to
            ``PubTF.inputs:targetPrims`` so the non-Raw
            ``ROS2PublishTransformTree`` auto-walks every joint and
            publishes the entire link chain.  Validated via
            :func:`_validate_prim_path` so a typo never reaches
            ``usdrt.Sdf.Path``.
        parent_anchor_prim_path: USD path of the stationary ``odom``
            anchor prim created by
            :func:`marslab.ros2_bridge.tf_nameoverrides.create_odom_anchor`.
            Forwarded to ``PubTF.inputs:parentPrim`` so the non-Raw
            publisher emits ``odom -> base_link -> ...`` instead of the
            default ``world -> base_link -> ...``.  Validated via
            :func:`_validate_prim_path`.  Citation:
            ``OgnROS2PublishTransformTree.rst:41``;
            ``test_pose_tree.py:154-156, :215-229``.
        sensor_qos_preset: JSON-encoded QoS dict for IMU / camera /
            LiDAR helpers.  Build via
            :func:`marslab.ros2_bridge.qos.to_omnigraph_qos_json`.
            Default ``"SensorData"`` is a legacy bare preset name kept
            only for offline test fixture compatibility.
        tf_qos_preset: JSON-encoded QoS dict for the TF publisher.
            Default ``"SystemDefault"`` carries the same legacy caveat
            as ``sensor_qos_preset``.
        include_pointcloud2: When True **and** ``topics["points"]`` is
            present, append the ``CamPCL`` value bindings
            (``inputs:type='depth_pcl'``, topic name from
            ``topics["points"]``, ``frameId='camera_link'`` to share the
            existing depth helper TF, and the same sensor QoS preset as
            the other camera helpers).  ``frameId`` deliberately reuses
            ``camera_link`` rather than introducing a separate
            ``camera_optical_frame`` so the PointCloud2 publisher joins
            the existing static TF tree broadcast by
            ``publish_static_sensor_tfs`` without requiring a new TF
            link.
        include_camera_info: When True **and** ``topics["camera_info"]``
            is present, append the ``CamInfo`` value bindings
            (topic name from ``topics["camera_info"]``,
            ``frameId='camera_optical_frame'`` to match the RGB / Depth /
            PointCloud2 headers, and the same sensor QoS preset as the
            other camera helpers).  ``ROS2CameraInfoHelper`` derives
            K / P / R / D + width / height from the underlying
            ``RPCamera`` render product, so no width / height is
            forwarded here -- the CameraInfo helper reads the same
            render product the RGB helper reads.
    """
    _validate_prim_path("articulation_root_prim_path", articulation_root_prim_path)
    _validate_prim_path("parent_anchor_prim_path", parent_anchor_prim_path)
    # Lazy import: ``usdrt`` ships with Isaac Sim, not the system
    # Python.  Importing at module top would break the offline unit
    # tests under ``tests/unit/``.  The tests monkeypatch
    # ``sys.modules["usdrt"]`` with a fake module, mirroring the
    # ``geometry_msgs`` pattern at
    # ``tests/unit/test_tf_broadcaster.py:14-27``.
    import usdrt  # type: ignore[import-not-found]  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    values: List[Tuple[str, Any]] = [
        ("PubClock.inputs:topicName", "/clock"),
        # Articulation joint chain on a dedicated ``/tf_raw`` topic so it
        # does not collide with the rclpy ``odom -> base_link``
        # broadcaster on ``/tf``.  Sharing one topic was tried and
        # produced duplicated/out-of-phase frames in RViz and Nav2.
        # See ``_build_set_values`` docstring.
        ("PubTF.inputs:topicName", "/tf_raw"),
        ("PubTF.inputs:qosProfile", tf_qos_preset),
        # ``targetPrims`` is a ``target`` list input
        # (``OgnROS2PublishTransformTree.rst:45-46``).  Wrapping with
        # ``usdrt.Sdf.Path`` matches the canonical sample at
        # ``test_pose_tree.py:77-84``.  Passing the articulation root
        # prim makes the node auto-enumerate the joint chain.
        ("PubTF.inputs:targetPrims", [usdrt.Sdf.Path(articulation_root_prim_path)]),
        # ``parentPrim`` is a single-prim ``target`` relationship
        # (``OgnROS2PublishTransformTree.rst:41``).  Wiring it to a
        # stationary ``odom`` anchor with
        # ``isaac:nameOverride="odom"`` makes the published chain read
        # ``odom -> base_link -> ...`` (REP-105 canonical) instead of
        # the default ``world -> base_link -> ...``.  Override
        # propagation pinned by ``test_pose_tree.py:154-156, :215-229``.
        ("PubTF.inputs:parentPrim", [usdrt.Sdf.Path(parent_anchor_prim_path)]),
        ("ReadIMU.inputs:imuPrim", [imu_prim_path]),
        ("PubIMU.inputs:topicName", _ns_topic(ns, topics["imu"])),
        ("PubIMU.inputs:frameId", "imu_link"),
        ("PubIMU.inputs:qosProfile", sensor_qos_preset),
        ("RPCamera.inputs:cameraPrim", [camera_prim_path]),
        ("RPCamera.inputs:width", int(camera_resolution[0])),
        ("RPCamera.inputs:height", int(camera_resolution[1])),
        # Camera RGB / Depth / PointCloud2 messages carry coordinates
        # in the **optical frame convention** (Z forward, X right, Y
        # down -- REP-105) because Isaac Sim's ``ROS2CameraHelper``
        # outputs in that convention regardless of the camera prim's
        # mount orientation.  The static TF
        # ``camera_link → camera_optical_frame`` is published by
        # ``marslab.ros2_bridge.tf_broadcaster.publish_static_sensor_tfs``;
        # frame_id here references that child frame so RViz /
        # image_pipeline / depth_image_proc see correct geometry.
        ("CamRGB.inputs:type", "rgb"),
        ("CamRGB.inputs:topicName", _ns_topic(ns, topics["rgb"])),
        ("CamRGB.inputs:frameId", "camera_optical_frame"),
        ("CamRGB.inputs:qosProfile", sensor_qos_preset),
        ("RPDepth.inputs:cameraPrim", [camera_prim_path]),
        ("RPDepth.inputs:width", int(camera_resolution[0])),
        ("RPDepth.inputs:height", int(camera_resolution[1])),
        ("CamDepth.inputs:type", "depth"),
        ("CamDepth.inputs:topicName", _ns_topic(ns, topics["depth"])),
        ("CamDepth.inputs:frameId", "camera_optical_frame"),
        ("CamDepth.inputs:qosProfile", sensor_qos_preset),
        ("RPLidar3D.inputs:cameraPrim", [lidar_3d_prim_path]),
        ("Lidar3DHelper.inputs:topicName", _ns_topic(ns, topics["lidar"])),
        ("Lidar3DHelper.inputs:frameId", "lidar_link"),
        ("Lidar3DHelper.inputs:type", "point_cloud"),
        ("Lidar3DHelper.inputs:qosProfile", sensor_qos_preset),
    ]
    if include_pointcloud2 and "points" in topics:
        values += [
            ("CamPCL.inputs:type", "depth_pcl"),
            ("CamPCL.inputs:topicName", _ns_topic(ns, topics["points"])),
            # Point cloud in optical frame convention.  RViz expects
            # the frame_id label to match the data's coordinate
            # handedness; ``camera_optical_frame`` is the REP-105
            # child of camera_link broadcast via
            # ``tf_broadcaster.publish_static_sensor_tfs``.
            ("CamPCL.inputs:frameId", "camera_optical_frame"),
            ("CamPCL.inputs:qosProfile", sensor_qos_preset),
        ]
    if include_camera_info and "camera_info" in topics:
        # ``ROS2CameraInfoHelper`` only exposes topicName / frameId /
        # qosProfile + the stereo-pair inputs; intrinsics are derived
        # from the render product internally
        # (OgnROS2CameraInfoHelper.rst:32-52).  ``frameId`` matches the
        # RGB / Depth / PointCloud2 headers (REP-105 optical frame) so
        # ``image_proc`` / ``depth_image_proc`` / RTAB-Map / ORB-SLAM3
        # see consistent geometry.
        values += [
            ("CamInfo.inputs:topicName", _ns_topic(ns, topics["camera_info"])),
            ("CamInfo.inputs:frameId", "camera_optical_frame"),
            ("CamInfo.inputs:qosProfile", sensor_qos_preset),
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
