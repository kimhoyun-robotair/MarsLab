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
