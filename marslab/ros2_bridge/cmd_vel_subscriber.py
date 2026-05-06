"""rclpy subscriber for ``geometry_msgs/Twist`` command input.

The runtime consumes ``/<ns>/cmd_vel`` each physics step to drive
the Ackermann controller.  Keeping the subscriber in its own module
lets the state container be unit-tested without importing ``rclpy``.

``queue_size`` is keyword-only with no default.  The canonical value
(``10``) lives in
:class:`marslab.config.schema.ros2_bridge.Ros2BridgeConfig` under
``cmd_vel_queue_size`` and is threaded through ``init_rclpy_side``.
Every call site must pass it explicitly so a missing YAML key cannot
hide behind a Python fallback.

The optional ``qos`` parameter pins reliability / durability / history
depth through YAML via
:class:`marslab.config.schema.ros2_bridge.QoSProfileConfig`.  When
omitted the integer-``queue_size`` overload is used, matching the
rclpy default profile.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def create_cmd_vel_subscriber(
    node: Any,
    topic: str,
    twist_state: Dict[str, float],
    *,
    queue_size: int,
    qos: Optional[Any] = None,
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
            (``ge=1``, ``le=1000``).  Ignored when ``qos`` is provided
            because a full QoSProfile already carries a ``depth`` field.
        qos: Optional ``rclpy.qos.QoSProfile`` instance.  When
            provided, ``create_subscription`` is called with the full
            profile (enabling custom reliability / durability).  When
            ``None`` the legacy integer queue-size overload is used.
            Callers that need YAML-driven QoS should build the
            profile via :func:`marslab.ros2_bridge.qos.to_rclpy_qos`.

    Returns:
        The created ``rclpy`` subscription handle.

    Raises:
        ValueError: When ``qos is None`` and ``queue_size < 1``.  The
            integer overload requires a positive depth -- a zero or
            negative depth would be silently rejected by rclpy at
            runtime, so this guard fails fast at the call site.
    """
    from geometry_msgs.msg import Twist

    if not {"v", "w"} <= set(twist_state.keys()):
        raise KeyError("twist_state must contain keys 'v' and 'w'")

    if qos is None and queue_size < 1:
        raise ValueError("queue_size must be >= 1 when qos is None")

    def _cb(msg: Twist) -> None:
        twist_state["v"] = float(msg.linear.x)
        twist_state["w"] = float(msg.angular.z)

    if qos is not None:
        # rclpy accepts QoSProfile as a positional arg identical in
        # slot to integer queue_size (overloaded at the rclpy layer).
        return node.create_subscription(Twist, topic, _cb, qos)
    return node.create_subscription(Twist, topic, _cb, queue_size)
