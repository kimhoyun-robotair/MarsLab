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
    """Zero every steering joint so PD gains land on a sane reference."""
    try:
        articulation.set_joint_positions(
            np.zeros(len(steer_indices), dtype=np.float32),
            joint_indices=np.asarray(list(steer_indices)),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("[articulation_setup] Could not init steer joints: %s", exc)


__all__ = [
    "create_rover_articulation",
    "pin_articulation_root_pose",
    "zero_steer_joints",
]
