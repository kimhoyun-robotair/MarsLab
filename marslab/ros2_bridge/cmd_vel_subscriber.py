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

Reviewer 2 #04 (2026-04-24) added an optional ``qos`` parameter.
When supplied it is passed directly to ``create_subscription`` so the
caller can pin reliability / durability / history depth through YAML
via :class:`marslab.config.schema.ros2_bridge.QoSProfileConfig`.
When omitted the legacy integer-``queue_size`` call is preserved so
existing tests and older call sites keep working.
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
    """
    from geometry_msgs.msg import Twist

    if not {"v", "w"} <= set(twist_state.keys()):
        raise KeyError("twist_state must contain keys 'v' and 'w'")

    def _cb(msg: Twist) -> None:
        twist_state["v"] = float(msg.linear.x)
        twist_state["w"] = float(msg.angular.z)

    if qos is not None:
        # rclpy accepts QoSProfile as a positional arg identical in
        # slot to integer queue_size (overloaded at the rclpy layer).
        return node.create_subscription(Twist, topic, _cb, qos)
    return node.create_subscription(Twist, topic, _cb, queue_size)
