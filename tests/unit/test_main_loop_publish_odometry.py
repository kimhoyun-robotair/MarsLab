"""B-2 refactor (2026-04-28) cover for ``main_loop._publish_odometry``.

The function is now a thin adapter around
:func:`marslab.ros2_bridge.odometry_publisher.publish_odometry`.
Tests pin:

1. ``odom_ctx is None`` -> early return, no publisher call.
2. Articulation pose + velocity reach the publisher with the right
   ``cur_pos_world`` / ``cur_quat_world`` / ``linear_vel_world`` /
   ``angular_vel_world``.
3. Velocity-fetch failure is swallowed (``velocity_query_failed`` log)
   and the publisher still receives a zero twist.
4. Publisher exception is swallowed (``odom_publish_failed`` log) so
   the main loop keeps running.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from marslab.runtime import main_loop as ml


def _make_ctx(*, odom_ctx: Any, articulation: Any) -> ml.LoopContext:
    """Build a barely-populated LoopContext for the adapter tests."""

    def _ackermann(*_args, **_kwargs):  # pragma: no cover - not invoked
        return np.zeros(4), np.zeros(6)

    return ml.LoopContext(
        simulation_app=object(),
        world=object(),
        stage=object(),
        articulation=articulation,
        imu=object(),
        drive_indices=[0],
        steer_indices=[1],
        wheelbase=1.0,
        track_steer=1.0,
        track_middle=1.0,
        wheel_radius=0.1,
        v_max=1.0,
        w_max=1.0,
        physics_dt=0.01,
        negate_steer=False,
        debug_logging=False,
        max_wheel_accel_rate=0.5,
        decel_multiplier=1.0,
        max_steer_angle=0.5,
        steer_ramp_rate=2.0,
        control=ml.ControlState(
            current_drive_targets=np.zeros(1, dtype=np.float32),
            current_steer_targets=np.zeros(1, dtype=np.float32),
        ),
        atmosphere=ml.AtmosphereLoopState(
            atmosphere_dict={"tau": 0.3},
            sol_duration=88642.0,
            solar_constant=589.0,
        ),
        odom_ctx=odom_ctx,
        render_config=object(),
        ackermann_fn=_ackermann,
    )


_DEFAULT_POS = np.array([1.0, 2.0, 3.0], dtype=np.float32)
_DEFAULT_QUAT = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
_DEFAULT_LIN = np.array([0.5, 0.0, 0.0], dtype=np.float32)
_DEFAULT_ANG = np.array([0.0, 0.0, 0.1], dtype=np.float32)


def _make_articulation(
    *,
    pos: np.ndarray = _DEFAULT_POS,
    quat: np.ndarray = _DEFAULT_QUAT,
    lin: np.ndarray | None = _DEFAULT_LIN,
    ang: np.ndarray | None = _DEFAULT_ANG,
    vel_raises: bool = False,
) -> MagicMock:
    art = MagicMock()
    # 2-D shape so the [_rp[0]] branch executes (matches Isaac Sim's
    # Articulation.get_world_poses output shape).
    art.get_world_poses.return_value = (pos[None, :], quat[None, :])
    if vel_raises:
        art.get_linear_velocities.side_effect = RuntimeError("velocity stub raise")
        art.get_angular_velocities.side_effect = RuntimeError("velocity stub raise")
    else:
        art.get_linear_velocities.return_value = None if lin is None else lin[None, :]
        art.get_angular_velocities.return_value = None if ang is None else ang[None, :]
    return art


class TestPublishOdometryAdapter:
    def test_skips_when_odom_ctx_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called = MagicMock()
        monkeypatch.setattr(
            "marslab.ros2_bridge.odometry_publisher.publish_odometry",
            called,
        )
        ctx = _make_ctx(odom_ctx=None, articulation=MagicMock())
        ml._publish_odometry(ctx, step_count=0)
        called.assert_not_called()

    def test_calls_publisher_with_world_pose_and_twist(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = MagicMock()
        monkeypatch.setattr(
            "marslab.ros2_bridge.odometry_publisher.publish_odometry",
            called,
        )
        odom_ctx = MagicMock()
        odom_ctx.publisher = MagicMock()  # truthy so the guard in run_main_loop matches
        articulation = _make_articulation()
        ctx = _make_ctx(odom_ctx=odom_ctx, articulation=articulation)

        ml._publish_odometry(ctx, step_count=0)

        assert called.call_count == 1
        kwargs = called.call_args.kwargs
        np.testing.assert_allclose(kwargs["cur_pos_world"], [1.0, 2.0, 3.0])
        np.testing.assert_allclose(kwargs["cur_quat_world"], [1.0, 0.0, 0.0, 0.0])
        np.testing.assert_allclose(kwargs["linear_vel_world"], [0.5, 0.0, 0.0])
        np.testing.assert_allclose(kwargs["angular_vel_world"], [0.0, 0.0, 0.1])

    def test_swallows_velocity_query_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        called = MagicMock()
        monkeypatch.setattr(
            "marslab.ros2_bridge.odometry_publisher.publish_odometry",
            called,
        )
        articulation = _make_articulation(vel_raises=True)
        odom_ctx = MagicMock()
        ctx = _make_ctx(odom_ctx=odom_ctx, articulation=articulation)

        with caplog.at_level("ERROR", logger="marslab.runtime.main_loop"):
            ml._publish_odometry(ctx, step_count=0)

        # Publisher still called, twist defaulted to zero.
        assert called.call_count == 1
        kwargs = called.call_args.kwargs
        np.testing.assert_allclose(kwargs["linear_vel_world"], np.zeros(3))
        np.testing.assert_allclose(kwargs["angular_vel_world"], np.zeros(3))
        assert any("velocity_query_failed" in rec.getMessage() for rec in caplog.records)

    def test_swallows_publisher_failure_into_log_once(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        def _raises(*_args, **_kwargs):
            raise RuntimeError("rclpy fault stub")

        monkeypatch.setattr(
            "marslab.ros2_bridge.odometry_publisher.publish_odometry",
            _raises,
        )
        odom_ctx = MagicMock()
        articulation = _make_articulation()
        ctx = _make_ctx(odom_ctx=odom_ctx, articulation=articulation)

        with caplog.at_level("ERROR", logger="marslab.runtime.main_loop"):
            ml._publish_odometry(ctx, step_count=0)

        # The "odom_publish_failed" log line is the user-visible spelling
        # the original Isaac Sim run reported.  Preserve it verbatim.
        assert any("odom_publish_failed" in rec.getMessage() for rec in caplog.records)

    def test_skips_when_articulation_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called = MagicMock()
        monkeypatch.setattr(
            "marslab.ros2_bridge.odometry_publisher.publish_odometry",
            called,
        )
        odom_ctx = MagicMock()
        articulation = MagicMock()
        articulation.get_world_poses.return_value = None
        ctx = _make_ctx(odom_ctx=odom_ctx, articulation=articulation)
        ml._publish_odometry(ctx, step_count=0)
        called.assert_not_called()
