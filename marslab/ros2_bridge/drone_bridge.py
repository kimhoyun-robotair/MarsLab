"""Isaac/ROS boundary migrated from the original Ingenuity sensor adapter."""

import math

import numpy as np

from marslab.flight.types import WrenchCommand
from marslab.sensors.drone_sensors import BODY_FRAME, IMU_FRAME, NAV_FRAME, RANGE_FRAME, RTE_FRAME


def create_drone_bridge(world, drone, sensors, config, gravity, backend, actuators):
    import carb
    import rclpy
    from builtin_interfaces.msg import Time
    from geometry_msgs.msg import TransformStamped, WrenchStamped
    from nav_msgs.msg import Odometry
    from omni.physx import get_physx_scene_query_interface
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
    from rosgraph_msgs.msg import Clock
    from sensor_msgs.msg import CameraInfo, Image, Imu, Range
    from std_msgs.msg import String
    from tf2_msgs.msg import TFMessage

    def stamp(seconds):
        value = max(0, round(float(seconds)*1_000_000_000))
        return Time(sec=value//1_000_000_000, nanosec=value % 1_000_000_000)

    def rotation(q):
        w, x, y, z = np.asarray(q, dtype=float)
        return np.array(((1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)),
                         (2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)),
                         (2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y))))

    def set_quaternion(message, q):
        message.w, message.x, message.y, message.z = map(float, q)

    class DroneBridge(Node):
        def __init__(self):
            super().__init__("marslab_ingenuity_sim")
            self.actuators = actuators
            self.clock_pub = self.create_publisher(Clock, "/clock", 10)
            self.imu_pub = self.create_publisher(Imu, "/ingenuity/imu", qos_profile_sensor_data)
            self.range_pub = self.create_publisher(Range, "/ingenuity/range", qos_profile_sensor_data)
            self.nav_pub = self.create_publisher(Image, "/ingenuity/nav/image_raw", qos_profile_sensor_data)
            self.nav_info_pub = self.create_publisher(CameraInfo, "/ingenuity/nav/camera_info", qos_profile_sensor_data)
            self.rte_pub = self.create_publisher(Image, "/ingenuity/rte/image_raw", qos_profile_sensor_data)
            self.rte_info_pub = self.create_publisher(CameraInfo, "/ingenuity/rte/camera_info", qos_profile_sensor_data)
            durable = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                                 durability=DurabilityPolicy.TRANSIENT_LOCAL)
            self.static_pub = self.create_publisher(TFMessage, "/tf_static", durable)
            self.truth_pub = (self.create_publisher(Odometry, "/ingenuity/ground_truth/odometry",
                                                    qos_profile_sensor_data)
                              if config.publish_ground_truth else None)
            if config.flight_backend == "external_wrench":
                self.create_subscription(WrenchStamped, "/ingenuity/actuator_wrench", self.receive_wrench, 1)
                self.create_subscription(String, "/ingenuity/status", self.receive_mode, durable)
            self.applied_pub = self.create_publisher(WrenchStamped, "/ingenuity/applied_wrench", 1)
            self.reset_episode()
            self.publish_static()

        def reset_episode(self):
            self.force = np.zeros(3)
            self.torque = np.zeros(3)
            self.mode = "DISARMED"
            self.last_imu_time = None
            self.last_nav_frame = self.last_rte_frame = None
            self.noise = np.random.default_rng(config.sensors.seed + 1)
            self.clock_pub.publish(Clock(clock=stamp(world.current_time)))

        def receive_mode(self, message):
            self.mode = message.data
            if backend.command is not None:
                backend.command = WrenchCommand(self.force, self.torque, self.mode not in
                    ("DISARMED", "EMERGENCY", "SPINDOWN", "TOUCHDOWN"))

        def receive_wrench(self, message):
            if message.header.frame_id != BODY_FRAME:
                return
            force = np.array([message.wrench.force.x, message.wrench.force.y, message.wrench.force.z])
            torque = np.array([message.wrench.torque.x, message.wrench.torque.y, message.wrench.torque.z])
            if not np.all(np.isfinite(np.r_[force, torque])):
                return
            self.force = np.array([0.0, 0.0, np.clip(force[2], 0.0,
                config.actuators.max_thrust_ratio*config.mass_kg*abs(gravity))])
            self.torque = np.clip(torque, -np.asarray(config.actuators.max_torque_nm),
                                  np.asarray(config.actuators.max_torque_nm))
            backend.command = WrenchCommand(self.force, self.torque, self.mode not in
                ("DISARMED", "EMERGENCY", "SPINDOWN", "TOUCHDOWN"))

        def publish_applied_wrench(self, force, torque):
            message = WrenchStamped()
            message.header.stamp = stamp(world.current_time)
            message.header.frame_id = BODY_FRAME
            (message.wrench.force.x, message.wrench.force.y, message.wrench.force.z) = map(float, force)
            (message.wrench.torque.x, message.wrench.torque.y, message.wrench.torque.z) = map(float, torque)
            self.applied_pub.publish(message)

        def publish_static(self):
            transforms = []
            cfg = config.sensors
            for child, offset, q in (
                (IMU_FRAME, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)),
                (NAV_FRAME, cfg.nav_position, (0.0, 1.0, 0.0, 0.0)),
                (RTE_FRAME, cfg.rte_position, sensors.rte_quaternion),
                (RANGE_FRAME, cfg.range_position, (math.sqrt(0.5), 0.0, math.sqrt(0.5), 0.0)),
            ):
                transform = TransformStamped()
                transform.header.frame_id = BODY_FRAME
                transform.child_frame_id = child
                (transform.transform.translation.x, transform.transform.translation.y,
                 transform.transform.translation.z) = map(float, offset)
                set_quaternion(transform.transform.rotation, q)
                transforms.append(transform)
            self.static_pub.publish(TFMessage(transforms=transforms))

        def publish_physics(self):
            now = float(world.current_time)
            self.clock_pub.publish(Clock(clock=stamp(now)))
            reading = sensors.imu_interface.get_sensor_reading(
                sensors.imu_path, use_latest_data=True, read_gravity=True,
            )
            # Physical sensor acquisition time, not the polling time or simulator orientation.
            if reading.is_valid and (self.last_imu_time is None or reading.time > self.last_imu_time):
                self.last_imu_time = float(reading.time)
                cfg = config.sensors
                message = Imu()
                message.header.stamp = stamp(reading.time)
                message.header.frame_id = IMU_FRAME
                message.orientation_covariance[0] = -1.0
                accel = (np.array([reading.lin_acc_x, reading.lin_acc_y, reading.lin_acc_z])
                         + np.asarray(cfg.imu_accel_bias) + self.noise.normal(0.0, cfg.imu_accel_sigma, 3))
                gyro = (np.array([reading.ang_vel_x, reading.ang_vel_y, reading.ang_vel_z])
                        + np.asarray(cfg.imu_gyro_bias) + self.noise.normal(0.0, cfg.imu_gyro_sigma, 3))
                (message.linear_acceleration.x, message.linear_acceleration.y,
                 message.linear_acceleration.z) = map(float, accel)
                (message.angular_velocity.x, message.angular_velocity.y,
                 message.angular_velocity.z) = map(float, gyro)
                for index in (0, 4, 8):
                    message.linear_acceleration_covariance[index] = cfg.imu_accel_sigma**2
                    message.angular_velocity_covariance[index] = cfg.imu_gyro_sigma**2
                self.imu_pub.publish(message)
            if self.truth_pub is not None and world.current_time_step_index % 10 == 0:
                position, q = drone.body.get_world_poses()
                velocity = drone.body.get_velocities()[0]
                message = Odometry()
                message.header.stamp = stamp(now)
                message.header.frame_id = "ground_truth_world"
                message.child_frame_id = "ground_truth_ingenuity/base_link"
                (message.pose.pose.position.x, message.pose.pose.position.y,
                 message.pose.pose.position.z) = map(float, position[0])
                set_quaternion(message.pose.pose.orientation, q[0])
                local = rotation(q[0]).T @ velocity[:3]
                rates = rotation(q[0]).T @ velocity[3:]
                (message.twist.twist.linear.x, message.twist.twist.linear.y,
                 message.twist.twist.linear.z) = map(float, local)
                (message.twist.twist.angular.x, message.twist.twist.angular.y,
                 message.twist.twist.angular.z) = map(float, rates)
                self.truth_pub.publish(message)

        def publish_range(self):
            cfg = config.sensors
            position, q = drone.body.get_world_poses()
            rot = rotation(q[0])
            origin = position[0] + rot @ np.asarray(cfg.range_position)
            direction = rot @ np.array([0.0, 0.0, -1.0])
            # Pose is used only to simulate the beam; it is not a navigation input.
            hit = get_physx_scene_query_interface().raycast_closest(
                carb.Float3(*map(float, origin)), carb.Float3(*map(float, direction)),
                cfg.range_max_m, True,
            )
            message = Range()
            message.header.stamp = stamp(world.current_time)
            message.header.frame_id = RANGE_FRAME
            message.radiation_type = Range.INFRARED
            message.field_of_view = cfg.range_beam_divergence_rad
            message.min_range, message.max_range = cfg.range_min_m, cfg.range_max_m
            message.range = math.inf
            if hit.get("hit", False):
                distance = float(hit["distance"]) + self.noise.normal(0.0, cfg.range_sigma_m)
                message.range = (-math.inf if distance < cfg.range_min_m
                                 else float(distance) if distance <= cfg.range_max_m else math.inf)
            self.range_pub.publish(message)
            return float(message.range) if math.isfinite(message.range) else None

        def publish_camera(self, camera, intrinsics, optical_frame, image_pub, info_pub, monochrome):
            frame = camera.get_current_frame()
            number = frame.get("rendering_frame")
            last = self.last_nav_frame if monochrome else self.last_rte_frame
            rgba = frame.get("rgb")
            if number is None or number == last or rgba is None:
                return
            rgba = np.asarray(rgba)
            if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.size == 0:
                return
            if monochrome:
                self.last_nav_frame = number
                pixels = np.clip(0.2126*rgba[..., 0] + 0.7152*rgba[..., 1]
                                 + 0.0722*rgba[..., 2], 0.0, 255.0).astype(np.uint8)
            else:
                self.last_rte_frame = number
                pixels = np.ascontiguousarray(rgba[..., :3], dtype=np.uint8)
            image = Image()
            image.header.stamp = stamp(frame.get("rendering_time", world.current_time))
            image.header.frame_id = optical_frame
            image.height, image.width = pixels.shape[:2]
            image.encoding = "mono8" if monochrome else "rgb8"
            image.step = image.width*(1 if monochrome else 3)
            image.data = pixels.tobytes()
            fx, fy, cx, cy = intrinsics
            info = CameraInfo()
            info.header = image.header
            info.height, info.width = image.height, image.width
            info.distortion_model, info.d = "plumb_bob", [0.0]*5
            info.k = [fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0]
            info.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
            info.p = [fx, 0.0, cx, 0.0, 0.0, fy, cy, 0.0, 0.0, 0.0, 1.0, 0.0]
            info_pub.publish(info)
            image_pub.publish(image)

        def publish_images(self):
            self.publish_camera(sensors.nav, sensors.nav_intrinsics, NAV_FRAME,
                                self.nav_pub, self.nav_info_pub, True)
            self.publish_camera(sensors.rte, sensors.rte_intrinsics, RTE_FRAME,
                                self.rte_pub, self.rte_info_pub, False)

    rclpy.init(args=[])
    try:
        return DroneBridge()
    except BaseException:
        rclpy.shutdown()
        raise
