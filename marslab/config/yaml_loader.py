"""Compose a scenario with an optional rover profile, then validate it.
Relative asset paths resolve from the YAML document that declares them.
Inline rover overrides merge recursively; sequences replace complete sequences.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

import yaml

from marslab.config.schema.root import MarsLabConfig

ROBOT_NAMES = ("perseverance", "spirit", "opportunity", "curiosity")
_PROFILE_DIRECTORY = Path(__file__).resolve().parents[2] / "configs" / "robots"


def _resolve_input_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=True)


def _anchor_path(raw: str, declaring_path: Path) -> str:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = declaring_path.parent / candidate
    return str(candidate.resolve(strict=False))


def _read_document(declaring_path: Path) -> dict:
    with declaring_path.open("r", encoding="utf-8") as stream:
        raw_data = yaml.safe_load(stream)
    if not isinstance(raw_data, Mapping):
        raise ValueError(f"YAML root must be a mapping: {declaring_path}")
    data = deepcopy(dict(raw_data))
    _resolve_asset_paths(data, declaring_path)
    return data


def _resolve_asset_paths(data: dict, declaring_path: Path) -> None:
    """Anchor paths before merging so each document retains its own base directory."""
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


def _merge_mapping(base: dict, overrides: Mapping) -> dict:
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(merged.get(key), dict) and isinstance(value, Mapping):
            merged[key] = _merge_mapping(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_robot_profile(robot: str) -> dict:
    if robot not in ROBOT_NAMES:
        raise ValueError(f"Unknown robot {robot!r}; choose one of {', '.join(ROBOT_NAMES)}")
    path = _resolve_input_path(_PROFILE_DIRECTORY / f"{robot}.yaml")
    profile = _read_document(path)
    if set(profile) != {"rover"} or not isinstance(profile["rover"], dict):
        raise ValueError(f"Robot profile must contain only a rover mapping: {path}")
    if profile["rover"].get("name") != robot:
        raise ValueError(f"Robot profile rover.name must equal {robot!r}: {path}")
    return profile["rover"]


def load_config(path: str | Path, *, robot: str | None = None) -> MarsLabConfig:
    """Load a legacy complete config or a scenario selecting ``robot: <name>``.

    ``robot`` overrides the scenario's selector. In profile-based scenarios, the
    optional inline ``rover`` mapping overrides profile settings. When selecting
    a robot for a legacy complete config, its old rover subtree is replaced.
    """
    data = _read_document(_resolve_input_path(path))
    configured_robot = data.pop("robot", None)
    selected_robot = robot if robot is not None else configured_robot
    if selected_robot is not None:
        rover_profile = _load_robot_profile(selected_robot)
        overrides = data.get("rover", {})
        if robot is not None and configured_robot is None and "rover" in data:
            logging.getLogger(__name__).info(
                "Robot %s replaces the legacy config's inline rover settings.", robot
            )
            overrides = {}
        if not isinstance(overrides, Mapping):
            raise ValueError("Inline rover overrides must be a mapping")
        data["rover"] = _merge_mapping(rover_profile, overrides)
        if data["rover"].get("name") != selected_robot:
            raise ValueError("Inline rover.name must match the selected robot")

    rover = data.get("rover")
    if isinstance(rover, dict):
        wheel_odometry = rover.get("wheel_odometry")
        if isinstance(wheel_odometry, dict) and "track_width" in wheel_odometry:
            raise ValueError(
                "wheel_odometry.track_width is obsolete; remove it and configure "
                "rover.control.wheelbase, track_steer, and track_middle"
            )
    drone = data.get("drone")
    if isinstance(drone, dict):
        asset = drone.get("asset_url")
        if isinstance(asset, str) and asset and "://" not in asset:
            drone["asset_url"] = _anchor_path(asset, declaring_path)

    return MarsLabConfig.model_validate_json(json.dumps(data, allow_nan=True))


__all__ = ["ROBOT_NAMES", "load_config"]
