"""Appelbaum–Flood Beer-law DNI, NASA TM-103623 equations 6–7.

The source supports secant air mass up to about 80 degrees zenith. Values
between 80 and 90 degrees retain that approximation for rendering continuity;
they are outside its stated accuracy domain. See assets/atmosphere/README.md.
"""

import math


def compute_direct_intensity(solar_constant: float, tau: float, zenith_angle_rad: float) -> float:
    """Return I0 exp(-tau*m(z)), with m(z)=sec(z) and zero below the horizon."""
    if not math.isfinite(solar_constant) or solar_constant < 0:
        raise ValueError("solar_constant must be finite and >= 0")
    if not math.isfinite(tau) or tau < 0:
        raise ValueError("tau must be finite and >= 0")
    if not math.isfinite(zenith_angle_rad) or not 0 <= zenith_angle_rad <= math.pi:
        raise ValueError("zenith_angle_rad must be in [0, pi]")
    if zenith_angle_rad >= math.pi / 2:
        return 0.0
    return solar_constant * math.exp(-tau / math.cos(zenith_angle_rad))
