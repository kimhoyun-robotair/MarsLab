"""Offline unit tests for ``marslab.runtime.articulation_setup``.

The Isaac-Sim-side wrapper :func:`apply_initial_joint_positions` is
exercised only at runtime; these tests cover the pure helper
:func:`_resolve_joint_position_targets` plus the dispatch logic of the
wrapper around it (so the warning behaviour is captured offline).
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import numpy as np

from marslab.runtime.articulation_setup import (
    _resolve_joint_position_targets,
    apply_initial_joint_positions,
    pin_articulation_root_pose,
    zero_steer_joints,
)


def test_resolve_joint_position_targets_happy_path() -> None:
    """All keys map to known DOF names: every entry is forwarded."""
    dof_names = ["joint_a", "joint_b", "joint_c", "joint_d"]
    initial = {"joint_a": 0.1, "joint_c": -0.5, "joint_d": 1.25}

    indices, targets = _resolve_joint_position_targets(initial, dof_names)

    assert indices == [0, 2, 3]
    assert targets == [0.1, -0.5, 1.25]


def test_resolve_joint_position_targets_empty_dict() -> None:
    """Empty initial-positions block yields empty arrays (no-op)."""
    indices, targets = _resolve_joint_position_targets({}, ["a", "b"])

    assert indices == []
    assert targets == []


def test_resolve_joint_position_targets_missing_key_logs_warning(
    caplog,
) -> None:
    """Unknown joint names are dropped with an ERROR log entry."""
    dof_names = ["joint_a", "joint_b"]
    initial = {"joint_a": 0.1, "joint_unknown": 0.4}

    target_logger = logging.getLogger("marslab.runtime.articulation_setup")
    target_logger.propagate = True
    caplog.set_level(logging.ERROR, logger="marslab.runtime.articulation_setup")
    indices, targets = _resolve_joint_position_targets(initial, dof_names)

    assert indices == [0]
    assert targets == [0.1]
    assert any("joint_unknown" in rec.getMessage() for rec in caplog.records)


def test_resolve_joint_position_targets_non_dict_input() -> None:
    """``None`` or list-shaped input is treated as a no-op."""
    indices_none, targets_none = _resolve_joint_position_targets(None, ["a"])
    indices_list, targets_list = _resolve_joint_position_targets([1, 2, 3], ["a"])

    assert (indices_none, targets_none) == ([], [])
    assert (indices_list, targets_list) == ([], [])


def test_apply_initial_joint_positions_invokes_articulation() -> None:
    """The wrapper forwards resolved arrays to ``set_joint_positions``."""
    articulation = MagicMock()
    dof_names = ["joint_a", "joint_b"]
    control_cfg = {"initial_joint_positions": {"joint_b": 0.42}}

    apply_initial_joint_positions(articulation, dof_names, control_cfg)

    articulation.set_joint_positions.assert_called_once()
    call_args = articulation.set_joint_positions.call_args
    targets_arr = call_args.args[0]
    indices_arr = call_args.kwargs["joint_indices"]
    np.testing.assert_array_equal(indices_arr, np.asarray([1]))
    np.testing.assert_allclose(targets_arr, np.asarray([0.42], dtype=np.float32))


def test_apply_initial_joint_positions_empty_is_noop() -> None:
    """Missing block must not call ``set_joint_positions`` at all."""
    articulation = MagicMock()
    apply_initial_joint_positions(articulation, ["a"], {})
    articulation.set_joint_positions.assert_not_called()


def test_apply_initial_joint_positions_runtime_error_logged(
    caplog,
) -> None:
    """A PhysX side failure logs at ERROR but does not raise."""
    articulation = MagicMock()
    articulation.set_joint_positions.side_effect = RuntimeError("physx hiccup")
    control_cfg = {"initial_joint_positions": {"joint_a": 0.1}}

    target_logger = logging.getLogger("marslab.runtime.articulation_setup")
    target_logger.propagate = True
    caplog.set_level(logging.ERROR, logger="marslab.runtime.articulation_setup")
    apply_initial_joint_positions(articulation, ["joint_a"], control_cfg)

    assert any("physx hiccup" in rec.getMessage() for rec in caplog.records)


def test_pin_articulation_root_pose_forwards_xyz_and_quat() -> None:
    """The pose pin packs xyz + quat into the articulation API call."""
    articulation = MagicMock()
    spawn_xyz = (1.0, 2.0, 3.0)
    spawn_rpy = (0.0, 0.0, 0.0)  # identity -> quat (1, 0, 0, 0)

    pin_articulation_root_pose(articulation, spawn_xyz, spawn_rpy)

    articulation.set_world_poses.assert_called_once()
    pos = articulation.set_world_poses.call_args.kwargs["positions"]
    quat = articulation.set_world_poses.call_args.kwargs["orientations"]
    np.testing.assert_allclose(pos, np.asarray([[1.0, 2.0, 3.0]], dtype=np.float32))
    # Identity RPY -> scalar-first quaternion (1, 0, 0, 0)
    np.testing.assert_allclose(quat, np.asarray([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32))


def test_zero_steer_joints_invokes_articulation() -> None:
    """The helper zero-fills a vector of length ``len(steer_indices)``."""
    articulation = MagicMock()
    steer_indices = [3, 7, 11, 15]

    zero_steer_joints(articulation, steer_indices)

    articulation.set_joint_positions.assert_called_once()
    targets_arr = articulation.set_joint_positions.call_args.args[0]
    indices_arr = articulation.set_joint_positions.call_args.kwargs["joint_indices"]
    np.testing.assert_allclose(targets_arr, np.zeros(4, dtype=np.float32))
    np.testing.assert_array_equal(indices_arr, np.asarray(steer_indices))


def test_zero_steer_joints_logs_runtime_error(caplog) -> None:
    """A PhysX side failure logs at ERROR but does not raise."""
    articulation = MagicMock()
    articulation.set_joint_positions.side_effect = RuntimeError("steer init failed")

    target_logger = logging.getLogger("marslab.runtime.articulation_setup")
    target_logger.propagate = True
    caplog.set_level(logging.ERROR, logger="marslab.runtime.articulation_setup")
    zero_steer_joints(articulation, [0, 1, 2])

    assert any("steer init failed" in rec.getMessage() for rec in caplog.records)
