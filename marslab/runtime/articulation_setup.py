"""Apply post-spawn articulation root pose and steering initialization."""

from __future__ import annotations

import logging
from typing import Any, Sequence

import numpy as np

from marslab.quaternion import rpy_to_quat

logger = logging.getLogger(__name__)


def create_rover_articulation(prim_path: str) -> Any:
    """Keep unrelated stage deletions from invalidating the rover physics view."""
    from isaacsim.core.prims import Articulation

    class RoverArticulation(Articulation):
        def _on_prim_deletion(self, deleted_prim_path: str) -> None:
            roots = self.prim_paths
            ancestor_prefix = deleted_prim_path.rstrip("/") + "/"
            if not any(
                root == deleted_prim_path or root.startswith(ancestor_prefix) for root in roots
            ):
                logger.debug(
                    "Ignoring prim deletion outside rover articulation roots: deleted=%s roots=%s",
                    deleted_prim_path,
                    roots,
                )
                return
            logger.info(
                "Invalidating rover articulation after prim deletion: %s", deleted_prim_path
            )
            super()._on_prim_deletion(deleted_prim_path)

    return RoverArticulation(prim_paths_expr=prim_path)


def pin_articulation_root_pose(
    articulation: Any,
    spawn_xyz: Sequence[float],
    spawn_rpy: Sequence[float],
) -> None:
    """Pin the PhysX articulation root world pose to ``(spawn_xyz, spawn_rpy)``."""
    qw, qx, qy, qz = rpy_to_quat(
        float(spawn_rpy[0]),
        float(spawn_rpy[1]),
        float(spawn_rpy[2]),
    )
    articulation.set_world_poses(
        positions=np.asarray([list(spawn_xyz)], dtype=np.float32),
        orientations=np.asarray([[qw, qx, qy, qz]], dtype=np.float32),
    )


def zero_steer_joints(articulation: Any, steer_indices: Sequence[int]) -> None:
    """Zero steering while preserving all other joints' authored position targets.

    Isaac's indexed ``set_joint_positions`` also replaces the full target vector
    with measured positions. Restore the other targets so an arm or mast does
    not adopt its gravity-deflected pose as its new commanded reference.
    """
    steering = np.asarray(list(steer_indices), dtype=np.int32)
    if steering.size == 0:
        return
    actions = articulation.get_applied_actions(clone=True)
    if actions is None or actions.joint_positions is None:
        raise RuntimeError("Steering initialization requires live joint position targets")
    targets = np.asarray(actions.joint_positions).copy()
    if targets.ndim not in (1, 2) or not np.isfinite(targets).all():
        raise RuntimeError("Steering initialization received invalid joint position targets")
    if np.any(steering < 0) or np.any(steering >= targets.shape[-1]):
        raise ValueError("Steering joint index is outside the articulation target vector")
    other = np.setdiff1d(np.arange(targets.shape[-1], dtype=np.int32), steering)
    zeros = np.zeros(len(steering), dtype=np.float32)
    articulation.set_joint_positions(zeros, joint_indices=steering)
    articulation.set_joint_position_targets(zeros, joint_indices=steering)
    if other.size:
        articulation.set_joint_position_targets(targets[..., other], joint_indices=other)

    expected = targets.copy()
    expected[..., steering] = 0.0
    applied = articulation.get_applied_actions(clone=True)
    if applied is None or not np.array_equal(applied.joint_positions, expected):
        raise RuntimeError("Steering initialization failed to preserve joint position targets")


__all__ = [
    "create_rover_articulation",
    "pin_articulation_root_pose",
    "zero_steer_joints",
]
