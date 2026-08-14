"""Pure helper that builds the sensor TF frame list for the runtime.

Extracted from ``marslab/main.py`` so frame construction
construction is exercised by an offline unit test instead of only at
Isaac Sim startup.

The output is a list of typed records (one per enabled sensor) carrying the
fields ``child_frame``, ``local_translation``, and
``local_orientation_rpy_deg``.  The URDF parent-link field is
intentionally NOT threaded through here: the YAML schema validates
that field but the runtime mounting code attaches every sensor to the
chassis rigid body discovered by
:func:`marslab.robots.rover.find_rigid_body_path`.  See
``tests/unit/test_tf_extrinsic_consistency.py`` for the gap assertion.

The current
:func:`marslab.ros2_bridge.tf_broadcaster.publish_static_sensor_tfs`
signature only consumes frame tuples;
:func:`sensor_frames_to_tuples` is provided as a thin adapter so the
runtime can hand the validated dicts straight to the broadcaster
without duplicating the iteration logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple, assert_never

from marslab.config.schema.rover_sensors import (
    DisabledSensorConfig,
    EnabledCameraConfig,
    EnabledImuConfig,
    EnabledLidar2DConfig,
    EnabledLidar3DConfig,
    SensorsConfig,
)


@dataclass(frozen=True, slots=True)
class SensorFrame:
    child_frame: str
    local_translation: tuple[float, float, float]
    local_orientation_rpy_deg: tuple[float, float, float]


def build_sensor_frames(
    sensors_cfg: SensorsConfig,
) -> List[SensorFrame]:
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
    frames: List[SensorFrame] = []
    bindings = (
        ("camera_link", sensors_cfg.camera),
        ("lidar_link", sensors_cfg.lidar_3d),
        ("scan_frame", sensors_cfg.lidar_2d),
        ("imu_link", sensors_cfg.imu),
    )
    for child_frame, sensor in bindings:
        match sensor:
            case DisabledSensorConfig():
                continue
            case (
                EnabledCameraConfig()
                | EnabledLidar3DConfig()
                | EnabledLidar2DConfig()
                | EnabledImuConfig()
            ):
                frames.append(
                    SensorFrame(
                        child_frame=child_frame,
                        local_translation=sensor.local_translation,
                        local_orientation_rpy_deg=sensor.local_orientation_rpy_deg,
                    )
                )
            case unreachable:
                assert_never(unreachable)
    return frames


def sensor_frames_to_tuples(
    frames: Sequence[SensorFrame],
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
            frame.child_frame,
            list(frame.local_translation),
            list(frame.local_orientation_rpy_deg),
        )
        for frame in frames
    ]


__all__ = ["SensorFrame", "build_sensor_frames", "sensor_frames_to_tuples"]
