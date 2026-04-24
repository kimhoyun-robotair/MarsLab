"""Numerical sanity checks for the new spherical sun-position path."""

import math
import sys

sys.path.insert(0, "/home/hoyunkim/MarsLab")

from marslab.environment.sun_position import (  # noqa: E402
    MARS_OBLIQUITY_DEG,
    compute_sol_sun_position,
    solar_declination_deg,
)


def case(label: str, **kwargs) -> None:
    pos = compute_sol_sun_position(**kwargs)
    print(
        f"{label:60s} az={pos.azimuth_deg:7.2f}  el={pos.elevation_deg:6.2f}  "
        f"zenith_rad={pos.zenith_angle_rad:.4f}"
    )


print(f"MARS_OBLIQUITY_DEG = {MARS_OBLIQUITY_DEG}")
print(f"solar_declination_deg(0)   = {solar_declination_deg(0.0):.4f}")
print(f"solar_declination_deg(90)  = {solar_declination_deg(90.0):.4f}")
print(f"solar_declination_deg(180) = {solar_declination_deg(180.0):.4f}")
print(f"solar_declination_deg(270) = {solar_declination_deg(270.0):.4f}")
print()

# Jezero Ls=0 (equinox), transit: expected el ≈ 90 - 18.44 = 71.56
case("Jezero Ls=0 transit (expect el≈71.56, az≈180)", time_of_sol_fraction=0.5)

# Jezero Ls=90 (N summer solstice): declination = +25.19
# transit el = 90 - |phi - delta| = 90 - (18.44 - 25.19)  = 90 - 6.75 = 83.25 (sun north)
# But azimuth should flip to 0/360 (sun north of observer at transit).
case("Jezero Ls=90 transit (expect el≈83.25, az≈0/360)", time_of_sol_fraction=0.5, ls_deg=90.0)

# Jezero Ls=270 (N winter solstice): delta = -25.19. el_transit = 90-(18.44+25.19)=46.37. az=180.
case(
    "Jezero Ls=270 transit (expect el≈46.37, az≈180)",
    time_of_sol_fraction=0.5,
    ls_deg=270.0,
)

# Equator Ls=0, transit: el=90, azimuth undefined (sun overhead) — atan2(0,0) → 0.
case("Equator Ls=0 transit (expect el≈90)", time_of_sol_fraction=0.5, latitude_deg=0.0)

# Ls=0 sunrise t=0.25: hour angle = -pi/2 = -90°. At equinox (delta=0) on equator,
# el = 0, az = 90 (due east). With latitude, still el=0 at t=0.25/0.75 (geometric).
case(
    "Equator Ls=0 t=0.25 (expect el≈0, az≈90 E)",
    time_of_sol_fraction=0.25,
    latitude_deg=0.0,
)
case(
    "Equator Ls=0 t=0.75 (expect el≈0, az≈270 W)",
    time_of_sol_fraction=0.75,
    latitude_deg=0.0,
)

# Jezero Ls=0 nighttime: t=0 (midnight). sin(el) = sin(phi)*0 + cos(phi)*1*cos(pi) = -cos(phi).
# phi=18.44 → sin(el)=-0.949 → el=-71.56 → clamped to 0.
case("Jezero Ls=0 midnight t=0 (expect el=0 clamped)", time_of_sol_fraction=0.0)
case("Jezero Ls=0 midnight t=1 (expect el=0 clamped)", time_of_sol_fraction=1.0)

# Symmetry: el(0.5 - x) == el(0.5 + x) at equinox.
for dx in (0.05, 0.1, 0.2):
    p_minus = compute_sol_sun_position(0.5 - dx)
    p_plus = compute_sol_sun_position(0.5 + dx)
    print(
        f"symmetry dx={dx:4.2f}  el-={p_minus.elevation_deg:6.3f} el+={p_plus.elevation_deg:6.3f} "
        f"az-={p_minus.azimuth_deg:7.2f} az+={p_plus.azimuth_deg:7.2f}  "
        f"(az_sum should be 360: {p_minus.azimuth_deg + p_plus.azimuth_deg:7.2f})"
    )

# South pole, Ls=90 (austral winter): sun below horizon all sol → all elevations 0.
print()
for t in (0.25, 0.5, 0.75):
    pos = compute_sol_sun_position(t, latitude_deg=-90.0, ls_deg=90.0)
    print(f"South pole Ls=90 t={t}: el={pos.elevation_deg} (expect 0)")

# North pole, Ls=90 (austral summer): sun stays ~constant at el=obliquity=25.19.
print()
for t in (0.25, 0.5, 0.75):
    pos = compute_sol_sun_position(t, latitude_deg=90.0, ls_deg=90.0)
    print(f"North pole Ls=90 t={t}: el={pos.elevation_deg:.4f} (expect 25.19)")

# Linear-mode backward compat check.
print()
p_lin = compute_sol_sun_position(0.5, mode="linear")
print(
    f"Linear mode t=0.5 default envelope: az={p_lin.azimuth_deg} el={p_lin.elevation_deg} "
    "(expect 180, 60)"
)
p_lin0 = compute_sol_sun_position(0.0, mode="linear")
p_lin1 = compute_sol_sun_position(1.0, mode="linear")
print(
    f"Linear mode t=0: az={p_lin0.azimuth_deg} el={p_lin0.elevation_deg} "
    f" | t=1: az={p_lin1.azimuth_deg} el={p_lin1.elevation_deg} "
    "(expect 90/0 and 270/0)"
)

# Mode validation.
try:
    compute_sol_sun_position(0.5, mode="bogus")
except ValueError as exc:
    print(f"bogus mode correctly rejected: {exc}")

try:
    compute_sol_sun_position(0.5, latitude_deg=100.0)
except ValueError as exc:
    print(f"latitude OOR correctly rejected: {exc}")

# Sanity check: all math finite.
for t in (i / 20 for i in range(21)):
    p = compute_sol_sun_position(t)
    assert math.isfinite(p.azimuth_deg)
    assert math.isfinite(p.elevation_deg)
    assert math.isfinite(p.zenith_angle_rad)
print("finite check OK for t ∈ [0,1] at 0.05 steps")
