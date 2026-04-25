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
helper nodes) accepts the ``inputs:qosProfile`` string as a
**JSON-encoded QoS dict** matching the schema produced by
``isaacsim.ros2.bridge.ROS2QoSProfile``.  The schema (verified at
``isaacsim/ros2/bridge/ogn/python/nodes/OgnROS2QoSProfile.py:101-113``,
Isaac Sim 5.1) is::

    {"history": "keepLast" | "keepAll" | "systemDefault" | "unknown",
     "depth": <uint64>,
     "reliability": "reliable" | "bestEffort" | "systemDefault" | "unknown",
     "durability": "volatile" | "transientLocal" | "systemDefault" | "unknown",
     "deadline": <double seconds>,
     "lifespan": <double seconds>,
     "liveliness": "automatic" | "manualByTopic" | "systemDefault",
     "leaseDuration": <double seconds>}

Day 5 v1.0 sprint fix-up (2026-04-25):
:func:`to_omnigraph_qos_preset` previously returned bare preset names
(``"SystemDefault"``, ``"SensorData"``).  The downstream OmniGraph
node ran ``json.loads("SystemDefault")`` on every step and emitted
``Parsing error: ... last read: 'S'`` to stderr, flooding the log
(verified ``~/MarsLab/log.txt:520+`` ~5500 lines per session).  The
preset name was non-fatally interpreted by the C++ writer so the
simulation worked, but the noise made other warnings unreadable.
The helper now returns proper JSON which the writer parses cleanly.
"""

from __future__ import annotations

import json
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
    """Build the JSON-encoded QoS dict for Isaac Sim ``inputs:qosProfile``.

    Isaac Sim's ``isaacsim.ros2.bridge`` helper nodes (``ROS2PublishImu``,
    ``ROS2CameraHelper``, ``ROS2RtxLidarHelper``,
    ``ROS2PublishRawTransformTree``) expose a string ``qosProfile``
    input.  The string is parsed as JSON by the C++ writer matching
    the schema produced by ``OgnROS2QoSProfile``
    (``isaacsim/ros2/bridge/ogn/python/nodes/OgnROS2QoSProfile.py:101-113``,
    Isaac Sim 5.1).

    Mapping from MarsLab schema to Isaac Sim QoS JSON keys:

    * ``reliability``: ``"reliable"`` → ``"reliable"``,
      ``"best_effort"`` → ``"bestEffort"`` (camelCase).
    * ``durability``: ``"volatile"`` → ``"volatile"``,
      ``"transient_local"`` → ``"transientLocal"``.
    * ``history``: ``"keep_last"`` → ``"keepLast"``,
      ``"keep_all"`` → ``"keepAll"``.
    * ``depth``: passed through.
    * ``deadline`` / ``lifespan`` / ``leaseDuration``: 0.0 (no policy).
    * ``liveliness``: ``"systemDefault"`` (we do not expose this knob).

    Day 5 fix-up (2026-04-25): switched from bare preset names
    (``"SystemDefault"``, ``"SensorData"``) to the JSON encoding that
    the C++ writer expects.  The bare-name path produced
    ``Parsing error: ... last read: 'S'`` log spam on every step
    (verified ``~/MarsLab/log.txt:520+``).  The bare-name fallback in
    the C++ writer was non-fatal, so behaviour was correct, but the
    noise made other diagnostic output unreadable.

    Args:
        cfg: The validated :class:`QoSProfileConfig`.

    Returns:
        A JSON-encoded string suitable for direct assignment to
        ``inputs:qosProfile`` on any of the Isaac Sim ROS2 helper
        nodes.  Single-line, deterministic key order (alphabetical via
        ``sort_keys=True``) so identical configs produce identical
        strings, which keeps unit tests stable.
    """
    reliability_map = {"reliable": "reliable", "best_effort": "bestEffort"}
    durability_map = {"volatile": "volatile", "transient_local": "transientLocal"}
    history_map = {"keep_last": "keepLast", "keep_all": "keepAll"}

    if cfg.durability == "transient_local":
        logger.warning(
            "to_omnigraph_qos_preset: transient_local durability is "
            "honoured on the rclpy publish path but the OmniGraph "
            "writer's transient-local support is unverified in Isaac "
            "Sim 5.1.  Late joiners may still miss the first message "
            "on OmniGraph-only topics."
        )

    qos_dict = {
        "history": history_map[cfg.history],
        "depth": int(cfg.depth),
        "reliability": reliability_map[cfg.reliability],
        "durability": durability_map[cfg.durability],
        "deadline": 0.0,
        "lifespan": 0.0,
        "liveliness": "systemDefault",
        "leaseDuration": 0.0,
    }
    return json.dumps(qos_dict, sort_keys=True)
