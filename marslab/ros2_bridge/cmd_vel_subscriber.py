"""rclpy subscriber for ``geometry_msgs/Twist`` command input.

The Stage-3 runtime consumes ``/<ns>/cmd_vel`` each physics step to
drive the Ackermann controller.  Keeping the subscriber in its own
module lets us unit-test the state container without importing
``rclpy``.

R4-5 extension (2026-04-23): ``queue_size`` is no longer a Python
default.  The historical value (``10``) now lives in
:class:`marslab.config.schema.ros2_bridge.Ros2BridgeConfig` under
``cmd_vel_queue_size`` and is threaded through ``init_rclpy_side``.
The ``queue_size`` parameter here remains keyword-only with no default
so every call site must pass it explicitly -- there is no longer a
silent fallback that would hide a missing YAML key.
"""

from __future__ import annotations

from typing import Any, Dict


def create_cmd_vel_subscriber(
    node: Any,
    topic: str,
    twist_state: Dict[str, float],
    *,
    queue_size: int,
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
        queue_size: rclpy subscription queue depth.  Keyword-only --
            callers must source this from
            :class:`marslab.config.schema.ros2_bridge.Ros2BridgeConfig`
            (``cmd_vel_queue_size``) so the value is validated upstream
            (``ge=1``, ``le=1000``).

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
