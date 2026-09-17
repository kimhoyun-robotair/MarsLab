"""Publish completed native RTX flat scans through the owned rover ROS node."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from marslab.config.schema.rover_ros2 import Ros2BridgeConfig, resolve_ros_topic
from marslab.ros2_bridge.qos import to_rclpy_qos
from marslab.ros2_bridge.timestamp import ros_stamp_from_ns
from marslab.sensors.lidar_2d_spawner import Lidar2DSpawnHandles


@dataclass
class LidarScanPublisher:
    acquisition: Lidar2DSpawnHandles
    publisher: Any
    last_completion_stamp_ns: int | None = None

    def reset(self) -> None:
        self.last_completion_stamp_ns = self.acquisition.read_scan_timestamp_ns()

    def publish_latest(self) -> None:
        from sensor_msgs.msg import LaserScan
        from std_msgs.msg import Header

        completed_ns = self.acquisition.read_scan_timestamp_ns()
        if completed_ns is None or completed_ns == self.last_completion_stamp_ns:
            return
        scan = self.acquisition.read_scan()
        ranges = np.asarray(scan.get("linearDepthData", []), dtype=np.float32)
        columns = int(scan.get("numCols", 0))
        rotation_rate = float(scan.get("rotationRate", 0.0))
        resolution = float(scan.get("horizontalResolution", 0.0))
        time_increment = float(scan.get("timeIncrementSeconds", 0.0))
        first_ray_offset = float(scan.get("firstRayOffsetSeconds", -1.0))
        azimuth = np.asarray(scan.get("azimuthRange", []), dtype=np.float64)
        depth_range = np.asarray(scan.get("depthRange", []), dtype=np.float64)
        if (
            ranges.ndim != 1
            or columns <= 0
            or columns != ranges.size
            or azimuth.shape != (2,)
            or depth_range.shape != (2,)
            or not math.isfinite(rotation_rate)
            or rotation_rate <= 0.0
            or not math.isfinite(resolution)
            or resolution <= 0.0
            or not math.isfinite(time_increment)
            or time_increment <= 0.0
            or not math.isfinite(first_ray_offset)
            or first_ray_offset < 0.0
            or not np.isfinite(azimuth).all()
            or azimuth[1] < azimuth[0]
            or not np.isfinite(depth_range).all()
            or depth_range[1] <= depth_range[0]
        ):
            return
        scan_time = 1.0 / rotation_rate
        # Retain full-turn timing, then advance to the first beam in the cropped sector.
        stamp_ns = completed_ns - int(round((scan_time - first_ray_offset) * 1_000_000_000))
        if stamp_ns < 0:
            return
        intensities = np.asarray(scan.get("intensitiesData", []), dtype=np.float32)
        if intensities.size not in (0, columns):
            return
        message = LaserScan(
            header=Header(stamp=ros_stamp_from_ns(stamp_ns), frame_id="lidar_2d_link"),
            angle_min=math.radians(float(azimuth[0])),
            angle_max=math.radians(float(azimuth[1])),
            angle_increment=math.radians(resolution),
            time_increment=time_increment,
            scan_time=scan_time,
            range_min=float(depth_range[0]),
            range_max=float(depth_range[1]),
            ranges=ranges.tolist(),
            intensities=intensities.tolist(),
        )
        self.publisher.publish(message)
        self.last_completion_stamp_ns = completed_ns


def create_lidar_scan_publisher(
    node: Any, acquisition: Lidar2DSpawnHandles, config: Ros2BridgeConfig
) -> LidarScanPublisher:
    from sensor_msgs.msg import LaserScan

    return LidarScanPublisher(
        acquisition=acquisition,
        publisher=node.create_publisher(
            LaserScan,
            resolve_ros_topic(config.namespace, config.topics.scan),
            to_rclpy_qos(config.sensor_qos),
        ),
    )
