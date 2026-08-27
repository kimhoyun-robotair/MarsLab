"""Deterministic rock prototype selection and scale calculation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from marslab_scene.layers.rocks.orientation import random_stable_orientations


@dataclass(frozen=True, slots=True)
class RockPrototype:
    id: str
    native_diameter_m: float
    stable_poses_wxyz: tuple[tuple[float, float, float, float], ...]


@dataclass(frozen=True, slots=True)
class RockPlacement:
    prototype_indices: NDArray[np.int32]
    scales: NDArray[np.float64]
    orientations_wxyz: NDArray[np.float64]
    clamped: NDArray[np.bool_]


def compute_rock_placement(
    diameters_m: np.ndarray,
    prototypes: tuple[RockPrototype, ...],
    *,
    seed: int,
    top_k: int,
    scale_clamp: tuple[float, float],
) -> RockPlacement:
    """Compute seeded prototype indices, scales, and stable orientations."""
    diameters = np.asarray(diameters_m, dtype=np.float64)
    if diameters.ndim != 1 or not np.isfinite(diameters).all() or np.any(diameters <= 0.0):
        raise ValueError("diameters_m must be a finite positive one-dimensional array")
    if not prototypes:
        raise ValueError("at least one rock prototype is required")
    if top_k < 1:
        raise ValueError("top_k must be positive")
    lower, upper = scale_clamp
    if lower <= 0.0 or lower >= upper:
        raise ValueError("scale_clamp must be positive and increasing")

    sorted_manifest_indices = sorted(
        range(len(prototypes)),
        key=lambda index: prototypes[index].native_diameter_m,
    )
    native_sorted = np.asarray(
        [prototypes[index].native_diameter_m for index in sorted_manifest_indices],
        dtype=np.float64,
    )
    rng = np.random.default_rng(seed)
    prototype_indices = np.empty(len(diameters), dtype=np.int32)
    scales = np.empty(len(diameters), dtype=np.float64)
    clamped = np.empty(len(diameters), dtype=np.bool_)
    candidate_count = min(top_k, len(prototypes))
    for row, diameter in enumerate(diameters):
        nearest_sorted = np.argsort(np.abs(native_sorted - diameter), kind="stable")[
            :candidate_count
        ]
        selected_sorted = int(nearest_sorted[int(rng.integers(0, candidate_count))])
        manifest_index = sorted_manifest_indices[selected_sorted]
        prototype_indices[row] = manifest_index
        raw_scale = float(diameter / prototypes[manifest_index].native_diameter_m)
        scales[row] = np.clip(raw_scale, lower, upper)
        clamped[row] = scales[row] != raw_scale
    orientations = random_stable_orientations(
        tuple(prototype.stable_poses_wxyz for prototype in prototypes),
        prototype_indices,
        rng,
    )
    return RockPlacement(
        prototype_indices=prototype_indices,
        scales=scales,
        orientations_wxyz=orientations,
        clamped=clamped,
    )
