"""Unit tests for pure-Python helpers in marslab.robots.rover."""

from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from marslab.robots import rover as rover_module
from marslab.robots.rover import SpawnedRover, resolve_joint_indices, rpy_to_quat


class TestRpyToQuat:
    def test_identity(self) -> None:
        w, x, y, z = rpy_to_quat(0.0, 0.0, 0.0)
        assert (w, x, y, z) == pytest.approx((1.0, 0.0, 0.0, 0.0))

    def test_yaw_only(self) -> None:
        w, x, y, z = rpy_to_quat(0.0, 0.0, np.pi / 2)
        # 90 deg yaw -> [cos(45 deg), 0, 0, sin(45 deg)]
        assert w == pytest.approx(np.cos(np.pi / 4), abs=1e-6)
        assert x == pytest.approx(0.0, abs=1e-6)
        assert y == pytest.approx(0.0, abs=1e-6)
        assert z == pytest.approx(np.sin(np.pi / 4), abs=1e-6)

    def test_roll_pi_quaternion(self) -> None:
        """``rpy_to_quat(pi, 0, 0)`` -> X-roll quaternion ``+/-(0, 1, 0, 0)``.

        The Stage-3 spawn no longer applies the 180-degree X-roll (see
        ``configs/robots/rover_m2020.yaml`` for the current spawn pose),
        but the math is still load-bearing for any scenario that
        legitimately needs an X-rolled spawn.
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


class TestSpawnRoverOrchestrator:
    """Verify ``spawn_rover`` delegates to its three helpers in order.

    The helpers each touch USD / Isaac Sim and are exercised separately
    in their own focused tests (``test_rover_physics_inject.py`` for the
    articulation physics path, plus the integration tests for the USD
    spawn).  Here we mock all three helpers so the orchestrator's
    contract -- argument routing and return value -- is decoupled from
    USD runtime concerns.
    """

    def _make_rover_cfg(self) -> dict:
        return {
            "prim_path": "/World/Rover",
            "spawn": {"orientation_rpy": [3.14159, 0.0, 0.5]},
            "com_offset": [0.1, -0.2, 0.3],
            "angular_damping": 4.0,
            "linear_damping": 2.0,
            "chassis": {"placeholder": True},
            "wheels": {"placeholder": True},
            "suspension": {"placeholder": True},
            "control": {"drive_joint_names": ["LF_DRIVE", "RF_DRIVE"]},
        }

    def test_returns_spawned_rover_with_discovered_paths(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Orchestrator returns a ``SpawnedRover`` with helper-supplied paths."""
        rb_path = "/World/Rover/Body_Chassis/Body_Chassis"

        monkeypatch.setattr(rover_module, "_spawn_rover_usd", lambda *_a, **_k: rb_path)
        monkeypatch.setattr(rover_module, "_apply_rover_mass", lambda *_a, **_k: None)
        monkeypatch.setattr(
            rover_module, "_apply_rover_articulation_physics", lambda *_a, **_k: None
        )

        result = rover_module.spawn_rover(
            stage=MagicMock(),
            rover_cfg=self._make_rover_cfg(),
            usd_abs="/tmp/fake.usd",
            spawn_xyz=(1.0, 2.0, 3.0),
        )
        assert isinstance(result, SpawnedRover)
        assert result.prim_path == "/World/Rover"
        assert result.chassis_path == "/World/Rover/Body_Chassis"
        assert result.rigid_body_path == rb_path

    def test_helpers_called_with_expected_arguments(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Each helper receives the orchestrator-resolved arguments verbatim."""
        rb_path = "/World/Rover/Body_Chassis/Body_Chassis"
        stage = MagicMock()
        rover_cfg = self._make_rover_cfg()

        spawn_usd = MagicMock(return_value=rb_path)
        apply_mass = MagicMock()
        apply_articulation = MagicMock()

        monkeypatch.setattr(rover_module, "_spawn_rover_usd", spawn_usd)
        monkeypatch.setattr(rover_module, "_apply_rover_mass", apply_mass)
        monkeypatch.setattr(rover_module, "_apply_rover_articulation_physics", apply_articulation)

        rover_module.spawn_rover(
            stage=stage,
            rover_cfg=rover_cfg,
            usd_abs="/tmp/fake.usd",
            spawn_xyz=(1.0, 2.0, 3.0),
        )

        # Helper 1: USD spawn -- prim_path resolved from cfg, rpy taken
        # from the ``spawn.orientation_rpy`` block (preferred over the
        # legacy top-level ``spawn_orientation_rpy``).
        spawn_usd.assert_called_once()
        args, _ = spawn_usd.call_args
        assert args[0] is stage
        assert args[1] == "/World/Rover"
        assert args[2] == "/tmp/fake.usd"
        assert args[3] == (1.0, 2.0, 3.0)
        assert tuple(args[4]) == (3.14159, 0.0, 0.5)

        # Helper 2: mass overrides -- com_offset coerced to tuple of
        # floats, damping values coerced to float.
        apply_mass.assert_called_once()
        args, _ = apply_mass.call_args
        assert args[0] is stage
        assert args[1] == rb_path
        assert args[2] == (0.1, -0.2, 0.3)
        assert args[3] == pytest.approx(4.0)
        assert args[4] == pytest.approx(2.0)

        # Helper 3: articulation physics -- gets the rigid_body_path and
        # the full rover_cfg so it can validate chassis/wheels/suspension.
        apply_articulation.assert_called_once_with(stage, rb_path, rover_cfg)

    def test_legacy_orientation_key_falls_back_when_spawn_block_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``spawn_orientation_rpy`` (top-level) is consulted only as fallback."""
        rb_path = "/World/Rover/Body_Chassis/Body_Chassis"
        spawn_usd = MagicMock(return_value=rb_path)

        monkeypatch.setattr(rover_module, "_spawn_rover_usd", spawn_usd)
        monkeypatch.setattr(rover_module, "_apply_rover_mass", lambda *_a, **_k: None)
        monkeypatch.setattr(
            rover_module, "_apply_rover_articulation_physics", lambda *_a, **_k: None
        )

        cfg: dict = {
            "prim_path": "/World/Rover",
            "spawn_orientation_rpy": [0.1, 0.2, 0.3],
        }
        rover_module.spawn_rover(
            stage=MagicMock(), rover_cfg=cfg, usd_abs="/tmp/x.usd", spawn_xyz=(0, 0, 0)
        )
        args, _ = spawn_usd.call_args
        assert tuple(args[4]) == (0.1, 0.2, 0.3)

    def test_missing_com_offset_passes_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``com_offset`` missing from cfg routes ``None`` to the mass helper."""
        apply_mass = MagicMock()
        monkeypatch.setattr(
            rover_module,
            "_spawn_rover_usd",
            lambda *_a, **_k: "/World/Rover/Body_Chassis/Body_Chassis",
        )
        monkeypatch.setattr(rover_module, "_apply_rover_mass", apply_mass)
        monkeypatch.setattr(
            rover_module, "_apply_rover_articulation_physics", lambda *_a, **_k: None
        )

        cfg: dict[str, Any] = {"prim_path": "/World/Rover"}
        rover_module.spawn_rover(
            stage=MagicMock(), rover_cfg=cfg, usd_abs="/tmp/x.usd", spawn_xyz=(0, 0, 0)
        )
        args, _ = apply_mass.call_args
        assert args[2] is None
        assert args[3] == 0.0
        assert args[4] == 0.0

    def test_helpers_called_in_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """USD spawn -> mass -> articulation physics, in that order."""
        order: list[str] = []
        monkeypatch.setattr(
            rover_module,
            "_spawn_rover_usd",
            lambda *_a, **_k: (order.append("usd"), "/rb")[1],
        )
        monkeypatch.setattr(
            rover_module, "_apply_rover_mass", lambda *_a, **_k: order.append("mass")
        )
        monkeypatch.setattr(
            rover_module,
            "_apply_rover_articulation_physics",
            lambda *_a, **_k: order.append("art"),
        )

        rover_module.spawn_rover(
            stage=MagicMock(),
            rover_cfg=self._make_rover_cfg(),
            usd_abs="/tmp/x.usd",
            spawn_xyz=(0, 0, 0),
        )
        assert order == ["usd", "mass", "art"]
