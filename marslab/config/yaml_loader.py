from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

import yaml

from marslab.config.schema.root import MarsLabConfig
from marslab.config.schema.rover import RoverConfig
from marslab.config.schema.scenario import ScenarioConfig


def _read_mapping(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


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


def load_scenario_config(path: str | Path) -> ScenarioConfig:
    declaring_path = _resolve_input_path(path)
    data = _read_mapping(declaring_path)
    rendering = data.get("rendering")
    if isinstance(rendering, dict):
        hdri_dir = rendering.get("sky_dome_hdri_dir")
        if isinstance(hdri_dir, str):
            rendering["sky_dome_hdri_dir"] = _anchor_path(hdri_dir, declaring_path)
    data["declaring_path"] = str(declaring_path)
    return ScenarioConfig.model_validate_json(json.dumps(data, allow_nan=True))


def load_rover_config(path: str | Path) -> RoverConfig:
    declaring_path = _resolve_input_path(path)
    data = _read_mapping(declaring_path)
    urdf_path = data.get("urdf_source_path")
    if isinstance(urdf_path, str):
        data["urdf_source_path"] = _anchor_path(urdf_path, declaring_path)
    sensors = data.get("sensors")
    if isinstance(sensors, dict):
        lidar_3d = sensors.get("lidar_3d")
        if isinstance(lidar_3d, dict):
            profile_path = lidar_3d.get("profile_json_path")
            if isinstance(profile_path, str):
                lidar_3d["profile_json_path"] = _anchor_path(profile_path, declaring_path)
    data["declaring_path"] = str(declaring_path)
    return RoverConfig.model_validate_json(json.dumps(data, allow_nan=True))


__all__ = ["load_rover_config", "load_scenario_config"]
