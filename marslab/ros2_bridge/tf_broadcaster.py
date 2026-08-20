"""Publish static TF for chassis-mounted sensor frames.
Camera optical orientation is represented explicitly in transforms.
ROS and NumPy dependencies stay deferred where runtime-only."""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union

SensorFrameSpec = Union[
    Tuple[str, Sequence[float]],
    Tuple[str, Sequence[float], Sequence[float]],
]
"""``(child_frame_id, xyz)`` or ``(child_frame_id, xyz, rpy_deg)`` tuple."""


def build_static_sensor_transforms(
    sensor_frames: Iterable[SensorFrameSpec],
    parent_frame_id: str = "Body_Chassis",
) -> List[Any]:
    """Return a list of ``TransformStamped`` messages for static TF."""
    import math  # noqa: PLC0415  -- stdlib, deferred to keep parity with msg import

    from geometry_msgs.msg import (
        TransformStamped,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    from marslab.quaternion import (
        rpy_to_quat,
    )  # noqa: PLC0415  -- avoids numpy import at module load for pure-config callers

    out: List[Any] = []
    for spec in sensor_frames:
        if len(spec) == 2:
            child_frame, local_t = spec
            rpy_deg: Sequence[float] = (0.0, 0.0, 0.0)
        elif len(spec) == 3:
            child_frame, local_t, rpy_deg = spec
        else:
            raise ValueError(
                f"sensor frame spec must be 2- or 3-tuple, got length {len(spec)}: {spec!r}"
            )
        if len(local_t) != 3:
            raise ValueError(
                f"local_translation for {child_frame} must have 3 elements, got {len(local_t)}"
            )
        if len(rpy_deg) != 3:
            raise ValueError(f"rpy_deg for {child_frame} must have 3 elements, got {len(rpy_deg)}")
        msg = TransformStamped()
        msg.header.frame_id = parent_frame_id
        msg.child_frame_id = child_frame
        msg.transform.translation.x = float(local_t[0])
        msg.transform.translation.y = float(local_t[1])
        msg.transform.translation.z = float(local_t[2])
        qw, qx, qy, qz = rpy_to_quat(
            math.radians(float(rpy_deg[0])),
            math.radians(float(rpy_deg[1])),
            math.radians(float(rpy_deg[2])),
        )
        msg.transform.rotation.w = qw
        msg.transform.rotation.x = qx
        msg.transform.rotation.y = qy
        msg.transform.rotation.z = qz
        out.append(msg)
    return out


def build_camera_optical_frame_transform(
    camera_frame_id: str = "camera_link",
    optical_frame_id: str = "camera_optical_frame",
) -> Any:
    """Return ``TransformStamped`` from ``camera_link`` to optical frame."""
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
    parent_frame_id: str = "Body_Chassis",
    *,
    qos: Optional[Any] = None,
) -> Any:
    """Publish ``/tf_static`` for each ``(child_frame, xyz)`` pair."""
    from tf2_ros import (
        StaticTransformBroadcaster,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    if qos is not None:
        try:
            broadcaster = StaticTransformBroadcaster(node, qos=qos)
        except TypeError:
            broadcaster = StaticTransformBroadcaster(node)
    else:
        broadcaster = StaticTransformBroadcaster(node)
    msgs = build_static_sensor_transforms(sensor_frames, parent_frame_id)
    if any(m.child_frame_id == "camera_link" for m in msgs):
        msgs.append(build_camera_optical_frame_transform("camera_link", "camera_optical_frame"))
    broadcaster.sendTransform(msgs)
    return broadcaster
