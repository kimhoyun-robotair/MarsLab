"""Create the rover camera and shared render product.
RGB and depth handles remain available to independent consumers.
Isaac imports are confined to the spawner call."""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from marslab.config.schema.rover_sensors import CameraConfig
from marslab.quaternion import rpy_deg_to_quat
from marslab.sensors.depth_noise import DepthNoise, DepthSample

_LOG = logging.getLogger(__name__)
_MM_PER_ISAAC_FOCAL_LENGTH_UNIT = 10.0
_DEPTH_TIME_ANNOTATOR = "MarsLabDepthSimulationTime"


class _StageHandle(Protocol):
    pass


class _CameraHandle(Protocol):
    def initialize(self) -> None: ...

    def set_focal_length(self, value: float) -> None: ...

    def set_clipping_range(self, near: float, far: float) -> None: ...

    def get_intrinsics_matrix(self) -> np.ndarray: ...


class _AnnotatorHandle(Protocol):
    def attach(self, products: Sequence["_RenderProductHandle"]) -> None: ...

    def get_data(self) -> np.ndarray: ...


class _RenderProductHandle(Protocol):
    @property
    def path(self) -> str: ...


class _TimeAnnotatorHandle(Protocol):
    def get_data(self) -> dict[str, float]: ...


@dataclass(frozen=True, slots=True)
class CameraSpawnHandles:
    """Live camera and shared acquisition handles returned by ``spawn_camera``."""

    camera: _CameraHandle
    camera_prim_path: str
    render_product: _RenderProductHandle
    render_product_path: str
    rgb_annotator: _AnnotatorHandle
    depth_annotator: _AnnotatorHandle
    depth_time_annotator: _TimeAnnotatorHandle | None
    depth_noise: DepthNoise | None

    @property
    def depth_noise_enabled(self) -> bool:
        return self.depth_noise is not None

    def reset_depth_noise(self) -> None:
        if self.depth_noise is not None:
            self.depth_noise.reset()

    def read_depth_sample(self) -> DepthSample | None:
        """Read the shared render product's depth and acquisition timestamp."""
        if self.depth_noise is None or self.depth_time_annotator is None:
            return None
        from isaacsim.core.simulation_manager import SimulationManager

        raw = self.depth_annotator.get_data()
        timing = self.depth_time_annotator.get_data()
        if raw is None or not np.size(raw) or not timing:
            return None
        depth = np.asarray(raw, dtype=np.float32)
        if depth.ndim != 2:
            raise RuntimeError(f"Expected a two-dimensional depth image, got {depth.shape}")
        seconds = float(timing["simulationTime"])
        if not math.isfinite(seconds) or seconds < 0.0:
            raise RuntimeError(f"Invalid depth acquisition time: {seconds}")
        stamp_ns = int(seconds * 1_000_000_000)
        physics_stamp_ns = int(SimulationManager.get_simulation_time() * 1_000_000_000)
        # A GPU frame from before Stop can outlive the acquisition's episode reset.
        if stamp_ns > physics_stamp_ns + 1:
            return None
        return self.depth_noise.apply(depth, stamp_ns)

    def read_depth(self) -> np.ndarray:
        if self.depth_noise_enabled:
            sample = self.read_depth_sample()
            return np.array([] if sample is None else sample.depth_m, dtype=np.float32)
        raw = self.depth_annotator.get_data()
        return np.array([] if raw is None else raw, dtype=np.float32)


def spawn_camera(
    stage: _StageHandle,
    camera_cfg: CameraConfig,
    chassis_path: str,
    *,
    seed: int | None,
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
    if camera_cfg.horizontal_fov_deg is None:
        camera.set_focal_length(
            float(camera_cfg.focal_length_mm) / _MM_PER_ISAAC_FOCAL_LENGTH_UNIT
        )
    else:
        # Isaac exposes aperture and focal length in the same native units.
        aperture = camera.get_horizontal_aperture()
        width, height = camera_cfg.resolution
        camera.set_vertical_aperture(aperture * height / width, maintain_square_pixels=False)
        camera.set_focal_length(
            aperture / (2.0 * math.tan(math.radians(camera_cfg.horizontal_fov_deg) / 2.0))
        )
    camera.set_clipping_range(
        float(camera_cfg.clipping_range[0]), float(camera_cfg.clipping_range[1])
    )
    focal_length = camera.get_focal_length()
    _LOG.info(
        "Camera pinhole: horizontal FOV=%.3f deg vertical FOV=%.3f deg clipping=%s m",
        math.degrees(2.0 * math.atan(camera.get_horizontal_aperture() / (2.0 * focal_length))),
        math.degrees(2.0 * math.atan(camera.get_vertical_aperture() / (2.0 * focal_length))),
        camera_cfg.clipping_range,
    )

    render_product = rep.create.render_product(camera_prim_path, tuple(camera_cfg.resolution))
    rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
    depth_annotator = rep.AnnotatorRegistry.get_annotator("distance_to_image_plane")
    rgb_annotator.attach([render_product])
    depth_annotator.attach([render_product])
    depth_time_annotator = None
    depth_noise = None
    if camera_cfg.depth_sensor.enabled:
        from omni.syntheticdata import SyntheticData

        # ROS helper teardown must not detach the acquisition's time node.
        if _DEPTH_TIME_ANNOTATOR not in rep.AnnotatorRegistry.get_registered_annotators():
            rep.AnnotatorRegistry.register_annotator_from_node(
                name=_DEPTH_TIME_ANNOTATOR,
                input_rendervars=[
                    SyntheticData.NodeConnectionTemplate(
                        "rpFabricTime",
                        attributes_mapping={
                            "outputs:fabricFrameTimeNumerator": "inputs:referenceTimeNumerator",
                            "outputs:fabricFrameTimeDenominator": "inputs:referenceTimeDenominator",
                        },
                    ),
                    SyntheticData.NodeConnectionTemplate(
                        depth_annotator.template_name,
                        attributes_mapping={"outputs:exec": "inputs:execIn"},
                    ),
                ],
                node_type_id="isaacsim.core.nodes.IsaacReadSimulationTimeAnnotator",
            )
        depth_time_annotator = rep.AnnotatorRegistry.get_annotator(_DEPTH_TIME_ANNOTATOR)
        depth_time_annotator.initialize(resetOnStop=True)
        depth_time_annotator.attach([render_product])
        depth_noise = DepthNoise(camera_cfg.depth_sensor, seed)
        _LOG.info(
            "Depth post-processing: Gaussian mean=%s m sigma=%s m seed=%s; shared RGB product %s",
            camera_cfg.depth_sensor.noise_mean,
            camera_cfg.depth_sensor.noise_sigma,
            seed,
            render_product.path,
        )

    handles = CameraSpawnHandles(
        camera=camera,
        camera_prim_path=camera_prim_path,
        render_product=render_product,
        render_product_path=render_product.path,
        rgb_annotator=rgb_annotator,
        depth_annotator=depth_annotator,
        depth_time_annotator=depth_time_annotator,
        depth_noise=depth_noise,
    )
    return handles


__all__ = ["CameraSpawnHandles", "spawn_camera"]
