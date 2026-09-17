"""Tau-only NIR COMIMART reduction at the declared Table 3 reference conditions.

Vicente-Retortillo et al. (2015), doi:10.1051/swsc/2015035, equations 10–23.
See assets/atmosphere/README.md for the spectral scope and reference data.
"""

import math

REFERENCE_COS_ZENITH = 0.7
REFERENCE_SINGLE_SCATTERING_ALBEDO = 0.97
REFERENCE_ASYMMETRY_FACTOR = 0.70
REFERENCE_SURFACE_ALBEDO = 0.25


def compute_reference_surface_transmittance(tau: float) -> float:
    """Return T/E for the fixed, dust-only NIR delta-Eddington reference."""
    if not math.isfinite(tau) or tau < 0:
        raise ValueError("tau must be finite and >= 0")
    if tau == 0:
        return 1.0

    mu = REFERENCE_COS_ZENITH
    albedo = REFERENCE_SURFACE_ALBEDO
    omega = REFERENCE_SINGLE_SCATTERING_ALBEDO
    asymmetry = REFERENCE_ASYMMETRY_FACTOR
    delta_scale = 1.0 - omega * asymmetry**2
    optical_depth = tau * delta_scale
    omega = omega * (1.0 - asymmetry**2) / delta_scale
    asymmetry = asymmetry / (1.0 + asymmetry)

    k = math.sqrt(3.0 * (1.0 - omega) * (1.0 - asymmetry * omega))
    p = (2.0 / 3.0) * math.sqrt(3.0 * (1.0 - omega) / (1.0 - asymmetry * omega))
    resonance = 1.0 - mu**2 * k**2
    a = 0.75 * mu * omega * (1.0 + asymmetry * (1.0 - omega)) / resonance
    b = 0.5 * mu * omega * (1.0 / mu + 3.0 * mu * asymmetry * (1.0 - omega)) / resonance
    c3 = albedo + (1.0 - albedo) * a - (1.0 + albedo) * b
    c4 = 1.0 - albedo + p * (1.0 + albedo)
    c5 = 1.0 - albedo - p * (1.0 + albedo)

    # Divide equations 18–19 by exp(k*tau') to avoid positive exponentials.
    attenuation = math.exp(-k * optical_depth)
    adjusted_beam = math.exp(-optical_depth / mu)
    denominator = (1.0 + p) * c4 - (1.0 - p) * c5 * attenuation**2
    c1 = ((a + b) * c4 - (1.0 - p) * c3 * adjusted_beam * attenuation) / denominator
    c2_exp = ((1.0 + p) * c3 * adjusted_beam - (a + b) * c5 * attenuation) / denominator
    return c1 * attenuation * (1.0 + p) + c2_exp * (1.0 - p) - (a + b - 1.0) * adjusted_beam


def compute_diffuse_fraction_1d_approx(tau: float, zenith_rad: float | None = None) -> float:
    """Return D/T at fixed mu=0.7; the legacy zenith argument is not a model input."""
    total = compute_reference_surface_transmittance(tau)
    if total == 0:
        return 1.0
    # Equation 23 uses the original optical depth, before delta scaling.
    beam = math.exp(-tau / REFERENCE_COS_ZENITH)
    return min(1.0, max(0.0, 1.0 - beam / total))
