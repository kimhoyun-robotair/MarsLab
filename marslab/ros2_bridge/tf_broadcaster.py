"""Static TF publisher for sensor frames.

The Isaac-Sim OmniGraph ``ROS2PublishRawTransformTree`` node publishes
only the articulation joint chain — sensor prims (camera, LiDAR, IMU)
are created by MarsLab in Isaac Sim after URDF import, so their frames
never appear on ``/tf``.  slam_toolbox / Nav2 need these frames.  This
module publishes a one-shot ``/tf_static`` batch covering every sensor
declared in the rover YAML.

Body-frame convention note
--------------------------

The M2020 USD is imported with a 180° X-roll so the chassis "up" maps
to world ``+Z``.  The YAML ``local_translation`` is authored in the
post-roll body frame where ``+Y_body = -Y_world`` and ``+Z_body = -Z_world``.
We therefore flip Y and Z when broadcasting the transform so the
broadcast matches the Isaac Sim pose of each sensor prim.
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
    from geometry_msgs.msg import TransformStamped

    out: List[Any] = []
    for child_frame, local_t in sensor_frames:
        if len(local_t) != 3:
            raise ValueError(
                f"local_translation for {child_frame} must have 3 elements, got {len(local_t)}"
            )
        msg = TransformStamped()
        msg.header.frame_id = parent_frame_id
        msg.child_frame_id = child_frame
        msg.transform.translation.x = float(local_t[0])
        # 180° X-roll: body Y/Z axes flip relative to world.
        msg.transform.translation.y = -float(local_t[1])
        msg.transform.translation.z = -float(local_t[2])
        msg.transform.rotation.w = 1.0
        msg.transform.rotation.x = 0.0
        msg.transform.rotation.y = 0.0
        msg.transform.rotation.z = 0.0
        out.append(msg)
    return out


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
            100) is used — late-joining subscribers still latch the
            transforms.  Reviewer 2 #04 (2026-04-24) surfaces this
            knob for YAML-driven tuning.

    Returns:
        The :class:`tf2_ros.StaticTransformBroadcaster` kept alive so
        the caller can hold a reference (the node does not own it).
    """
    from tf2_ros import StaticTransformBroadcaster

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
    broadcaster.sendTransform(msgs)
    return broadcaster
