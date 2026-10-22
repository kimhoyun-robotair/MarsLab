"""Processed IMU, downward Navcam, oblique RTE camera and a single laser beam."""

from dataclasses import dataclass
import math

import numpy as np

from marslab.config.schema.drone import DroneConfig

BODY_FRAME = "ingenuity/base_link"
IMU_FRAME = "ingenuity/imu_link"
NAV_FRAME = "ingenuity/nav_optical"
RTE_FRAME = "ingenuity/rte_optical"
RANGE_FRAME = "ingenuity/range_link"


@dataclass
class DroneSensors:
    imu: object
    imu_interface: object
    imu_path: str
    nav: object
    rte: object
    nav_intrinsics: tuple[float, float, float, float]
    rte_intrinsics: tuple[float, float, float, float]
    rte_quaternion: tuple[float, float, float, float]

    def initialize_cameras(self):
        self.nav.initialize()
        self.rte.initialize()


def spawn_drone_sensors(world, config: DroneConfig) -> DroneSensors:
    from isaacsim.core.utils.extensions import enable_extension

    enable_extension("isaacsim.sensors.physics")
    enable_extension("isaacsim.sensors.camera")
    from isaacsim.sensors.camera import Camera
    from isaacsim.sensors.physics import IMUSensor, _sensor

    class DroneCamera(Camera):
        def _data_acquisition_callback(self, event):
            # Isaac 5.1 resets the acquisition accumulator to zero. With a
            # 500 Hz physics clock and 60 Hz renders, the rounded render times
            # then turn the requested 30 Hz Navcam into ~20 Hz. Carry the
            # fractional period after acquisition instead of losing it.
            previous_time = self._previous_time
            elapsed = self._elapsed_time
            captured_time = self._current_frame.get("rendering_time")
            super()._data_acquisition_callback(event)
            if (self._frequency > 0 and previous_time is not None
                    and self._current_frame.get("rendering_time") != captured_time):
                interval = self._previous_time - previous_time
                self._elapsed_time = max(0.0, elapsed+interval-self.get_dt())

    sensors = config.sensors
    imu_path = config.prim_path + "/Imu"
    imu = world.scene.add(IMUSensor(
        prim_path=imu_path, name="ingenuity_imu", frequency=sensors.imu_hz,
        translation=np.zeros(3), orientation=np.array([1.0, 0.0, 0.0, 0.0]),
        linear_acceleration_filter_size=sensors.imu_acceleration_filter_size,
        angular_velocity_filter_size=sensors.imu_angular_velocity_filter_size,
        orientation_filter_size=1,
    ))

    def camera(path, name, resolution, frequency, position, quaternion, fx, fy):
        cam = DroneCamera(prim_path=path, name=name, resolution=resolution, frequency=frequency,
                     translation=np.asarray(position))
        cam.set_local_pose(translation=np.asarray(position), orientation=np.asarray(quaternion),
                           camera_axes="ros")
        cam.set_focal_length(0.0028)
        cam.set_horizontal_aperture(0.0028 * resolution[0] / fx)
        cam.set_vertical_aperture(0.0028 * resolution[1] / fy)
        cam.set_lens_aperture(0.0)
        cam.set_clipping_range(0.01, 100.0)
        cx, cy = resolution[0]/2.0, resolution[1]/2.0
        cam.set_opencv_pinhole_properties(cx=cx, cy=cy, fx=fx, fy=fy, pinhole=[0.0]*5)
        return cam, (fx, fy, cx, cy)

    # Preserve published central angular scale; this is rectified pinhole optics.
    nav_fx = 1.0 / sensors.nav_central_pixel_scale_rad
    nav, nav_k = camera(config.prim_path + "/NavCamera", "ingenuity_nav_camera",
                         sensors.nav_resolution, sensors.nav_hz, sensors.nav_position,
                         (0.0, 1.0, 0.0, 0.0), nav_fx, nav_fx)
    alpha = math.radians(90.0 - sensors.rte_angle_below_horizon_deg)
    rte_q = (0.0, math.cos(alpha/2.0), 0.0, math.sin(alpha/2.0))
    rte_fx = sensors.rte_resolution[0] / (2.0*math.tan(math.radians(sensors.rte_horizontal_fov_deg)/2.0))
    rte_fy = sensors.rte_resolution[1] / (2.0*math.tan(math.radians(sensors.rte_vertical_fov_deg)/2.0))
    rte, rte_k = camera(config.prim_path + "/RteCamera", "ingenuity_rte_camera",
                         sensors.rte_resolution, sensors.rte_hz, sensors.rte_position,
                         rte_q, rte_fx, rte_fy)
    return DroneSensors(imu, _sensor.acquire_imu_sensor_interface(), imu_path,
                         nav, rte, nav_k, rte_k, rte_q)
