"""Apply post-spawn articulation pose and steering initialization.
Joint-target resolution stays pure and separate from Isaac side effects.
Warnings preserve startup when optional joints are absent."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from marslab.quaternion import rpy_to_quat

logger = logging.getLogger(__name__)


def _resolve_joint_position_targets(
    initial_positions: Any,
    dof_names: Sequence[str],
) -> Tuple[List[int], List[float]]:
    """Map ``{joint_name: target_rad}`` to ``(indices, targets)``."""
    indices: List[int] = []
    targets: List[float] = []

    if not isinstance(initial_positions, dict) or not initial_positions:
        return indices, targets

    for joint_name, target_rad in initial_positions.items():
        if joint_name in dof_names:
            indices.append(list(dof_names).index(joint_name))
            targets.append(float(target_rad))
        else:
            logger.warning(
                "[articulation_setup] initial_joint_positions key %r is not in "
                "articulation.dof_names; skipped.",
                joint_name,
            )

    return indices, targets


def apply_initial_joint_positions(
    articulation: Any,
    dof_names: Sequence[str],
    control_cfg: Dict[str, Any],
) -> None:
    """Apply ``rover.control.initial_joint_positions`` to the articulation."""
    initial_positions = control_cfg.get("initial_joint_positions") or {}
    indices, targets = _resolve_joint_position_targets(initial_positions, dof_names)
    if not indices:
        return

    try:
        articulation.set_joint_positions(
            np.asarray(targets, dtype=np.float32),
            joint_indices=np.asarray(indices),
        )
        logger.info(
            "[articulation_setup] Applied initial_joint_positions: %s",
            dict(zip([dof_names[i] for i in indices], targets, strict=True)),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[articulation_setup] Could not apply initial_joint_positions: %s",
            exc,
        )


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
    "_resolve_joint_position_targets",
    "apply_initial_joint_positions",
    "pin_articulation_root_pose",
    "zero_steer_joints",
]
