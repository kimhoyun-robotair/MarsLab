"""Create the rover camera and shared render product.
RGB and depth handles remain available to independent consumers.
Isaac imports are confined to the spawner call."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from marslab.config.schema.rover_sensors import CameraConfig
from marslab.quaternion import rpy_deg_to_quat

_LOG = logging.getLogger(__name__)
_MM_PER_ISAAC_FOCAL_LENGTH_UNIT = 10.0


class _StageHandle(Protocol):
    pass


class _CameraHandle(Protocol):
    def initialize(self) -> None: ...

    def set_focal_length(self, value: float) -> None: ...

    def set_clipping_range(self, near: float, far: float) -> None: ...


class _AnnotatorHandle(Protocol):
    def attach(self, products: Sequence["_RenderProductHandle"]) -> None: ...


class _RenderProductHandle(Protocol):
    @property
    def path(self) -> str: ...


@dataclass(frozen=True, slots=True)
class CameraSpawnHandles:
    """Live camera and shared acquisition handles returned by ``spawn_camera``."""

    camera: _CameraHandle
    camera_prim_path: str
    render_product: _RenderProductHandle
    render_product_path: str
    rgb_annotator: _AnnotatorHandle
    depth_annotator: _AnnotatorHandle


def spawn_camera(
    stage: _StageHandle,
    camera_cfg: CameraConfig,
    chassis_path: str,
) -> CameraSpawnHandles:
    """Create one configured Camera prim and its RGB/depth acquisition handles."""
    import omni.replicator.core as rep
    from isaacsim.sensors.camera import Camera
    from pxr import Gf, UsdGeom

    camera_orientation = camera_cfg.local_orientation_rpy_deg
    has_orientation = any(abs(value) > 0.01 for value in camera_orientation)
    if has_orientation:
        cam_qw, cam_qx, cam_qy, cam_qz = rpy_deg_to_quat(camera_orientation)
        camera_xform_path = f"{chassis_path}/camera_xform"
        camera_xform = UsdGeom.Xform.Define(stage, camera_xform_path)
        camera_xform.ClearXformOpOrder()
        camera_xform.AddTranslateOp().Set(Gf.Vec3d(*map(float, camera_cfg.local_translation)))
        camera_xform.AddOrientOp().Set(Gf.Quatf(cam_qw, cam_qx, cam_qy, cam_qz))
        camera_prim_path = f"{camera_xform_path}/camera"
        camera_translation = None
        _LOG.info("Camera parent Xform: %s rpy_deg=%s", camera_xform_path, camera_orientation)
    else:
        camera_prim_path = f"{chassis_path}/camera"
        camera_translation = np.asarray(camera_cfg.local_translation, dtype=np.float32)

    camera = Camera(
        prim_path=camera_prim_path,
        resolution=tuple(camera_cfg.resolution),
        translation=camera_translation,
    )
    camera.initialize()
    camera.set_focal_length(float(camera_cfg.focal_length_mm) / _MM_PER_ISAAC_FOCAL_LENGTH_UNIT)
    camera.set_clipping_range(
        float(camera_cfg.clipping_range[0]), float(camera_cfg.clipping_range[1])
    )

    render_product = rep.create.render_product(camera_prim_path, tuple(camera_cfg.resolution))
    rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
    depth_annotator = rep.AnnotatorRegistry.get_annotator("distance_to_image_plane")
    rgb_annotator.attach([render_product])
    depth_annotator.attach([render_product])

    return CameraSpawnHandles(
        camera=camera,
        camera_prim_path=camera_prim_path,
        render_product=render_product,
        render_product_path=render_product.path,
        rgb_annotator=rgb_annotator,
        depth_annotator=depth_annotator,
    )


__all__ = ["CameraSpawnHandles", "spawn_camera"]
