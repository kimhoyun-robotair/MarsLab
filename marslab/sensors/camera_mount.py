"""Resolve camera rigid mounts and reject authored USD/ROS pose disagreements.

USD imports are deferred so configuration and graph helpers remain usable
outside Isaac. Validation runs before any camera acquisition is initialized.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from marslab.config.schema.rover_sensors import CameraConfig
from marslab.quaternion import rpy_deg_to_quat

# Camera-link FLU basis vectors expressed in USD graphics-camera coordinates.
_USD_FROM_CAMERA_LINK = np.array([[0.0, -1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]])
_TRANSLATION_TOLERANCE_M = 1e-5
_ROTATION_MATRIX_TOLERANCE = 1e-6


def resolve_camera_mount_path(stage: Any, config: CameraConfig, chassis_path: str) -> str:
    """Find the configured sibling rigid link, preserving the chassis default."""
    from pxr import UsdGeom, UsdPhysics

    mount_path = (
        f"{chassis_path.rsplit('/', 1)[0]}/{config.parent_link}"
        if config.parent_link is not None
        else chassis_path
    )
    mount = stage.GetPrimAtPath(mount_path)
    if not mount.IsValid() or not UsdGeom.Xformable(mount):
        raise ValueError(f"Camera mount link is missing or not transformable: {mount_path}")
    if config.parent_link is not None and not mount.HasAPI(UsdPhysics.RigidBodyAPI):
        raise ValueError(f"Camera parent_link is not a USD rigid body: {mount_path}")
    return mount_path


def validate_authored_camera_pose(
    stage: Any,
    config: CameraConfig,
    mount_path: str,
    camera_path: str,
) -> None:
    """Check that the USD camera inherits its mount and matches its static ROS TF.

    Intervening fixed Xforms are included in the relative pose. A reset transform
    stack or another rigid link would make the selected static TF parent wrong.
    The source USD pose is never modified to hide a configuration disagreement.
    """
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

    camera = stage.GetPrimAtPath(camera_path)
    mount = stage.GetPrimAtPath(mount_path)
    if not camera.IsValid() or not camera.IsA(UsdGeom.Camera):
        raise ValueError(f"Configured camera prim is missing or not a Camera: {camera_path}")
    if not camera.GetPath().HasPrefix(Sdf.Path(mount_path)) or camera.GetPath() == mount.GetPath():
        raise ValueError(f"Camera {camera_path} must be below its configured mount {mount_path}")

    ancestor = camera
    while ancestor != mount:
        transformable = UsdGeom.Xformable(ancestor)
        if transformable and transformable.GetResetXformStack():
            raise ValueError(f"Camera mount inheritance is reset at {ancestor.GetPath()}")
        if ancestor.HasAPI(UsdPhysics.RigidBodyAPI):
            raise ValueError(
                f"Camera {camera_path} crosses another rigid link {ancestor.GetPath()}; "
                "set parent_link to the camera's actual rigid link"
            )
        ancestor = ancestor.GetParent()

    relative, _ = UsdGeom.XformCache(Usd.TimeCode.Default()).ComputeRelativeTransform(camera, mount)
    # USD matrices multiply row vectors; quaternion/ROS rotation matrices use columns.
    relative_matrix = np.asarray(relative, dtype=np.float64)
    authored_translation = relative_matrix[3, :3]
    authored_rotation = relative_matrix[:3, :3].T @ _USD_FROM_CAMERA_LINK
    qw, qx, qy, qz = rpy_deg_to_quat(config.local_orientation_rpy_deg)
    expected_rotation = np.asarray(
        Gf.Matrix3d(Gf.Quatd(float(qw), Gf.Vec3d(float(qx), float(qy), float(qz))))
    ).T
    position_error = float(np.linalg.norm(authored_translation - config.local_translation))
    rotation_error = float(np.max(np.abs(authored_rotation - expected_rotation)))
    if (
        not np.isfinite(relative_matrix).all()
        or position_error > _TRANSLATION_TOLERANCE_M
        or rotation_error > _ROTATION_MATRIX_TOLERANCE
    ):
        raise ValueError(
            f"Camera USD/config pose mismatch at {camera_path}, relative to {mount_path}: "
            f"translation error={position_error:.6g} m, "
            f"rotation matrix error={rotation_error:.6g}. "
            "Set local_translation and local_orientation_rpy_deg to the authored mount-relative "
            "pose in +X-forward/+Y-left/+Z-up camera-link axes; USD cameras use -Z-forward/+Y-up."
        )


__all__ = ["resolve_camera_mount_path", "validate_authored_camera_pose"]
