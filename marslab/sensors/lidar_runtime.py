"""Apply verified range and azimuth overrides to native OmniLidar prims."""

from __future__ import annotations

import logging
import math
from typing import Any

from marslab.config.schema.rover_sensors import Lidar2DConfig, Lidar3DConfig

_LOG = logging.getLogger(__name__)


def resolve_omnilidar_prim(stage: Any, prim_path: str) -> Any:
    root = stage.GetPrimAtPath(prim_path)
    if not root.IsValid():
        raise RuntimeError(f"LiDAR root prim not found at {prim_path!r}")
    stack = [root]
    while stack:
        prim = stack.pop()
        if prim.GetTypeName() == "OmniLidar":
            return prim
        stack.extend(prim.GetChildren())
    raise RuntimeError(f"No OmniLidar acquisition prim below {prim_path!r}")


def set_verified_scalar(prim: Any, attribute_name: str, requested: float) -> float:
    attribute = prim.GetAttribute(attribute_name)
    value = int(requested) if str(attribute.GetTypeName()) == "uint" else requested
    if not attribute.IsValid() or not attribute.Set(value):
        raise RuntimeError(f"LiDAR override write failed: {attribute_name}={requested}")
    effective = attribute.Get()
    if effective is None or not math.isclose(
        float(effective), requested, rel_tol=1e-6, abs_tol=1e-6
    ):
        raise RuntimeError(
            f"LiDAR override mismatch for {attribute_name}: "
            f"requested={requested}, effective={effective}"
        )
    return float(effective)


def apply_range_and_scan_overrides(
    prim: Any,
    config: Lidar2DConfig | Lidar3DConfig,
    *,
    native_horizontal_fov_deg: float | None = None,
) -> None:
    near_range = set_verified_scalar(prim, "omni:sensor:Core:nearRangeM", config.range_min)
    far_range = set_verified_scalar(prim, "omni:sensor:Core:farRangeM", config.range_max)
    ray_offset = set_verified_scalar(prim, "omni:sensor:Core:rangeOffsetM", config.range_min)
    scan_rate = set_verified_scalar(prim, "omni:sensor:Core:scanRateBaseHz", config.rotation_rate_hz)
    fov = config.horizontal_fov_deg if native_horizontal_fov_deg is None else native_horizontal_fov_deg
    half_fov = fov / 2.0
    azimuth_offset = float(prim.GetAttribute("omni:sensor:Core:startAzimuthOffsetDeg").Get())
    if not math.isfinite(azimuth_offset):
        raise RuntimeError(f"LiDAR has a non-finite start azimuth offset: {prim.GetPath()}")
    # The native FOV gate uses emitter angles before the sensor's azimuth offset.
    start, end = (
        (0.0, 360.0)
        if half_fov >= 180.0
        else ((-azimuth_offset - half_fov) % 360.0, (-azimuth_offset + half_fov) % 360.0)
    )
    set_verified_scalar(prim, "omni:sensor:Core:validStartAzimuthDeg", start)
    set_verified_scalar(prim, "omni:sensor:Core:validEndAzimuthDeg", end)
    _LOG.info(
        "LiDAR %s: range %.3f–%.3f m, ray origin offset %.3f m, scan %.3f Hz, azimuth %.3f–%.3f deg",
        prim.GetPath(), near_range, far_range, ray_offset, scan_rate, start, end,
    )
