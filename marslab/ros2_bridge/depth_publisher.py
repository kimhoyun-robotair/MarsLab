"""Publish optional noisy depth and its matching organized XYZ point cloud."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from marslab.config.schema.rover_ros2 import Ros2BridgeConfig, resolve_ros_topic
from marslab.ros2_bridge.qos import to_rclpy_qos
from marslab.ros2_bridge.timestamp import ros_stamp_from_ns
from marslab.sensors.camera_spawner import CameraSpawnHandles


@dataclass
class DepthPublisher:
    acquisition: CameraSpawnHandles
    image_publisher: Any
    points_publisher: Any
    last_stamp_ns: int | None = None

    def reset(self) -> None:
        self.last_stamp_ns = None

    def publish_latest(self) -> None:
        from sensor_msgs.msg import Image, PointCloud2, PointField
        from std_msgs.msg import Header

        sample = self.acquisition.read_depth_sample()
        if sample is None or sample.stamp_ns == self.last_stamp_ns:
            return
        depth = np.asarray(sample.depth_m, dtype="<f4")
        height, width = depth.shape
        header = Header(stamp=ros_stamp_from_ns(sample.stamp_ns), frame_id="camera_optical_frame")
        image = Image(
            header=header,
            height=height,
            width=width,
            encoding="32FC1",
            is_bigendian=False,
            step=width * 4,
            data=depth.tobytes(),
        )
        intrinsics = np.asarray(self.acquisition.camera.get_intrinsics_matrix())
        fx, fy = float(intrinsics[0, 0]), float(intrinsics[1, 1])
        cx, cy = float(intrinsics[0, 2]), float(intrinsics[1, 2])
        xyz = np.empty((height, width, 3), dtype="<f4")
        xyz[..., 0] = depth * ((np.arange(width, dtype=np.float32) - cx) / fx)
        xyz[..., 1] = depth * ((np.arange(height, dtype=np.float32)[:, None] - cy) / fy)
        xyz[..., 2] = depth
        points = PointCloud2(
            header=header,
            height=height,
            width=width,
            fields=[
                PointField(name=name, offset=index * 4, datatype=PointField.FLOAT32, count=1)
                for index, name in enumerate(("x", "y", "z"))
            ],
            is_bigendian=False,
            point_step=12,
            row_step=width * 12,
            data=xyz.tobytes(),
            is_dense=bool(np.isfinite(depth).all()),
        )
        self.image_publisher.publish(image)
        self.points_publisher.publish(points)
        self.last_stamp_ns = sample.stamp_ns


def create_depth_publisher(
    node: Any, camera_acquisition: CameraSpawnHandles, config: Ros2BridgeConfig
) -> DepthPublisher | None:
    """Reuse the bridge node and configured sensor QoS when noise is enabled."""
    if not camera_acquisition.depth_noise_enabled:
        return None
    from sensor_msgs.msg import Image, PointCloud2

    qos = to_rclpy_qos(config.sensor_qos)
    return DepthPublisher(
        acquisition=camera_acquisition,
        image_publisher=node.create_publisher(
            Image, resolve_ros_topic(config.namespace, config.topics.depth), qos
        ),
        points_publisher=node.create_publisher(
            PointCloud2, resolve_ros_topic(config.namespace, config.topics.points), qos
        ),
    )
