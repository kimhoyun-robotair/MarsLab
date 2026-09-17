"""Receive finite Twist commands and signal fresh input to the physics loop.

Queue depth and QoS are supplied by the validated ROS configuration.
The loop owns command expiry in simulation time.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


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
        twist_state: Shared command values and a receipt ``sequence``.
            The physics loop timestamps sequence changes in simulation time.
            Invalid commands replace both velocities with a stop command.
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

    twist_state.setdefault("sequence", 0)
    invalid_reported = False

    def _cb(msg: Twist) -> None:
        nonlocal invalid_reported
        v = float(msg.linear.x)
        w = float(msg.angular.z)
        valid = math.isfinite(v) and math.isfinite(w)
        if not valid:
            v = w = 0.0
            if not invalid_reported:
                logger.warning("Non-finite cmd_vel on %s; requesting a controlled stop", topic)
        invalid_reported = not valid
        twist_state.update(v=v, w=w, sequence=twist_state["sequence"] + 1)

    if qos is not None:
        # rclpy accepts QoSProfile as a positional arg identical in
        # slot to integer queue_size (overloaded at the rclpy layer).
        return node.create_subscription(Twist, topic, _cb, qos)
    return node.create_subscription(Twist, topic, _cb, queue_size)
