"""Explicit operator velocity commands, held until the next operator command."""
import select
import os
import sys
import termios
import tty

import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node
from std_msgs.msg import String


HELP = """
Ingenuity commands. Start the simulator and flight launch first.
T: take off    L: land    X: force disarm    Z: disarm/reset operator command
W/S: +X/-X    A/D: +Y/-Y    R/F: up/down    Q/E: +yaw/-yaw
Space: stop translation and yaw. Ctrl-C: request velocity zero and exit.
Motion keys set their axis; commands persist until changed or Space is pressed.
Axes combine, for example W then A then R then Q.
X/Y/Z use the world ENU axes. A is +Y (left at zero yaw).
Space also cancels automatic climb/descent and requests velocity zero.
"""


class Keyboard(Node):
    def __init__(self):
        super().__init__('ingenuity_keyboard')
        self.declare_parameter('use_sim_time', True) if not self.has_parameter('use_sim_time') else None
        self.declare_parameter('linear_speed_mps', 0.5)
        self.declare_parameter('vertical_speed_mps', 0.3)
        self.declare_parameter('yaw_speed_radps', 0.5)
        self.publisher = self.create_publisher(TwistStamped, '/ingenuity/cmd_vel', 10)
        self.commands = self.create_publisher(String, '/ingenuity/flight_command', 10)
        self.velocity = [0.0, 0.0, 0.0, 0.0]

    def handle_key(self, key):
        linear = float(self.get_parameter('linear_speed_mps').value)
        vertical = float(self.get_parameter('vertical_speed_mps').value)
        yaw = float(self.get_parameter('yaw_speed_radps').value)
        motions = {'w': (0, linear), 's': (0, -linear),
                   'a': (1, linear), 'd': (1, -linear),
                   'r': (2, vertical), 'f': (2, -vertical),
                   'q': (3, yaw), 'e': (3, -yaw)}
        if key in motions:
            axis, value = motions[key]
            self.velocity[axis] = value
            self.publish_velocity()
        elif key in (' ', 't', 'l', 'x', 'z'):
            self.velocity = [0.0] * 4
            command = {'t': 'takeoff', 'l': 'land', 'x': 'emergency', 'z': 'reset'}.get(key)
            if command:
                self.commands.publish(String(data=command))
                print(f'\rCommand: {command}            ', end='', flush=True)
            else:
                self.publish_velocity()

    def publish_velocity(self, force_stop=False):
        if force_stop:
            self.velocity = [0.0] * 4
        message = TwistStamped()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = 'world'
        message.twist.linear.x, message.twist.linear.y, message.twist.linear.z = map(float, self.velocity[:3])
        message.twist.angular.z = float(self.velocity[3])
        self.publisher.publish(message)


def main(args=None):
    if not sys.stdin.isatty():
        raise SystemExit('Run keyboard in an interactive terminal. Do not use a launch process.')
    rclpy.init(args=args)
    node = Keyboard()
    previous_settings = termios.tcgetattr(sys.stdin.fileno())
    print(HELP)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.0)
            readable, _, _ = select.select([sys.stdin], [], [], 0.05)
            if readable:
                # TextIO can buffer a second key beyond select's OS descriptor,
                # leaving combined-axis input stuck until another key arrives.
                raw = os.read(sys.stdin.fileno(), 1)
                if not raw:
                    break
                key = raw.decode(errors='ignore').lower()
                if key == '\x03':
                    break
                node.handle_key(key)
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, previous_settings)
        if rclpy.ok():
            node.publish_velocity(force_stop=True)
            rclpy.spin_once(node, timeout_sec=0.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        print('\nZero-velocity hold requested. The flight stack remains active.')


if __name__ == '__main__':
    main()
