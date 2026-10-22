"""SI units, ENU world, FLU body, and WXYZ body-to-world quaternions.

An autopilot owns its control and estimation. The simulator owns the plant.
Future PX4/MPPI adapters use this boundary rather than changing Isaac code.
"""

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class PhysicsState:
    timestamp: float
    position: np.ndarray
    quaternion: np.ndarray
    velocity: np.ndarray
    body_rates: np.ndarray
    specific_force: np.ndarray


@dataclass(frozen=True)
class ServoCommand:
    pwm: tuple[int, ...]
    frame_count: int
    frame_rate: int


@dataclass(frozen=True)
class WrenchCommand:
    force: np.ndarray
    torque: np.ndarray
    powered: bool = True


class FlightBackend(Protocol):
    lockstep: bool

    def poll(self) -> ServoCommand | WrenchCommand | None: ...
    def send_state(self, state: PhysicsState, range_m: float | None = None) -> None: ...
    def reset(self) -> None: ...
    def close(self) -> None: ...
