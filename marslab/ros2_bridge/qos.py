"""QoS profile adapter: pydantic ``QoSProfileConfig`` → ``rclpy.qos.QoSProfile``.

Isolated in its own module so the rest of the bridge can stay
Isaac-Sim-runtime-focused: the ``rclpy.qos`` imports live inside the
function body and are therefore evaluated only when the Stage-3
runtime actually spins up rclpy.  Unit tests that import
:mod:`marslab.ros2_bridge.qos` without rclpy on the PYTHONPATH will
succeed at import time and fail only if they call
:func:`to_rclpy_qos`.

Reviewer 2 #04 (2026-04-24) mandated QoS profile plumbing through
every publisher / subscriber in the bridge.  The adapter here is the
single conversion point so the mapping

    reliability: "reliable" | "best_effort"
    durability:  "volatile" | "transient_local"
    history:     "keep_last" | "keep_all"
    depth:       int

is declared in one place.  The OmniGraph side (Isaac Sim ROS2 bridge
helper nodes) accepts a different encoding: the
``ROS2PublishImu`` / ``ROS2CameraHelper`` / ``ROS2RtxLidarHelper``
nodes take a **string preset** on the ``inputs:qosProfile`` attribute,
not a structured QoSProfile object.  The preset strings accepted by
Isaac Sim 5.x (verified against the ``isaacsim.ros2.bridge``
extension shipped with Kit 106+) are:

* ``"SystemDefault"`` — RELIABLE + VOLATILE + KEEP_LAST(10)
* ``"ServicesDefault"`` — RELIABLE + VOLATILE + KEEP_LAST(10) (shallower keep)
* ``"SensorData"`` — BEST_EFFORT + VOLATILE + KEEP_LAST(5)
* ``"ParameterEvents"`` — RELIABLE + VOLATILE + KEEP_LAST(1000)
* ``""`` (empty) — the node falls back to SystemDefault

We expose :func:`to_omnigraph_qos_preset` to pick the closest preset
for a given :class:`QoSProfileConfig`.  When the config does not map
cleanly to a bundled preset (for example RELIABLE + TRANSIENT_LOCAL,
which Isaac Sim has no named preset for in 5.0), the helper returns
``"SystemDefault"`` and emits a warning so the user knows the
OmniGraph side is NOT honouring their TRANSIENT_LOCAL request.  The
rclpy side (``create_publisher`` / ``create_subscription``) receives
the exact ``QoSProfile`` regardless, so the ``/tf_static``
transient-local guarantee is preserved on at least one publish path.
"""

from __future__ import annotations

import logging
from typing import Any

from marslab.config.schema.ros2_bridge import QoSProfileConfig

__all__ = [
    "to_rclpy_qos",
    "to_omnigraph_qos_preset",
]

logger = logging.getLogger(__name__)


def to_rclpy_qos(cfg: QoSProfileConfig) -> Any:
    """Return a ``rclpy.qos.QoSProfile`` built from ``cfg``.

    rclpy is imported lazily so this module stays importable without
    the ROS 2 distro on PYTHONPATH.  Tests that exercise the mapping
    logic should use ``pytest.importorskip("rclpy")`` or monkey-patch
    ``sys.modules["rclpy.qos"]`` before calling.

    Args:
        cfg: The validated :class:`QoSProfileConfig` from the scenario
            YAML.  The string fields are already constrained by
            ``Literal[...]`` on the schema so no further validation is
            needed here.

    Returns:
        A ``rclpy.qos.QoSProfile`` instance.  Typed as ``Any`` because
        the return type depends on the lazily-imported rclpy module.
    """
    # Runtime-only import keeps the module import surface pure-Python.
    # Callers that do not have rclpy (unit tests) should never reach
    # this line in the first place.
    from rclpy.qos import (
        DurabilityPolicy,
        HistoryPolicy,
        QoSProfile,
        ReliabilityPolicy,
    )

    reliability_map = {
        "reliable": ReliabilityPolicy.RELIABLE,
        "best_effort": ReliabilityPolicy.BEST_EFFORT,
    }
    durability_map = {
        "volatile": DurabilityPolicy.VOLATILE,
        "transient_local": DurabilityPolicy.TRANSIENT_LOCAL,
    }
    history_map = {
        "keep_last": HistoryPolicy.KEEP_LAST,
        "keep_all": HistoryPolicy.KEEP_ALL,
    }

    return QoSProfile(
        reliability=reliability_map[cfg.reliability],
        durability=durability_map[cfg.durability],
        history=history_map[cfg.history],
        depth=int(cfg.depth),
    )


def to_omnigraph_qos_preset(cfg: QoSProfileConfig) -> str:
    """Pick the closest Isaac Sim OmniGraph ``qosProfile`` preset string.

    Isaac Sim's ``isaacsim.ros2.bridge`` helper nodes (``ROS2PublishImu``,
    ``ROS2CameraHelper``, ``ROS2RtxLidarHelper``,
    ``ROS2PublishRawTransformTree``) expose a string ``qosProfile``
    input rather than a structured profile.  The preset vocabulary is
    fixed by the extension; this helper maps our schema to the
    closest preset.

    Mapping (verified against Isaac Sim 5.x ``isaacsim.ros2.bridge``):

    * ``best_effort`` + ``volatile`` → ``"SensorData"``  (matches the
      sensor_data convention: LiDAR scans, raw camera frames, IMU).
    * ``reliable`` + ``transient_local`` → ``"SystemDefault"`` + warning
      (no bundled preset is transient-local; the caller must wire a
      rclpy-side republisher if TRANSIENT_LOCAL is essential).
    * everything else → ``"SystemDefault"`` (RELIABLE + VOLATILE +
      depth 10).  Matches Nav2 controller_server output for cmd_vel
      and nav_msgs/Odometry for odom.

    Args:
        cfg: The validated :class:`QoSProfileConfig`.

    Returns:
        The preset string to assign to ``inputs:qosProfile`` on the
        Isaac Sim helper node.  Never returns empty (which would fall
        back to SystemDefault implicitly) — always explicit for
        audit / grep-friendliness.
    """
    if cfg.reliability == "best_effort" and cfg.durability == "volatile":
        return "SensorData"
    if cfg.durability == "transient_local":
        logger.warning(
            "to_omnigraph_qos_preset: no bundled Isaac Sim preset for "
            "transient_local durability; falling back to SystemDefault. "
            "The rclpy-side publisher (if any) will still honour "
            "transient_local; OmniGraph-only topics (e.g. PubTF on "
            "/tf_raw) will NOT be latched to late joiners."
        )
        return "SystemDefault"
    return "SystemDefault"
