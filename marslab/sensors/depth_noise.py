"""Apply optional seeded metric noise once to each acquired depth frame."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from marslab.config.schema.rover_sensors import DepthSensorConfig


@dataclass(frozen=True, slots=True)
class DepthSample:
    stamp_ns: int
    depth_m: npt.NDArray[np.float32]


class DepthNoise:
    """Cache one noisy sample so readers and ROS points use identical depths."""

    def __init__(self, config: DepthSensorConfig, seed: int | None) -> None:
        self.config = config
        self.seed = seed
        self._rng = np.random.default_rng(seed)
        self._sample: DepthSample | None = None

    def reset(self) -> None:
        self._rng = np.random.default_rng(self.seed)
        self._sample = None

    def apply(self, depth: npt.NDArray[np.float32], stamp_ns: int) -> DepthSample:
        if self._sample is not None and stamp_ns == self._sample.stamp_ns:
            return self._sample
        if self._sample is not None and stamp_ns < self._sample.stamp_ns:
            raise RuntimeError("Depth acquisition time moved backward without an episode reset")
        config = self.config
        valid = (
            np.isfinite(depth)
            & (depth > 0.0)
            & (depth >= config.min_distance_m)
            & (depth <= config.max_distance_m)
        )
        rng = (
            self._rng
            if self.seed is None
            else np.random.default_rng(np.random.SeedSequence([self.seed, stamp_ns]))
        )
        noisy = depth.copy()
        noise = rng.normal(config.noise_mean, config.noise_sigma, depth.shape).astype(np.float32)
        noisy[valid] += noise[valid]
        valid &= (noisy > 0.0) & (noisy >= config.min_distance_m) & (noisy <= config.max_distance_m)
        noisy[~valid] = np.nan
        self._sample = DepthSample(stamp_ns, noisy)
        return self._sample
