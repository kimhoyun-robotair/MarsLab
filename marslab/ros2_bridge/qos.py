"""Translate validated QoS settings for rclpy and OmniGraph.
One adapter owns reliability, durability, history, and depth mapping.
ROS imports stay deferred until conversion is requested."""

from __future__ import annotations

import json
from typing import Any

from marslab.config.schema.rover_ros2 import QoSProfileConfig

__all__ = [
    "to_rclpy_qos",
    "to_omnigraph_qos_json",
]


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
    reliability_map = {"reliable": "reliable", "best_effort": "bestEffort"}
    history_map = {"keep_last": "keepLast", "keep_all": "keepAll"}

    if cfg.durability != "volatile":
        raise ValueError(
            "OmniGraph publishers require volatile durability; "
            "transient-local delivery is not a MarsLab runtime contract"
        )

    qos_dict = {
        "history": history_map[cfg.history],
        "depth": int(cfg.depth),
        "reliability": reliability_map[cfg.reliability],
        "durability": "volatile",
        "deadline": 0.0,
        "lifespan": 0.0,
        "liveliness": "systemDefault",
        "leaseDuration": 0.0,
    }
    return json.dumps(qos_dict, sort_keys=True)
