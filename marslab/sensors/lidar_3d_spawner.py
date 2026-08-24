"""Create the RTX 3-D LiDAR and point-cloud acquisition handle.
Profile resolution and runtime overrides stay in this spawner.
Isaac imports are deferred to runtime calls."""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import numpy.typing as npt

from marslab.config.schema.rover_sensors import Lidar3DConfig

_POINT_CLOUD_ANNOTATOR = "IsaacExtractRTXSensorPointCloudNoAccumulator"
_LOG = logging.getLogger(__name__)


class _StageHandle(Protocol):
    def GetPrimAtPath(self, prim_path: str) -> "_PrimHandle | None": ...


class _PrimHandle(Protocol):
    def IsValid(self) -> bool: ...

    def GetTypeName(self) -> str: ...

    def GetChildren(self) -> Sequence["_PrimHandle"]: ...

    def GetPath(self) -> str: ...

    def GetAttribute(self, name: str) -> "_AttributeHandle": ...


class _AttributeHandle(Protocol):
    def Set(self, value: float | list[float]) -> bool: ...

    def Get(self) -> float | Sequence[float] | None: ...


class _PointCloudAnnotator(Protocol):
    def get_data(self) -> Mapping[str, npt.NDArray[np.float32]]: ...


class _LidarHandle(Protocol):
    def initialize(self) -> None: ...

    def attach_annotator(self, annotator_name: str) -> None: ...

    def get_annotators(self) -> Mapping[str, _PointCloudAnnotator]: ...

    def get_render_product_path(self) -> str: ...


@dataclass(frozen=True, slots=True)
class Lidar3DSpawnHandles:
    """Live LiDAR and ROS-independent point-cloud acquisition handles."""

    lidar: _LidarHandle
    lidar_prim_path: str
    render_product_path: str
    point_cloud_annotator: _PointCloudAnnotator

    def read_point_cloud(self) -> npt.NDArray[np.float32]:
        """Read the current annotator frame on demand as an ``(N, 3)`` array."""
        data = self.point_cloud_annotator.get_data()
        points = data.get("data")
        if points is None or points.size == 0:
            return np.empty((0, 3), dtype=np.float32)
        return np.asarray(points, dtype=np.float32).reshape(-1, 3)


def _resolve_lidar_profile(config: Lidar3DConfig) -> str:
    """Resolve the configured profile name or explicit JSON path."""
    profile_json_path: Path | None = config.profile_json_path
    if profile_json_path is not None:
        return str(profile_json_path)
    profile_name: str | None = config.profile_name
    if profile_name is not None:
        return profile_name
    raise ValueError("LiDAR config requires profile_name or profile_json_path")


def _resolve_omnilidar_prim_path(stage: _StageHandle, prim_path: str) -> str:
    """Find a referenced OmniLidar descendant when a carrier Xform is used."""
    if not hasattr(stage, "GetPrimAtPath"):
        return prim_path
    root = stage.GetPrimAtPath(prim_path)
    if root is None or not root.IsValid() or root.GetTypeName() == "OmniLidar":
        return prim_path
    stack = list(root.GetChildren())
    while stack:
        child = stack.pop()
        if child.GetTypeName() == "OmniLidar":
            return str(child.GetPath())
        stack.extend(child.GetChildren())
    return prim_path


def _set_verified_scalar(
    prim: _PrimHandle,
    attribute_name: str,
    requested: float,
) -> float:
    attribute = prim.GetAttribute(attribute_name)
    if not attribute.Set(requested):
        raise RuntimeError(f"LiDAR override write failed: {attribute_name}={requested}")
    effective = attribute.Get()
    if effective is None or isinstance(effective, Sequence):
        raise RuntimeError(f"LiDAR override readback missing: {attribute_name}")
    effective_value = float(effective)
    if not math.isclose(effective_value, requested, rel_tol=1e-6, abs_tol=1e-6):
        raise RuntimeError(
            f"LiDAR override mismatch for {attribute_name}: "
            f"requested={requested}, effective={effective_value}"
        )
    return effective_value


def _apply_lidar_runtime_overrides(
    stage: _StageHandle,
    prim_path: str,
    config: Lidar3DConfig,
) -> None:
    """Apply range, rate, and FOV overrides to the loaded OmniLidar prim."""
    if not hasattr(stage, "GetPrimAtPath"):
        return
    prim = stage.GetPrimAtPath(prim_path)
    if prim is None or not prim.IsValid():
        raise RuntimeError(f"OmniLidar prim not found at {prim_path!r}")

    near_range = _set_verified_scalar(prim, "omni:sensor:Core:nearRangeM", float(config.range_min))
    far_range = _set_verified_scalar(prim, "omni:sensor:Core:farRangeM", float(config.range_max))
    scan_rate = _set_verified_scalar(
        prim, "omni:sensor:Core:scanRateBaseHz", float(config.rotation_rate_hz)
    )

    half_fov = float(config.horizontal_fov_deg) / 2.0
    if half_fov >= 180.0:
        start_azimuth, end_azimuth = 0.0, 360.0
    else:
        start_azimuth, end_azimuth = 360.0 - half_fov, half_fov
    effective_start = _set_verified_scalar(
        prim, "omni:sensor:Core:validStartAzimuthDeg", start_azimuth
    )
    effective_end = _set_verified_scalar(prim, "omni:sensor:Core:validEndAzimuthDeg", end_azimuth)

    elevation_attribute = prim.GetAttribute("omni:sensor:Core:emitterState:s001:elevationDeg")
    existing_value = elevation_attribute.Get()
    existing = (
        [] if existing_value is None or isinstance(existing_value, float) else list(existing_value)
    )
    if existing:
        current_span = max(existing) - min(existing)
        if current_span > 1e-6:
            center = (max(existing) + min(existing)) / 2.0
            scale = float(config.vertical_fov_deg) / current_span
            requested_elevations = [(value - center) * scale for value in existing]
            if not elevation_attribute.Set(requested_elevations):
                raise RuntimeError("LiDAR elevation override write failed")
            effective_elevations = elevation_attribute.Get()
            if effective_elevations is None or not np.allclose(
                effective_elevations,
                requested_elevations,
                rtol=1e-6,
                atol=1e-6,
            ):
                raise RuntimeError("LiDAR elevation override readback mismatch")

    _LOG.info(
        "LiDAR runtime overrides:\n"
        "  range: %.3f to %.3f m\n"
        "  rotation rate: %.3f Hz\n"
        "  azimuth: %.3f to %.3f deg",
        near_range,
        far_range,
        scan_rate,
        effective_start,
        effective_end,
    )


def _rpy_deg_to_quat_wxyz(rpy_deg: Iterable[float]) -> tuple[float, float, float, float]:
    """Convert ZYX roll-pitch-yaw degrees to a WXYZ quaternion."""
    values = list(rpy_deg)
    if len(values) != 3:
        raise ValueError(
            f"orientation rpy must have 3 entries (roll, pitch, yaw deg); got {values!r}"
        )
    roll, pitch, yaw = (math.radians(float(value)) for value in values)
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return (
        float(cr * cp * cy + sr * sp * sy),
        float(sr * cp * cy - cr * sp * sy),
        float(cr * sp * cy + sr * cp * sy),
        float(cr * cp * sy - sr * sp * cy),
    )


def spawn_lidar_3d(
    stage: _StageHandle,
    lidar_cfg: Lidar3DConfig,
    chassis_path: str,
) -> Lidar3DSpawnHandles:
    """Create one configured RTX LiDAR and its point-cloud acquisition handle."""
    from isaacsim.sensors.rtx import LidarRtx

    lidar_prim_path = f"{chassis_path}/lidar_3d"
    lidar_kwargs: dict[str, str | npt.NDArray[np.float32]] = {
        "prim_path": lidar_prim_path,
        "config_file_name": _resolve_lidar_profile(lidar_cfg),
        "translation": np.asarray(lidar_cfg.local_translation, dtype=np.float32),
    }
    if any(abs(value) > 0.01 for value in lidar_cfg.local_orientation_rpy_deg):
        lidar_kwargs["orientation"] = np.asarray(
            _rpy_deg_to_quat_wxyz(lidar_cfg.local_orientation_rpy_deg), dtype=np.float32
        )
    if lidar_cfg.usd_profile is not None:
        lidar_kwargs["name"] = lidar_cfg.usd_profile
    if lidar_cfg.variant is not None:
        lidar_kwargs["variant"] = lidar_cfg.variant

    lidar = LidarRtx(**lidar_kwargs)
    resolved_prim_path = _resolve_omnilidar_prim_path(stage, lidar_prim_path)
    _apply_lidar_runtime_overrides(stage, resolved_prim_path, lidar_cfg)
    lidar.initialize()
    lidar.attach_annotator(_POINT_CLOUD_ANNOTATOR)
    point_cloud_annotator = lidar.get_annotators()[_POINT_CLOUD_ANNOTATOR]
    return Lidar3DSpawnHandles(
        lidar=lidar,
        lidar_prim_path=resolved_prim_path,
        render_product_path=lidar.get_render_product_path(),
        point_cloud_annotator=point_cloud_annotator,
    )


__all__ = ["Lidar3DSpawnHandles", "spawn_lidar_3d"]
