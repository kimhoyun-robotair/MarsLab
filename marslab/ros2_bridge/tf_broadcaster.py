"""Static TF publisher for sensor frames.

The Isaac-Sim OmniGraph ``ROS2PublishTransformTree`` node publishes
only the articulation joint chain -- sensor prims (camera, LiDAR, IMU)
are created by MarsLab in Isaac Sim after URDF import, so their frames
never appear on ``/tf_raw``.  slam_toolbox / Nav2 need these frames.
This module publishes a one-shot ``/tf_static`` batch covering every
sensor declared in the rover YAML.

Body-frame convention
---------------------

The published ``base_link`` frame is X-rolled (RPY ≈ [180°, 0°, 0°])
relative to ``odom``.  This compensates for the NASA JPL m2020 URDF's
non-standard link frame author convention.  YAML ``local_translation``
for sensors is authored in this rolled body frame: ``+Z_yaml = -Z_world``
(down) and ``+Y_yaml = -Y_world`` (right).  This broadcaster emits the
YAML values identity (no Y/Z flip) -- the X-roll on the spawn parent
provides the single canonical chain rotation; a second flip here would
double-correct.  See ``docs/frame_conventions.md`` for full background.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence, Tuple

SensorFrameSpec = Tuple[str, Sequence[float]]
"""``(child_frame_id, local_translation_xyz)`` pair."""


def build_static_sensor_transforms(
    sensor_frames: Iterable[SensorFrameSpec],
    parent_frame_id: str = "base_link",
) -> List[Any]:
    """Return a list of ``TransformStamped`` messages for static TF.

    Kept separate from :func:`publish_static_sensor_tfs` so callers
    can inspect or mutate the transforms before broadcast (e.g. for
    unit tests that inject a fake ``TransformStamped``).
    """
    from geometry_msgs.msg import (
        TransformStamped,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    out: List[Any] = []
    for child_frame, local_t in sensor_frames:
        if len(local_t) != 3:
            raise ValueError(
                f"local_translation for {child_frame} must have 3 elements, got {len(local_t)}"
            )
        msg = TransformStamped()
        msg.header.frame_id = parent_frame_id
        msg.child_frame_id = child_frame
        # YAML ``local_translation`` is authored in the X-rolled
        # base_link body frame.  Broadcast identity (no Y/Z flip):
        # the X-roll on the spawn parent is the single canonical
        # rotation.  See ``docs/frame_conventions.md``.
        msg.transform.translation.x = float(local_t[0])
        msg.transform.translation.y = float(local_t[1])
        msg.transform.translation.z = float(local_t[2])
        msg.transform.rotation.w = 1.0
        msg.transform.rotation.x = 0.0
        msg.transform.rotation.y = 0.0
        msg.transform.rotation.z = 0.0
        out.append(msg)
    return out


def build_camera_optical_frame_transform(
    camera_frame_id: str = "camera_link",
    optical_frame_id: str = "camera_optical_frame",
) -> Any:
    """Return ``TransformStamped`` from ``camera_link`` to optical frame.

    RGB / Depth images and PointCloud2 from Isaac Sim's
    ``ROS2CameraHelper`` come out in the **optical frame convention**
    (Z forward, X right, Y down -- REP-105).  Without a separate
    optical frame, RViz would show the point cloud rotated 90° because
    the frame label would not match the data layout.

    This helper publishes the canonical ROS rotation that maps
    ``camera_link`` → ``camera_optical_frame``.  Image / depth /
    pointcloud frame_ids should reference ``camera_optical_frame`` so
    downstream consumers (RViz, ``image_pipeline``,
    ``depth_image_proc``) interpret the data correctly.

    Rotation: RPY = (-π/2, 0, -π/2) (intrinsic ZYX), matching
    ``tf_transformations.quaternion_from_euler(-1.5708, 0, -1.5708)``
    = (x, y, z, w) = (-0.5, 0.5, -0.5, 0.5).

    Args:
        camera_frame_id: Parent frame name (the REP-103 mount frame).
            Defaults to ``"camera_link"``.
        optical_frame_id: Child frame name.  Defaults to
            ``"camera_optical_frame"``.

    Returns:
        A populated ``geometry_msgs/TransformStamped``.
    """
    from geometry_msgs.msg import (
        TransformStamped,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    msg = TransformStamped()
    msg.header.frame_id = camera_frame_id
    msg.child_frame_id = optical_frame_id
    msg.transform.translation.x = 0.0
    msg.transform.translation.y = 0.0
    msg.transform.translation.z = 0.0
    msg.transform.rotation.x = -0.5
    msg.transform.rotation.y = 0.5
    msg.transform.rotation.z = -0.5
    msg.transform.rotation.w = 0.5
    return msg


def publish_static_sensor_tfs(
    node: Any,
    sensor_frames: Iterable[SensorFrameSpec],
    parent_frame_id: str = "base_link",
    *,
    qos: Optional[Any] = None,
) -> Any:
    """Publish ``/tf_static`` for each ``(child_frame, xyz)`` pair.

    Args:
        node: ``rclpy.node.Node`` used to create the
            ``StaticTransformBroadcaster``.
        sensor_frames: Iterable of ``(child_frame_id, xyz)`` pairs.
        parent_frame_id: Parent frame for all transforms.
        qos: Optional ``rclpy.qos.QoSProfile`` forwarded to the
            ``tf2_ros.StaticTransformBroadcaster`` constructor.
            ``StaticTransformBroadcaster`` takes a ``qos`` keyword
            argument in tf2_ros >= 0.25 (Humble+).  When ``None`` the
            tf2_ros default (RELIABLE + TRANSIENT_LOCAL + KEEP_LAST
            100) is used -- late-joining subscribers still latch the
            transforms.

    Returns:
        The :class:`tf2_ros.StaticTransformBroadcaster` kept alive so
        the caller can hold a reference (the node does not own it).
    """
    from tf2_ros import (
        StaticTransformBroadcaster,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    if qos is not None:
        # tf2_ros older than 0.25 does not accept a ``qos`` keyword;
        # fall back so MarsLab boots on a mismatched install rather
        # than crashing at startup.
        try:
            broadcaster = StaticTransformBroadcaster(node, qos=qos)
        except TypeError:
            broadcaster = StaticTransformBroadcaster(node)
    else:
        broadcaster = StaticTransformBroadcaster(node)
    msgs = build_static_sensor_transforms(sensor_frames, parent_frame_id)
    # Publish camera_optical_frame as a child of camera_link so RViz /
    # image_pipeline / depth_image_proc consume PointCloud2 in the
    # optical convention they expect.  Driven by the actual broadcast
    # list (msgs) so this works whether the caller passed a list, a
    # generator, or any other Iterable.
    if any(m.child_frame_id == "camera_link" for m in msgs):
        msgs.append(build_camera_optical_frame_transform("camera_link", "camera_optical_frame"))
    broadcaster.sendTransform(msgs)
    return broadcaster
