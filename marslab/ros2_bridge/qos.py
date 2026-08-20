"""Translate validated QoS settings for rclpy and OmniGraph.
One adapter owns reliability, durability, history, and depth mapping.
ROS imports stay deferred until conversion is requested."""

from __future__ import annotations

import json
import logging
from typing import Any

from marslab.config.schema.rover_ros2 import QoSProfileConfig

__all__ = [
    "to_rclpy_qos",
    "to_omnigraph_qos_json",
]

logger = logging.getLogger(__name__)

_transient_local_warned = False


def _reset_transient_local_warned() -> None:
    """Test hook: clear the once-per-process warning latch."""
    global _transient_local_warned
    _transient_local_warned = False


def to_rclpy_qos(cfg: QoSProfileConfig) -> Any:
    """Return a ``rclpy.qos.QoSProfile`` built from ``cfg``."""
    from rclpy.qos import (  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope
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


def to_omnigraph_qos_json(cfg: QoSProfileConfig) -> str:
    """Build the JSON-encoded QoS dict for Isaac Sim ``inputs:qosProfile``."""
    global _transient_local_warned

    reliability_map = {"reliable": "reliable", "best_effort": "bestEffort"}
    durability_map = {"volatile": "volatile", "transient_local": "transientLocal"}
    history_map = {"keep_last": "keepLast", "keep_all": "keepAll"}

    if cfg.durability == "transient_local" and not _transient_local_warned:
        logger.warning(
            "to_omnigraph_qos_json: transient_local durability is "
            "honoured on the rclpy publish path but the OmniGraph "
            "writer's transient-local support is unverified in Isaac "
            "Sim 5.1.  Late joiners may still miss the first message "
            "on OmniGraph-only topics."
        )
        _transient_local_warned = True

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
