"""Broadband DNI using NASA TM-102299's plane-parallel Beer approximation."""

import math


def compute_direct_intensity(solar_constant: float, tau: float, zenith_angle_rad: float) -> float:
    """Return I0 exp(-tau/cos(z)); the secant approximation degrades above z=80°."""
    if not math.isfinite(solar_constant) or solar_constant < 0:
        raise ValueError("solar_constant must be finite and >= 0")
    if not math.isfinite(tau) or tau < 0:
        raise ValueError("tau must be finite and >= 0")
    if not math.isfinite(zenith_angle_rad) or not 0 <= zenith_angle_rad <= math.pi:
        raise ValueError("zenith_angle_rad must be in [0, pi]")
    if zenith_angle_rad >= math.pi / 2:
        return 0.0
    return solar_constant * math.exp(-tau / math.cos(zenith_angle_rad))
