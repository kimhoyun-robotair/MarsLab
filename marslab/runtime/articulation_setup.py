"""Articulation post-spawn configuration helpers.

Extracted from ``marslab/main.py`` so the joint-name resolution
logic (which is pure Python and therefore offline-testable) lives apart
from the Isaac Sim side effects.

The pure helper :func:`_resolve_joint_position_targets` maps a
``{joint_name: target_rad}`` dictionary to two parallel arrays
``(dof_indices, target_values)`` that the runtime then feeds into
``Articulation.set_joint_positions``.  Unknown joint names are dropped
with a warning rather than raising so a YAML typo on an optional joint
(e.g. an arm pose stow) does not abort the whole simulation.

The thin :func:`apply_initial_joint_positions`,
:func:`pin_articulation_root_pose`, and :func:`zero_steer_joints`
wrappers perform the Isaac-Sim-side calls and are therefore exercised
only inside an Isaac Sim runtime; the unit tests cover the pure helper
exclusively.
"""

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
    """Map ``{joint_name: target_rad}`` to ``(indices, targets)``.

    Args:
        initial_positions: The ``rover.control.initial_joint_positions``
            block from the scenario YAML. A non-dict value (including
            ``None``) is treated as "no targets" and returns empty lists.
        dof_names: Articulation DOF name list as reported by
            ``isaacsim.core.prims.Articulation.dof_names``.

    Returns:
        ``(indices, targets)`` where ``indices[i]`` is the position of
        joint ``targets[i]``'s name in ``dof_names``. Joint names that
        are not present in ``dof_names`` are dropped with a
        ``WARNING``-level log entry (not fatal: the runtime continues
        with the URDF default pose for the missing joint).
    """
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
    """Apply ``rover.control.initial_joint_positions`` to the articulation.

    This is the runtime wrapper around
    :func:`_resolve_joint_position_targets`. An empty / missing /
    malformed ``initial_joint_positions`` block is a no-op so the URDF
    default pose is preserved.

    Args:
        articulation: ``isaacsim.core.prims.Articulation`` instance
            already initialised by ``world.reset()``.
        dof_names: DOF names from ``articulation.dof_names``.
        control_cfg: The ``rover.control`` block from the scenario YAML.
            Must be a dict; the helper only reads
            ``initial_joint_positions``.

    Notes:
        The Isaac Sim ``set_joint_positions`` call is wrapped in a
        broad ``except`` so a transient PhysX hiccup does not abort the
        simulation; the failure is logged at ``WARNING`` level because
        the next physics step retries.
    """
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
    """Pin the PhysX articulation root world pose to ``(spawn_xyz, spawn_rpy)``.

    Without this explicit set, a free articulation (``fix_base=False``)
    starts at the USD-native pose of the deepest articulation-root prim
    (identity at world origin), even when the parent xform was already
    moved by ``apply_spawn_pose`` -- PhysX ignores parent translates for
    the articulation root.  Using the YAML ``spawn_rpy`` here makes the
    rover scenario YAML the single source of truth for both the USD
    parent xform orientation and the PhysX root pose.

    Args:
        articulation: ``isaacsim.core.prims.Articulation`` instance
            already initialised by ``world.reset()``.
        spawn_xyz: World position ``[x, y, z]`` (meters).
        spawn_rpy: World RPY ``[roll, pitch, yaw]`` (radians, ZYX
            intrinsic).  Converted to a scalar-first quaternion before
            being handed to PhysX.
    """
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
    """Zero every steering joint so PD gains land on a sane reference.

    A failure here is logged at ``ERROR`` level but not raised; the
    runtime continues with whatever pose the URDF provided so a
    transient PhysX hiccup does not abort the simulation.
    """
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
