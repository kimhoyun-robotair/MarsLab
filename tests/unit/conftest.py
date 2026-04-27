"""Shared fixtures for tests/unit/. Hoisted from near-identical per-file copies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Deterministic RNG (shared by every cave_* test module)
# ---------------------------------------------------------------------------


@pytest.fixture()
def rng() -> np.random.Generator:
    """Deterministic numpy Generator seeded with 42."""
    return np.random.default_rng(42)


# ---------------------------------------------------------------------------
# ROS2 message fake dataclasses (shared between odometry_publisher & tf_broadcaster)
#
# FakeHeader carries ``stamp`` so both suites can share it -- the tf suite
# ignores the field, the odom suite relies on it.  Other definitions are
# byte-identical across the source files.
# ---------------------------------------------------------------------------


@dataclass
class FakeStamp:
    sec: int = 0
    nanosec: int = 0


@dataclass
class FakeHeader:
    stamp: FakeStamp = field(default_factory=FakeStamp)
    frame_id: str = ""


@dataclass
class FakeVec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class FakeQuat:
    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class FakeTransform:
    translation: FakeVec3 = field(default_factory=FakeVec3)
    rotation: FakeQuat = field(default_factory=FakeQuat)


@dataclass
class FakeTransformStamped:
    header: FakeHeader = field(default_factory=FakeHeader)
    child_frame_id: str = ""
    transform: FakeTransform = field(default_factory=FakeTransform)


@dataclass
class FakePose:
    position: FakeVec3 = field(default_factory=FakeVec3)
    orientation: FakeQuat = field(default_factory=FakeQuat)


@dataclass
class FakePoseWithCov:
    pose: FakePose = field(default_factory=FakePose)


@dataclass
class FakeTwist:
    linear: FakeVec3 = field(default_factory=FakeVec3)
    angular: FakeVec3 = field(default_factory=FakeVec3)


@dataclass
class FakeTwistWithCov:
    twist: FakeTwist = field(default_factory=FakeTwist)


@dataclass
class FakeOdometry:
    header: FakeHeader = field(default_factory=FakeHeader)
    child_frame_id: str = ""
    pose: FakePoseWithCov = field(default_factory=FakePoseWithCov)
    twist: FakeTwistWithCov = field(default_factory=FakeTwistWithCov)


class FakeTransformBroadcaster:
    """Capture-only tf2 ``TransformBroadcaster`` stand-in."""

    def __init__(self, node: Any) -> None:
        self.node = node
        self.sent: List[FakeTransformStamped] = []

    def sendTransform(self, tf_msg: FakeTransformStamped) -> None:  # noqa: N802
        self.sent.append(tf_msg)


class FakeStaticTransformBroadcaster:
    """Capture-only tf2 ``StaticTransformBroadcaster`` stand-in.

    Accepts either a single message or a list (mirrors the real API).
    """

    def __init__(self, node: Any) -> None:
        self.node = node
        self.sent: List[Any] = []

    def sendTransform(self, msgs: Any) -> None:  # noqa: N802
        if isinstance(msgs, list):
            self.sent.extend(msgs)
        else:
            self.sent.append(msgs)


# ---------------------------------------------------------------------------
# Fake ``usdrt`` for offline OmniGraph builder tests.
#
# ``marslab.ros2_bridge.sensor_graph_builder._build_set_values`` lazily
# imports ``usdrt`` to wrap the articulation root path (canonical
# pattern at ``isaacsim/.../tests/test_pose_tree.py``). ``usdrt`` ships
# with Isaac Sim, not the system Python -- without this fixture every
# offline test that exercises ``_build_set_values`` would fail with
# ``ModuleNotFoundError``. Installed session-wide so tests do not need
# to opt in individually.
#
# The two pure quaternion test suites (``test_quaternion`` and
# ``test_odometry_math``) intentionally cover the same family of math
# helpers from different angles; per the project's flat-architecture
# guidance, duplication below the 3x threshold is acceptable and the
# tests stay separate.
# ---------------------------------------------------------------------------


class _FakeUsdrtSdfPath:
    """Wrapper recording the original USD path string for assertion."""

    def __init__(self, raw: str) -> None:
        self._raw = str(raw)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"FakeUsdrtSdfPath({self._raw!r})"

    def __str__(self) -> str:
        return self._raw

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _FakeUsdrtSdfPath):
            return self._raw == other._raw
        return self._raw == other

    def __hash__(self) -> int:
        return hash(self._raw)


@pytest.fixture(autouse=True, scope="session")
def _install_fake_usdrt() -> None:
    """Register a stub ``usdrt`` module so offline tests can import it."""
    import sys
    import types

    if "usdrt" in sys.modules:
        return
    fake_usdrt = types.ModuleType("usdrt")
    fake_sdf = types.ModuleType("usdrt.Sdf")
    fake_sdf.Path = _FakeUsdrtSdfPath  # type: ignore[attr-defined]
    fake_usdrt.Sdf = fake_sdf  # type: ignore[attr-defined]
    sys.modules["usdrt"] = fake_usdrt
    sys.modules["usdrt.Sdf"] = fake_sdf
