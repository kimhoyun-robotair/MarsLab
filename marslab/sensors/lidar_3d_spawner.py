"""Create the RTX 3-D LiDAR and point-cloud acquisition handle.
Profile resolution and runtime overrides stay in this spawner.
Isaac imports are deferred to runtime calls."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import numpy.typing as npt

from marslab.config.schema.rover_sensors import Lidar3DConfig
from marslab.quaternion import rpy_deg_to_quat
from marslab.sensors.lidar_runtime import apply_range_and_scan_overrides, resolve_omnilidar_prim

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

    def GetAttributes(self) -> Sequence["_AttributeHandle"]: ...


class _AttributeHandle(Protocol):
    def GetName(self) -> str: ...

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


def _apply_vertical_fov(prim: _PrimHandle, vertical_fov_deg: float) -> None:
    states = []
    for attribute in prim.GetAttributes():
        name = str(attribute.GetName())
        if name.startswith("omni:sensor:Core:emitterState:") and name.endswith(":elevationDeg"):
            values = attribute.Get()
            if values is not None:
                states.append((attribute, np.asarray(values, dtype=np.float64)))
    elevations = np.concatenate([values for _, values in states]) if states else np.array([])
    if elevations.size < 2 or not np.all(np.isfinite(elevations)):
        raise RuntimeError("3-D LiDAR profile requires finite emitter elevation arrays")
    low, high = float(elevations.min()), float(elevations.max())
    if high - low <= 1e-6:
        raise RuntimeError("3-D LiDAR profile must contain multiple elevation layers")
    center = (low + high) / 2.0
    for attribute, values in states:
        requested = ((values - center) * vertical_fov_deg / (high - low)).tolist()
        if not attribute.Set(requested):
            raise RuntimeError(f"LiDAR elevation write failed: {attribute.GetName()}")
        effective = attribute.Get()
        if effective is None or not np.allclose(effective, requested, rtol=1e-6, atol=1e-6):
            raise RuntimeError(f"LiDAR elevation readback mismatch: {attribute.GetName()}")
    _LOG.info("LiDAR %s: vertical FOV %.3f deg", prim.GetPath(), vertical_fov_deg)


def spawn_lidar_3d(
    stage: _StageHandle,
    lidar_cfg: Lidar3DConfig,
    chassis_path: str,
) -> Lidar3DSpawnHandles:
    """Create one configured RTX LiDAR and its point-cloud acquisition handle."""
    from isaacsim.sensors.rtx import LidarRtx

    lidar_prim_path = f"{chassis_path}/lidar_3d"
    if lidar_cfg.profile_name is None:
        raise ValueError("3-D LiDAR requires a named native USD model")
    lidar_kwargs: dict[str, str | npt.NDArray[np.float32]] = {
        "prim_path": lidar_prim_path,
        "name": "lidar_3d",
        "config_file_name": lidar_cfg.profile_name,
        "translation": np.asarray(lidar_cfg.local_translation, dtype=np.float32),
        "orientation": np.asarray(rpy_deg_to_quat(lidar_cfg.local_orientation_rpy_deg), dtype=np.float32),
    }
    if lidar_cfg.variant is not None:
        lidar_kwargs["variant"] = lidar_cfg.variant

    lidar = LidarRtx(**lidar_kwargs)
    prim = resolve_omnilidar_prim(stage, lidar_prim_path)
    apply_range_and_scan_overrides(prim, lidar_cfg)
    _apply_vertical_fov(prim, lidar_cfg.vertical_fov_deg)
    lidar.initialize()
    lidar.attach_annotator(_POINT_CLOUD_ANNOTATOR)
    point_cloud_annotator = lidar.get_annotators()[_POINT_CLOUD_ANNOTATOR]
    return Lidar3DSpawnHandles(
        lidar=lidar,
        lidar_prim_path=str(prim.GetPath()),
        render_product_path=lidar.get_render_product_path(),
        point_cloud_annotator=point_cloud_annotator,
    )


__all__ = ["Lidar3DSpawnHandles", "spawn_lidar_3d"]
