"""Dust optical depth (tau) temporal profiles for dynamic atmosphere.

Provides functions to compute tau as a function of time-of-sol fraction,
modelling different atmospheric dust scenarios on Mars.

Scientific basis:
    - tau (dust optical depth) is the primary atmospheric parameter
      governing visibility and irradiance on Mars.
    - Observed range: tau ~0.2 (clear, InSight/Curiosity) to 6+
      (2018 global dust storm).
    - Ref: Lemmon et al. (2015) Icarus, Smith et al. (2019) JGR Planets.
    - tau feeds into Beer's Law (direct irradiance) and COMIMART
      (diffuse fraction), both already implemented in this package.

Three profile types:
    - constant: fixed tau throughout the sol (clear day baseline).
    - ramp: linear increase from start_tau to end_tau (dust storm onset).
    - sine: periodic oscillation around a base tau (diurnal dust cycle).
"""

import math


def compute_tau_constant(base_tau: float, t: float) -> float:
    """Return a constant tau regardless of time.

    Args:
        base_tau: Fixed optical depth value (>= 0).
        t: Time-of-sol fraction [0, 1] (unused, for API consistency).

    Returns:
        The constant tau value.

    Raises:
        ValueError: If base_tau is negative or t is outside [0, 1].
    """
    _validate_t(t)
    if base_tau < 0:
        raise ValueError(f"base_tau must be >= 0, got {base_tau}")
    return base_tau


def compute_tau_ramp(start_tau: float, end_tau: float, t: float) -> float:
    """Return tau linearly interpolated between start and end values.

    Models a dust storm onset (start < end) or dissipation (start > end).

    Args:
        start_tau: Tau at t=0 (>= 0).
        end_tau: Tau at t=1 (>= 0).
        t: Time-of-sol fraction [0, 1].

    Returns:
        Interpolated tau at time t.

    Raises:
        ValueError: If either tau is negative or t is outside [0, 1].
    """
    _validate_t(t)
    if start_tau < 0:
        raise ValueError(f"start_tau must be >= 0, got {start_tau}")
    if end_tau < 0:
        raise ValueError(f"end_tau must be >= 0, got {end_tau}")
    return start_tau + (end_tau - start_tau) * t


def compute_tau_sine(
    base_tau: float,
    amplitude: float,
    period_fraction: float,
    t: float,
) -> float:
    """Return tau with sinusoidal oscillation around a base value.

    ``tau(t) = base_tau + amplitude * sin(2 * pi * t / period_fraction)``

    The result is clamped to a minimum of 0.0 (negative tau is unphysical).

    Args:
        base_tau: Mean optical depth (>= 0).
        amplitude: Oscillation amplitude (>= 0). Must satisfy
            amplitude <= base_tau to avoid negative excursions (clamped).
        period_fraction: Period as fraction of sol (e.g. 1.0 = one full
            cycle per sol, 0.5 = two cycles per sol). Must be > 0.
        t: Time-of-sol fraction [0, 1].

    Returns:
        Tau at time t (>= 0).

    Raises:
        ValueError: If base_tau or amplitude is negative,
            period_fraction <= 0, or t is outside [0, 1].
    """
    _validate_t(t)
    if base_tau < 0:
        raise ValueError(f"base_tau must be >= 0, got {base_tau}")
    if amplitude < 0:
        raise ValueError(f"amplitude must be >= 0, got {amplitude}")
    if period_fraction <= 0:
        raise ValueError(f"period_fraction must be > 0, got {period_fraction}")

    tau = base_tau + amplitude * math.sin(2 * math.pi * t / period_fraction)
    return max(0.0, tau)


def compute_tau(profile: str, t: float, **kwargs: float) -> float:
    """Dispatch to the appropriate tau profile function.

    Required kwargs per profile (no defaults are filled in here -- the
    canonical caller pattern is to pass the schema's ``model_dump()``,
    which already guarantees every key is present):

    * ``constant``: ``base_tau``.
    * ``ramp``:     ``start_tau``, ``end_tau``.
    * ``sine``:     ``base_tau``, ``amplitude``, ``period_fraction``.

    Missing keys raise :class:`TypeError` so a schema/profile mismatch
    fails loudly instead of silently substituting a default that is not
    declared in the YAML.

    Args:
        profile: One of "constant", "ramp", "sine".
        t: Time-of-sol fraction [0, 1].
        **kwargs: Profile-specific parameters forwarded to the chosen
            function. Must contain every required key for that profile.

    Returns:
        Tau at time t.

    Raises:
        ValueError: If profile is unknown.
        TypeError: If a required kwarg for the chosen profile is missing.
    """
    if profile == "constant":
        return compute_tau_constant(base_tau=kwargs["base_tau"], t=t)
    elif profile == "ramp":
        return compute_tau_ramp(
            start_tau=kwargs["start_tau"],
            end_tau=kwargs["end_tau"],
            t=t,
        )
    elif profile == "sine":
        return compute_tau_sine(
            base_tau=kwargs["base_tau"],
            amplitude=kwargs["amplitude"],
            period_fraction=kwargs["period_fraction"],
            t=t,
        )
    else:
        raise ValueError(f"Unknown tau profile: '{profile}'. Choose from: constant, ramp, sine")


def _validate_t(t: float) -> None:
    """Validate that t is in [0, 1]."""
    if not 0.0 <= t <= 1.0:
        raise ValueError(f"t must be in [0, 1], got {t}")
