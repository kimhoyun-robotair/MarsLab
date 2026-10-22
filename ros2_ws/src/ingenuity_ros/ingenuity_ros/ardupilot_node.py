"""ROS operator/telemetry adapter for the Mars-gravity ArduPilot SITL.

ArduPilot owns flight modes, trajectory generation, control and estimation.
This node owns its SITL process, transports explicit operator commands, and
publishes autopilot state. It implements no position or attitude controller.
"""

import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

import numpy as np
import rclpy
from builtin_interfaces.msg import Time
from geometry_msgs.msg import TransformStamped, TwistStamped
from nav_msgs.msg import Odometry
from pymavlink import mavutil
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String
from tf2_ros import Buffer, TransformBroadcaster, TransformException, TransformListener
from rclpy.time import Time as RosTime

from marslab.flight.ardupilot_setup import DEFAULT_SOURCE, read_settings, require_mars_build, write_parameters
from marslab.flight.frames import ENU_TO_NED, FLU_TO_FRD, convert_quaternion, rotation


def stamp(seconds):
    nanoseconds = max(0, round(seconds*1e9))
    return Time(sec=nanoseconds//1_000_000_000, nanosec=nanoseconds % 1_000_000_000)


class ArduPilotNode(Node):
    def __init__(self):
        super().__init__("ingenuity_ardupilot")
        self.declare_parameter("marslab_config", "")
        self.declare_parameter("ardupilot_source", str(DEFAULT_SOURCE))
        self.settings = read_settings(self.get_parameter("marslab_config").value)
        self.drone = self.settings["drone"]
        self.ap = self.drone.get("ardupilot", {})
        self.source = Path(self.get_parameter("ardupilot_source").value).expanduser().resolve()
        self.binary = require_mars_build(self.settings, self.source)
        self.process = self.link = None
        self.sim_time = self.last_clock = None
        self.position = self.velocity_world = self.quaternion = self.rates = None
        self.connected = self.armed = self.interlock = False
        self.rsc_pwm = 1000
        self.mode = None
        self.mode_request = None
        self.intent = self.pending_command = None
        self.explicit_arm_request = False
        self.command_velocity = np.zeros(3)
        self.command_yaw_rate = 0.0
        self.command_frame = "world"
        self.last_heartbeat_sent = -math.inf
        self.last_status = None
        durable = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.odom_pub = self.create_publisher(Odometry, "/ingenuity/odometry", qos_profile_sensor_data)
        self.status_pub = self.create_publisher(String, "/ingenuity/status", durable)
        self.details_pub = self.create_publisher(String, "/ingenuity/autopilot_status", durable)
        self.tf_pub = TransformBroadcaster(self)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.create_subscription(Clock, "/clock", self.on_clock, 10)
        self.create_subscription(TwistStamped, "/ingenuity/cmd_vel", self.on_velocity, 10)
        self.create_subscription(String, "/ingenuity/flight_command", self.on_command, 10)
        try:
            self.start_sitl()
            # Wall-clock polling also handles commands when simulation is paused.
            self.create_timer(0.05, self.tick)
        except BaseException:
            self.stop_sitl()
            raise

    def start_sitl(self):
        directory = self.source.parent / "runtime" / f"instance-{int(self.ap.get('instance', 0))}"
        directory.mkdir(parents=True, exist_ok=True)
        parameters = write_parameters(self.settings, self.source, directory / "marslab.parm")
        port = int(self.ap.get("mavlink_port", 14560))
        self.link = mavutil.mavlink_connection(f"udpin:127.0.0.1:{port}", source_system=255,
                                              source_component=191, dialect="ardupilotmega")
        home = ",".join(str(value) for value in (
            self.ap.get("home_latitude_deg", -35.363261), self.ap.get("home_longitude_deg", 149.165230),
            self.ap.get("home_altitude_m", 584.0), 90.0))
        self.process = subprocess.Popen([
            str(self.binary), "--instance", str(self.ap.get("instance", 0)),
            "--model", f"JSON:{self.ap.get('json_bind', '127.0.0.1')}",
            "--sim-port-out", str(self.ap.get("json_port", 9002)),
            "--rate", str(self.drone.get("simulation", {}).get("physics_hz", 500)),
            "--serial0", f"udpclient:127.0.0.1:{port}", "--defaults", str(parameters),
            "--home", home, "--wipe",
        ], cwd=directory, start_new_session=True)
        self.get_logger().info(
            f"ArduPilot Copter-4.6.3 heli SITL; gravity={self.settings['mars_env']['gravity']} m/s^2; "
            f"navigation={self.ap.get('navigation', 'sim_truth')}; JSON PWM={self.ap.get('json_port', 9002)}.")
        self.get_logger().info(f"Active ArduPilot parameters: {parameters}")

    def stop_sitl(self):
        if self.process is not None:
            process, self.process = self.process, None
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                except ProcessLookupError:
                    pass
        if self.link is not None:
            self.link.close()
            self.link = None

    def destroy_node(self):
        self.stop_sitl()
        return super().destroy_node()

    def on_clock(self, message):
        now = message.clock.sec+message.clock.nanosec*1e-9
        if self.last_clock is not None and now < self.last_clock:
            # Operator Stop/Play starts a fresh, disarmed flight episode.
            self.stop_sitl()
            self.connected = self.armed = self.interlock = False
            self.rsc_pwm = 1000
            self.mode = self.intent = self.pending_command = None
            self.mode_request = None
            self.explicit_arm_request = False
            self.position = self.velocity_world = self.quaternion = self.rates = None
            self.last_status = None
            self.start_sitl()
        self.sim_time = self.last_clock = now

    def on_velocity(self, message):
        values = np.array([message.twist.linear.x, message.twist.linear.y, message.twist.linear.z,
                           message.twist.angular.z])
        if not np.all(np.isfinite(values)):
            self.get_logger().warning("Undefined operator velocity; retaining the previous command.")
            return
        self.command_velocity, self.command_yaw_rate = values[:3].copy(), float(values[3])
        self.command_frame = message.header.frame_id or "world"
        self.intent = "velocity"
        self.mode_request = 4
        # A new operator command cancels a pending automatic takeoff/landing.
        if (self.pending_command is not None
                and self.pending_command["command"] == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF):
            self.pending_command = None

    def on_command(self, message):
        command = message.data.strip().lower()
        if command not in ("takeoff", "land", "emergency", "reset"):
            self.get_logger().warning(f"Unknown operator command: {command}")
            return
        # Serialize mode/arming ACKs so a canceled mode's ACK cannot be
        # mistaken for the next mode's ACK. The latest operator intent wins.
        if (self.pending_command is not None
                and self.pending_command["command"] == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF):
            self.pending_command = None
        self.command_velocity[:] = 0.0
        self.command_yaw_rate = 0.0
        if command == "takeoff":
            self.explicit_arm_request = not self.armed
            self.intent = "takeoff"
            self.mode_request = 4
        elif command == "land":
            self.explicit_arm_request = False
            self.intent = "land"
            self.mode_request = 9
        else:
            self.explicit_arm_request = False
            self.pending_command = self.mode_request = None
            self.interlock = False
            self.intent = "disarm"
        self.get_logger().info(f"Operator requested {command}.")

    def send_command(self, command, parameters):
        parameters = list(parameters)+[0.0]*(7-len(parameters))
        self.link.mav.command_long_send(self.link.target_system, self.link.target_component,
                                       command, 0, *parameters)
        self.pending_command = {"command": command, "parameters": parameters,
                                "sent": time.monotonic(), "attempts": 1, "accepted": False}

    def send_mode(self, mode):
        self.send_command(mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                          [mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode])

    def request_telemetry(self):
        for identifier, interval in ((31, 20000), (32, 20000), (36, 20000)):
            self.link.mav.command_long_send(self.link.target_system, self.link.target_component,
                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, identifier, interval, 0, 0, 0, 0, 0)

    def pending_observed(self):
        pending = self.pending_command
        if pending["command"] == mavutil.mavlink.MAV_CMD_DO_SET_MODE:
            return pending["accepted"]
        if pending["command"] == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
            return pending["accepted"] and self.armed == bool(pending["parameters"][0])
        return pending["accepted"]

    def receive(self, message):
        kind = message.get_type()
        if kind == "HEARTBEAT":
            if message.type == mavutil.mavlink.MAV_TYPE_GCS:
                return
            first = not self.connected
            self.connected = True
            self.link.target_system, self.link.target_component = message.get_srcSystem(), message.get_srcComponent()
            self.mode = int(message.custom_mode)
            self.armed = bool(message.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            if not self.armed:
                self.interlock = False
            else:
                # Consume this T's arming request once. A later native disarm
                # must never cause the adapter to rearm on a latched velocity.
                self.explicit_arm_request = False
            if first:
                self.get_logger().info("ArduPilot connected; T explicitly requests arming and takeoff.")
                self.request_telemetry()
        elif kind == "ATTITUDE_QUATERNION":
            self.quaternion = convert_quaternion(np.array([message.q1, message.q2, message.q3, message.q4]))
            self.rates = FLU_TO_FRD@np.array([message.rollspeed, message.pitchspeed, message.yawspeed])
        elif kind == "LOCAL_POSITION_NED":
            self.position = ENU_TO_NED@np.array([message.x, message.y, message.z])
            self.velocity_world = ENU_TO_NED@np.array([message.vx, message.vy, message.vz])
        elif kind == "SERVO_OUTPUT_RAW" and message.port == 0:
            self.rsc_pwm = int(message.servo8_raw)
        elif kind == "STATUSTEXT":
            text = message.text.decode(errors="replace") if isinstance(message.text, bytes) else message.text
            self.get_logger().info(f"ArduPilot: {text}")
        elif kind == "COMMAND_ACK" and self.pending_command is not None:
            pending = self.pending_command
            if message.command != pending["command"]:
                return
            if message.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                pending["accepted"] = True
                if message.command == mavutil.mavlink.MAV_CMD_DO_SET_MODE:
                    # ArduPilot ACKs after set_mode succeeds. Send the next
                    # operator setpoint now, without a one-second heartbeat delay.
                    self.mode = int(pending["parameters"][1])
                    if self.mode_request == self.mode:
                        self.mode_request = None
                elif message.command == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF and self.intent == "takeoff":
                    self.intent = None
                    self.explicit_arm_request = False
                elif (message.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM
                      and not pending["parameters"][0] and self.intent == "disarm"):
                    self.intent = None
            elif message.result != mavutil.mavlink.MAV_RESULT_IN_PROGRESS:
                self.get_logger().warning(f"ArduPilot rejected command {message.command}: MAV_RESULT={message.result}.")
                self.pending_command = self.intent = None
                self.mode_request = None
                self.explicit_arm_request = False

    def send_rc(self):
        # Channels 1..4 centered/low throttle; channel 8 is the documented motor interlock.
        self.link.mav.rc_channels_override_send(self.link.target_system, self.link.target_component,
            1500, 1500, 1000, 1500, 65535, 65535, 65535, 2000 if self.interlock else 1000)

    def send_velocity(self):
        velocity = self.command_velocity.copy()
        if np.any(velocity):
            if self.command_frame == "ingenuity/base_link":
                if self.quaternion is None:
                    return
                velocity = rotation(self.quaternion)@velocity
            elif self.command_frame != "world":
                try:
                    transform = self.tf_buffer.lookup_transform("world", self.command_frame, RosTime())
                except TransformException:
                    self.get_logger().warning(f"Waiting for {self.command_frame} -> world TF.", throttle_duration_sec=1.)
                    return
                q = transform.transform.rotation
                velocity = rotation([q.w, q.x, q.y, q.z])@velocity
        north, east, down = ENU_TO_NED@velocity
        # Ignore position, acceleration and yaw; retain velocity XYZ and yaw rate.
        self.link.mav.set_position_target_local_ned_send(int((self.sim_time or 0.)*1000) & 0xffffffff,
            self.link.target_system, self.link.target_component, mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            1479, 0, 0, 0, north, east, down, 0, 0, 0, 0, -self.command_yaw_rate)

    def tick(self):
        if self.process.poll() is not None:
            raise RuntimeError(f"ArduPilot SITL exited with code {self.process.returncode}; inspect its console output")
        for _ in range(100):
            message = self.link.recv_match(blocking=False)
            if message is None:
                break
            self.receive(message)
        if not self.connected:
            return
        now = time.monotonic()
        if now-self.last_heartbeat_sent >= 1.0:
            self.link.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, mavutil.mavlink.MAV_STATE_ACTIVE)
            self.last_heartbeat_sent = now
        self.send_rc()
        if self.pending_command is not None:
            pending = self.pending_command
            if self.pending_observed():
                self.pending_command = None
            elif not pending["accepted"] and now-pending["sent"] >= 2.0:
                if pending["attempts"] >= 3:
                    self.get_logger().warning(f"No acknowledgment for command {pending['command']}; request it again.")
                    self.pending_command = self.intent = None
                    self.mode_request = None
                    self.explicit_arm_request = False
                else:
                    self.link.mav.command_long_send(self.link.target_system, self.link.target_component,
                        pending["command"], pending["attempts"], *pending["parameters"])
                    pending["attempts"] += 1
                    pending["sent"] = now
        if self.pending_command is None:
            if self.intent in ("takeoff", "velocity"):
                if self.armed or self.explicit_arm_request:
                    if self.mode_request is not None or self.mode != 4:  # GUIDED
                        self.send_mode(4)
                    elif not self.armed:
                        self.send_command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, [1, 0])
                    else:
                        self.interlock = True
                        if self.intent == "takeoff":
                            # Native takeoff rejects an interlock that has not
                            # yet been processed. Observe native RSC output,
                            # rather than assuming the RC override is immediate.
                            if self.rsc_pwm > 1000:
                                height = float(self.drone.get("flight", {}).get("takeoff_height_m", 3.0))
                                self.send_command(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                                                  [0, 0, 0, float("nan"), 0, 0, height])
                        else:
                            self.send_velocity()
            elif self.intent == "land":
                if self.armed and (self.mode_request is not None or self.mode != 9):  # LAND
                    self.send_mode(9)
                else:
                    self.intent = None
                    self.mode_request = None
            elif self.intent == "disarm":
                # Send even if the last heartbeat was disarmed: an earlier arm
                # request may already be in transit. Only explicit X/Z use force.
                self.send_command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, [0, 21196])
        self.publish_state()

    def publish_state(self):
        mode_name = self.link.flightmode or f"MODE_{self.mode}"
        status = mode_name if self.armed else "DISARMED"
        if status != self.last_status:
            self.get_logger().info(f"Autopilot mode={mode_name}, armed={self.armed}, interlock={self.interlock}.")
            self.last_status = status
        self.status_pub.publish(String(data=status))
        self.details_pub.publish(String(data=json.dumps({"backend": "ardupilot", "mode": mode_name,
            "armed": self.armed, "motor_interlock": self.interlock,
            "navigation": self.ap.get("navigation", "sim_truth"),
            "gravity_mps2": self.settings["mars_env"]["gravity"], "operator_intent": self.intent})))
        if self.sim_time is None or self.position is None or self.quaternion is None or self.velocity_world is None:
            return
        message = Odometry()
        message.header.stamp, message.header.frame_id, message.child_frame_id = stamp(self.sim_time), "world", "ingenuity/base_link"
        (message.pose.pose.position.x, message.pose.pose.position.y, message.pose.pose.position.z) = map(float, self.position)
        q = self.quaternion
        message.pose.pose.orientation.w, message.pose.pose.orientation.x = float(q[0]), float(q[1])
        message.pose.pose.orientation.y, message.pose.pose.orientation.z = float(q[2]), float(q[3])
        body_velocity = rotation(q).T@self.velocity_world
        (message.twist.twist.linear.x, message.twist.twist.linear.y, message.twist.twist.linear.z) = map(float, body_velocity)
        if self.rates is not None:
            (message.twist.twist.angular.x, message.twist.twist.angular.y, message.twist.twist.angular.z) = map(float, self.rates)
        self.odom_pub.publish(message)
        transform = TransformStamped()
        transform.header, transform.child_frame_id = message.header, message.child_frame_id
        (transform.transform.translation.x, transform.transform.translation.y, transform.transform.translation.z) = map(float, self.position)
        transform.transform.rotation = message.pose.pose.orientation
        self.tf_pub.sendTransform(transform)


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ArduPilotNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
