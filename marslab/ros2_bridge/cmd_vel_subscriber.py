"""rclpy subscriber for ``geometry_msgs/Twist`` command input.

The Stage-3 runtime consumes ``/<ns>/cmd_vel`` each physics step to
drive the Ackermann controller.  Keeping the subscriber in its own
module lets us unit-test the state container without importing
``rclpy``.
"""

from __future__ import annotations

from typing import Any, Dict


def create_cmd_vel_subscriber(
    node: Any,
    topic: str,
    twist_state: Dict[str, float],
    queue_size: int = 10,
) -> Any:
    """Subscribe ``twist_state`` to a ``geometry_msgs/Twist`` topic.

    Args:
        node: ``rclpy.node.Node`` instance.
        topic: Fully-qualified topic name (e.g. ``/rover/cmd_vel``).
        twist_state: Mutable dict with keys ``"v"`` and ``"w"``.  The
            subscriber writes the latest ``linear.x`` into ``v`` and
            ``angular.z`` into ``w`` on every message.  Passing a
            shared dict keeps the subscriber side-effect-visible to
            the main simulation loop without a class.
        queue_size: rclpy subscription queue depth.

    Returns:
        The created ``rclpy`` subscription handle.
    """
    from geometry_msgs.msg import Twist

    if not {"v", "w"} <= set(twist_state.keys()):
        raise KeyError("twist_state must contain keys 'v' and 'w'")

    def _cb(msg: Twist) -> None:
        twist_state["v"] = float(msg.linear.x)
        twist_state["w"] = float(msg.angular.z)

    return node.create_subscription(Twist, topic, _cb, queue_size)
