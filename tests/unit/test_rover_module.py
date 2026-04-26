"""Unit tests for pure-Python helpers in marslab.robots.rover."""

import numpy as np
import pytest

from marslab.robots.rover import resolve_joint_indices, rpy_to_quat


class TestRpyToQuat:
    def test_identity(self) -> None:
        w, x, y, z = rpy_to_quat(0.0, 0.0, 0.0)
        assert (w, x, y, z) == pytest.approx((1.0, 0.0, 0.0, 0.0))

    def test_yaw_only(self) -> None:
        w, x, y, z = rpy_to_quat(0.0, 0.0, np.pi / 2)
        # 90° yaw → [cos(45°), 0, 0, sin(45°)]
        assert w == pytest.approx(np.cos(np.pi / 4), abs=1e-6)
        assert x == pytest.approx(0.0, abs=1e-6)
        assert y == pytest.approx(0.0, abs=1e-6)
        assert z == pytest.approx(np.sin(np.pi / 4), abs=1e-6)

    def test_roll_pi_quaternion(self) -> None:
        """``rpy_to_quat(π, 0, 0)`` -> X-roll quaternion ``±(0, 1, 0, 0)``.

        2026-04-28: the Stage-3 spawn no longer applies the 180° X-roll
        (see configs/robots/rover_m2020.yaml:31-44 and the LOG entry
        for that date), but the math is still load-bearing for any
        scenario that legitimately needs an X-rolled spawn.
        """
        w, x, y, z = rpy_to_quat(np.pi, 0.0, 0.0)
        # ±(0, 1, 0, 0) both acceptable in double-cover; check magnitudes.
        assert abs(w) == pytest.approx(0.0, abs=1e-6)
        assert abs(x) == pytest.approx(1.0, abs=1e-6)
        assert abs(y) == pytest.approx(0.0, abs=1e-6)
        assert abs(z) == pytest.approx(0.0, abs=1e-6)

    def test_output_is_python_float(self) -> None:
        out = rpy_to_quat(0.3, -0.2, 0.5)
        assert all(isinstance(v, float) for v in out)


class TestResolveJointIndices:
    def test_happy_path(self) -> None:
        dof_names = ["LF_DRIVE", "LM_DRIVE", "LR_DRIVE", "RF_DRIVE", "RM_DRIVE", "RR_DRIVE"]
        requested = ["LM_DRIVE", "RR_DRIVE", "LF_DRIVE"]
        assert resolve_joint_indices(dof_names, requested) == [1, 5, 0]

    def test_preserves_request_order(self) -> None:
        dof_names = ["a", "b", "c"]
        assert resolve_joint_indices(dof_names, ["c", "a"]) == [2, 0]

    def test_missing_joint_raises_with_name(self) -> None:
        with pytest.raises(ValueError, match="NOPE"):
            resolve_joint_indices(["a", "b"], ["a", "NOPE"])

    def test_empty_request_returns_empty(self) -> None:
        assert resolve_joint_indices(["a", "b"], []) == []
