"""Stable rock orientation math."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray


def random_stable_orientations(
    stable_pose_candidates_wxyz: tuple[tuple[tuple[float, float, float, float], ...], ...],
    prototype_indices: NDArray[np.int32],
    rng: np.random.Generator,
) -> NDArray[np.float64]:
    """Apply legacy-compatible uniform Z yaw to manifest stable poses."""
    orientations = np.empty((len(prototype_indices), 4), dtype=np.float64)
    for index, prototype_index in enumerate(prototype_indices):
        candidates = stable_pose_candidates_wxyz[int(prototype_index)]
        if not candidates:
            raise ValueError("rock prototype must have at least one stable pose")
        stable_pose = candidates[int(rng.choice(len(candidates)))]
        theta = float(rng.uniform(0.0, 2.0 * math.pi))
        yaw = (math.cos(theta / 2.0), 0.0, 0.0, math.sin(theta / 2.0))
        orientation = np.asarray(
            _quaternion_multiply(yaw, stable_pose),
            dtype=np.float64,
        )
        orientations[index] = orientation / np.linalg.norm(orientation)
    return orientations


def quaternions_equivalent(
    first: np.ndarray,
    second: np.ndarray,
    *,
    atol: float,
) -> bool:
    """Compare unit quaternions while treating q and -q as equivalent."""
    left = np.asarray(first, dtype=np.float64)
    right = np.asarray(second, dtype=np.float64)
    return bool(
        np.allclose(left, right, atol=atol, rtol=0.0)
        or np.allclose(left, -right, atol=atol, rtol=0.0)
    )


def _quaternion_multiply(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    wa, xa, ya, za = first
    wb, xb, yb, zb = second
    return (
        wa * wb - xa * xb - ya * yb - za * zb,
        wa * xb + xa * wb + ya * zb - za * yb,
        wa * yb - xa * zb + ya * wb + za * xb,
        wa * zb + xa * yb - ya * xb + za * wb,
    )
