"""Pure helper that builds the sensor TF frame list for the runtime.

Extracted from ``marslab/main.py`` so the dict-to-list
construction is exercised by an offline unit test instead of only at
Isaac Sim startup.

The output is a list of ``dict`` records (one per sensor) carrying the
fields ``child_frame``, ``local_translation``, and
``local_orientation_rpy_deg``.  The URDF parent-link field is
intentionally NOT threaded through here: the YAML schema validates
that field but the runtime mounting code attaches every sensor to the
chassis rigid body discovered by
:func:`marslab.robots.rover.find_rigid_body_path`.  See
``tests/unit/test_tf_extrinsic_consistency.py`` for the gap assertion.

The current
:func:`marslab.ros2_bridge.tf_broadcaster.publish_static_sensor_tfs`
signature only consumes ``(child_frame, local_translation)`` tuples;
:func:`sensor_frames_to_tuples` is provided as a thin adapter so the
runtime can hand the validated dicts straight to the broadcaster
without duplicating the iteration logic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

# ``(child_frame, sensor_key)`` -- the canonical child-frame name and
# the YAML key it sources from. Keeping this tuple-of-tuples local
# avoids a runtime import of the schema module just to iterate four
# constants.
_SENSOR_FRAME_BINDINGS: Tuple[Tuple[str, str], ...] = (
    ("camera_link", "camera"),
    ("lidar_link", "lidar_3d"),
    ("scan_frame", "lidar_2d"),
    ("imu_link", "imu"),
)


def _resolve_sensor_block(sensors_cfg: Dict[str, Any], sensor_key: str) -> Dict[str, Any]:
    """Return the dict for ``sensors_cfg[sensor_key]`` (or empty).

    ``sensor_key`` ``"lidar_3d"`` falls back to ``"lidar"`` to match the
    legacy YAML alias accepted by :mod:`marslab.main`.
    """
    block = sensors_cfg.get(sensor_key)
    if block is None and sensor_key == "lidar_3d":
        block = sensors_cfg.get("lidar")
    if not isinstance(block, dict):
        return {}
    return block


def build_sensor_frames(
    sensors_cfg: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Construct the static-TF frame list from the rover sensor block.

    Args:
        sensors_cfg: The ``rover.sensors`` block. Each sensor that is
            present contributes one frame record. Missing sensors are
            skipped silently so an asymmetric scenario (e.g. no 2D
            LiDAR) does not raise.

    Returns:
        Ordered list of dicts, one per declared sensor, with keys:

        * ``child_frame`` -- TF child frame id (e.g. ``"camera_link"``).
        * ``local_translation`` -- ``[x, y, z]`` offset in the rolled
          base_link body frame, copied verbatim from the sensor block.
        * ``local_orientation_rpy_deg`` -- ``[roll, pitch, yaw]``
          (degrees, ZYX intrinsic); defaults to ``[0.0, 0.0, 0.0]``
          when the sensor block omits it.
    """
    frames: List[Dict[str, Any]] = []
    for child_frame, sensor_key in _SENSOR_FRAME_BINDINGS:
        block = _resolve_sensor_block(sensors_cfg, sensor_key)
        if not block:
            continue
        if "local_translation" not in block:
            continue
        frames.append(
            {
                "child_frame": child_frame,
                "local_translation": list(block["local_translation"]),
                "local_orientation_rpy_deg": list(
                    block.get("local_orientation_rpy_deg", [0.0, 0.0, 0.0])
                ),
            }
        )
    return frames


def sensor_frames_to_tuples(
    frames: Sequence[Dict[str, Any]],
) -> List[Tuple[str, List[float], List[float]]]:
    """Adapt :func:`build_sensor_frames` output to the broadcaster API.

    :func:`marslab.ros2_bridge.tf_broadcaster.publish_static_sensor_tfs`
    consumes ``(child_frame, xyz, rpy_deg)`` tuples so the ROS broadcast
    quaternion matches the USD prim orient set by
    ``marslab.sensors.sensor_spawner`` (camera/IMU YAML
    ``local_orientation_rpy_deg = [180, 0, 0]``).  The 3-tuple shape
    is required for the camera_link -> camera_optical_frame chain to
    land RGB-D PointCloud2 in the correct REP-103 axis -- a 2-tuple
    (identity rotation) leaves camera_link inheriting the
    Body_Chassis graphics-style axis and the depth_pcl frame ends up
    pointing at the sky in RViz.
    """
    return [
        (
            str(frame["child_frame"]),
            list(frame["local_translation"]),
            list(frame.get("local_orientation_rpy_deg", [0.0, 0.0, 0.0])),
        )
        for frame in frames
    ]


__all__ = ["build_sensor_frames", "sensor_frames_to_tuples"]
