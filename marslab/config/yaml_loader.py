"""Load and normalize the canonical integrated YAML document.
Relative asset paths resolve from the declaring config file.
The public result is one validated immutable root model."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

import yaml

from marslab.config.schema.root import MarsLabConfig


def _resolve_input_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=True)


def _anchor_path(raw: str, declaring_path: Path) -> str:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = declaring_path.parent / candidate
    return str(candidate.resolve(strict=False))


def load_config(path: str | Path) -> MarsLabConfig:
    declaring_path = _resolve_input_path(path)
    with declaring_path.open("r", encoding="utf-8") as stream:
        raw_data = yaml.safe_load(stream)
    if not isinstance(raw_data, Mapping):
        raise ValueError(f"YAML root must be a mapping: {declaring_path}")

    data = deepcopy(dict(raw_data))
    scene = data.get("scene")
    if isinstance(scene, dict):
        usdz_path = scene.get("usdz_path")
        if isinstance(usdz_path, str):
            scene["usdz_path"] = _anchor_path(usdz_path, declaring_path)

    rendering = data.get("rendering")
    if isinstance(rendering, dict):
        hdri_dir = rendering.get("sky_dome_hdri_dir")
        if isinstance(hdri_dir, str):
            rendering["sky_dome_hdri_dir"] = _anchor_path(hdri_dir, declaring_path)

    rover = data.get("rover")
    if isinstance(rover, dict):
        for field_name in ("usd_path", "urdf_source_path"):
            rover_path = rover.get(field_name)
            if isinstance(rover_path, str):
                rover[field_name] = _anchor_path(rover_path, declaring_path)
        sensors = rover.get("sensors")
        if isinstance(sensors, dict):
            lidar_3d = sensors.get("lidar_3d")
            if isinstance(lidar_3d, dict):
                profile_path = lidar_3d.get("profile_json_path")
                if isinstance(profile_path, str):
                    lidar_3d["profile_json_path"] = _anchor_path(profile_path, declaring_path)

    return MarsLabConfig.model_validate_json(json.dumps(data, allow_nan=True))


__all__ = ["load_config"]
