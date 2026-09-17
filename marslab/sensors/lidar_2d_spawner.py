"""Create a horizontal RTX LiDAR and ROS-independent flat-scan acquisition."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from marslab.config.schema.rover_sensors import Lidar2DConfig
from marslab.quaternion import rpy_deg_to_quat
from marslab.sensors.lidar_runtime import (
    apply_range_and_scan_overrides,
    resolve_omnilidar_prim,
    set_verified_scalar,
)

_FLAT_SCAN_ANNOTATOR = "IsaacComputeRTXLidarFlatScan"
_SCAN_TIME_ANNOTATOR = "MarsLabLidar2DScanTime"


@dataclass(frozen=True, slots=True)
class Lidar2DSpawnHandles:
    lidar: Any
    lidar_prim_path: str
    render_product_path: str
    flat_scan_annotator: Any
    scan_time_annotator: Any
    horizontal_fov_deg: float

    def read_scan(self) -> Mapping[str, Any]:
        scan = self.flat_scan_annotator.get_data()
        ranges = np.asarray(scan.get("linearDepthData", []), dtype=np.float32)
        intensities = np.asarray(scan.get("intensitiesData", []), dtype=np.float32)
        columns = int(scan.get("numCols", 0))
        resolution = float(scan.get("horizontalResolution", 0.0))
        rotation_rate = float(scan.get("rotationRate", 0.0))
        azimuth = np.asarray(scan.get("azimuthRange", []), dtype=np.float64)
        if (
            ranges.ndim != 1
            or columns != ranges.size
            or columns <= 0
            or intensities.ndim != 1
            or intensities.size not in (0, columns)
            or azimuth.shape != (2,)
            or not np.isfinite(azimuth).all()
            or not math.isfinite(resolution)
            or resolution <= 0.0
            or not math.isfinite(rotation_rate)
            or rotation_rate <= 0.0
        ):
            return {}

        # Keep the configured forward sector from native full-turn acquisition.
        angles = float(azimuth[0]) + np.arange(columns) * resolution
        half_fov = self.horizontal_fov_deg / 2.0
        tolerance = max(1e-5, resolution * 1e-4)
        selected = np.flatnonzero(
            (angles >= -half_fov - tolerance) & (angles <= half_fov + tolerance)
        )
        if selected.size == 0:
            return {}
        first, last = int(selected[0]), int(selected[-1])
        first_angle, last_angle = float(angles[first]), float(angles[last])
        scan_time = 1.0 / rotation_rate
        return {
            **scan,
            "linearDepthData": ranges[first : last + 1],
            "intensitiesData": intensities[first : last + 1] if intensities.size else intensities,
            "numCols": last - first + 1,
            "azimuthRange": np.asarray([first_angle, last_angle], dtype=np.float64),
            "horizontalFov": last_angle - first_angle,
            "timeIncrementSeconds": scan_time * resolution / 360.0,
            "firstRayOffsetSeconds": scan_time * (first_angle + 180.0) / 360.0,
        }

    def read_scan_timestamp_ns(self) -> int | None:
        from isaacsim.core.simulation_manager import SimulationManager

        timing = self.scan_time_annotator.get_data()
        value = timing.get("simulationTime")
        if value is None:
            return None
        seconds = float(value)
        if not math.isfinite(seconds) or seconds <= 0.0:
            return None
        stamp_ns = int(round(seconds * 1_000_000_000))
        completed_ns = int(round(SimulationManager.get_simulation_time() * 1_000_000_000))
        if stamp_ns > completed_ns + 1:
            return None
        return stamp_ns


def spawn_lidar_2d(stage: Any, lidar_cfg: Lidar2DConfig, chassis_path: str) -> Lidar2DSpawnHandles:
    import omni.replicator.core as rep
    from omni.syntheticdata import SyntheticData
    from isaacsim.sensors.rtx import LidarRtx

    prim_path = f"{chassis_path}/lidar_2d"
    lidar = LidarRtx(
        prim_path=prim_path,
        name="lidar_2d",
        config_file_name="Example_Rotary_2D",
        translation=np.asarray(lidar_cfg.local_translation, dtype=np.float32),
        orientation=np.asarray(rpy_deg_to_quat(lidar_cfg.local_orientation_rpy_deg), dtype=np.float32),
    )
    prim = resolve_omnilidar_prim(stage, prim_path)
    direction = prim.GetAttribute("omni:sensor:Core:rotationDirection")
    if not direction.Set("CCW") or direction.Get() != "CCW":
        raise RuntimeError("2-D LiDAR requires counterclockwise angular ordering")
    set_verified_scalar(prim, "omni:sensor:Core:startAzimuthOffsetDeg", 180.0)
    # Full-turn acquisition preserves native completion timing; read_scan limits the usable sector.
    apply_range_and_scan_overrides(prim, lidar_cfg, native_horizontal_fov_deg=360.0)
    elevation_attributes = [
        attribute
        for attribute in prim.GetAttributes()
        if str(attribute.GetName()).startswith("omni:sensor:Core:emitterState:")
        and str(attribute.GetName()).endswith(":elevationDeg")
    ]
    if not elevation_attributes:
        raise RuntimeError("2-D LiDAR profile has no emitter elevation arrays")
    for attribute in elevation_attributes:
        values = attribute.Get()
        if values is None or len(values) != 1:
            raise RuntimeError("2-D LiDAR profile requires exactly one emitter per state")
        if not attribute.Set([0.0]) or not np.allclose(attribute.Get(), [0.0], atol=1e-6):
            raise RuntimeError("2-D LiDAR could not establish a horizontal scan plane")
    lidar.initialize()
    lidar.attach_annotator(_FLAT_SCAN_ANNOTATOR)
    if _SCAN_TIME_ANNOTATOR not in rep.AnnotatorRegistry.get_registered_annotators():
        rep.AnnotatorRegistry.register_annotator_from_node(
            name=_SCAN_TIME_ANNOTATOR,
            input_rendervars=[
                SyntheticData.NodeConnectionTemplate(
                    _FLAT_SCAN_ANNOTATOR,
                    attributes_mapping={"outputs:exec": "inputs:execIn"},
                ),
                SyntheticData.NodeConnectionTemplate(
                    "rpFabricTime",
                    attributes_mapping={
                        "outputs:fabricFrameTimeNumerator": "inputs:referenceTimeNumerator",
                        "outputs:fabricFrameTimeDenominator": "inputs:referenceTimeDenominator",
                    },
                ),
            ],
            node_type_id="isaacsim.core.nodes.IsaacReadSimulationTimeAnnotator",
        )
    scan_time_annotator = rep.AnnotatorRegistry.get_annotator(_SCAN_TIME_ANNOTATOR)
    scan_time_annotator.initialize(resetOnStop=True)
    scan_time_annotator.attach([lidar.get_render_product_path()])
    return Lidar2DSpawnHandles(
        lidar=lidar,
        lidar_prim_path=str(prim.GetPath()),
        render_product_path=lidar.get_render_product_path(),
        flat_scan_annotator=lidar.get_annotators()[_FLAT_SCAN_ANNOTATOR],
        scan_time_annotator=scan_time_annotator,
        horizontal_fov_deg=lidar_cfg.horizontal_fov_deg,
    )


__all__ = ["Lidar2DSpawnHandles", "spawn_lidar_2d"]
