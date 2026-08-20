"""Build chassis-relative sensor TF frame records.
The transformation data stays pure and offline-testable.
Broadcast conversion is kept separate from sensor creation."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

_SENSOR_FRAME_BINDINGS: Tuple[Tuple[str, str], ...] = (
    ("camera_link", "camera"),
    ("lidar_link", "lidar_3d"),
    ("imu_link", "imu"),
)


def _resolve_sensor_block(sensors_cfg: Dict[str, Any], sensor_key: str) -> Dict[str, Any]:
    block = sensors_cfg.get(sensor_key)
    if not isinstance(block, dict):
        return {}
    return block


def build_sensor_frames(
    sensors_cfg: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Construct the static-TF frame list from the rover sensor block."""
    frames: List[Dict[str, Any]] = []
    for child_frame, sensor_key in _SENSOR_FRAME_BINDINGS:
        block = _resolve_sensor_block(sensors_cfg, sensor_key)
        if not block:
            continue
        if "local_translation" not in block:
            continue
        frames.append(
            {
                "child_frame": child_frame,
                "local_translation": list(block["local_translation"]),
                "local_orientation_rpy_deg": list(
                    block.get("local_orientation_rpy_deg", [0.0, 0.0, 0.0])
                ),
            }
        )
    return frames


def sensor_frames_to_tuples(
    frames: Sequence[Dict[str, Any]],
) -> List[Tuple[str, List[float], List[float]]]:
    """Adapt :func:`build_sensor_frames` output to the broadcaster API."""
    return [
        (
            str(frame["child_frame"]),
            list(frame["local_translation"]),
            list(frame.get("local_orientation_rpy_deg", [0.0, 0.0, 0.0])),
        )
        for frame in frames
    ]


__all__ = ["build_sensor_frames", "sensor_frames_to_tuples"]
