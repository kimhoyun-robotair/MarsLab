# MarsLab atmospheric reference reduction

## Direct light: MarsLab.pdf III-E, equation 3

`compute_direct_intensity` uses `I0 exp(-tau sec(z))` above the horizon and
zero at and below it. This is the relative optical air-mass approximation in
[Appelbaum and Flood, NASA TM-103623 (1990), equations 6–7](https://ntrs.nasa.gov/api/citations/19910005804/downloads/19910005804.pdf),
an update to their Solar Energy 45(6), 353–363 article cited by MarsLab.pdf.
The authors limit the secant approximation to zenith angles up to about 80°.
MarsLab retains continuous low-sun rendering at 80° < z < 90°, but does not
claim validated irradiance accuracy in that interval. A finite spherical
air-mass formula must not be attributed to this source without further data.

## Diffuse light: a tau-indexed COMIMART reduction

The runtime evaluates the delta-Eddington equations 10–23 of
[Vicente-Retortillo et al. (2015), COMIMART](https://doi.org/10.1051/swsc/2015035)
using the coefficients and mu0 column from Table 3, with a MarsLab dust-only
reduction assumption:

| Quantity | Reference value |
|---|---:|
| Single-scattering albedo, omega | 0.97 |
| Asymmetry parameter, g | 0.70 |
| Lambertian surface albedo, A | 0.25 |
| Cosine of zenith angle, mu0 | 0.70 |
| Sun elevation corresponding to mu0 | 44.427° |
| Cloud and gas optical depths (MarsLab assumption) | 0 |

These are representative NIR (700–1100 nm) dust parameters. Fixing mu0 at
the central Table 3 column produces the one-dimensional, tau-indexed reduction
used by MarsLab's sky renderer. The diffuse fraction is `D/T = 1 - B/T`, where
`T/E` comes from equations 10–22 and `B/E = exp(-tau/mu0)` uses the original
optical depth, as required by equation 23. The previous heuristic table has
been removed; no curve fitting or hand-adjusted diffuse fractions are used.

[comimart_reference.json](comimart_reference.json) transcribes the published
COMIMART and independent 32-stream DISORT comparisons (Table 3), preserving
all tau and mu0 values and their provenance. The source is CC-BY-4.0. A readable
[author-uploaded copy](https://www.researchgate.net/publication/283452176_A_model_to_calculate_solar_radiation_fluxes_on_the_Martian_surface)
was consulted on 2026-09-16.

### Scope and error interpretation

The independent DISORT comparison in the mu0=0.7 column spans tau 0.3–5.
Published COMIMART total-flux departures in this column range from about
-0.83% to +4.02%. The source values are printed to four decimal places.
Direct evaluation of the production equations gives the following values;
the largest residual against the printed COMIMART column is 0.00002596,
within its rounding resolution. Recomputing departure against the rounded
DISORT values gives -0.829% to +4.029%.

| tau | Computed T/E | Published COMIMART T/E | Diffuse D/T |
|---:|---:|---:|---:|
| 0.3 | 0.94450107 | 0.9445 | 0.31028235 |
| 0.6 | 0.89232596 | 0.8923 | 0.52441948 |
| 1.0 | 0.82759438 | 0.8276 | 0.71042452 |
| 1.5 | 0.75382140 | 0.7538 | 0.84436742 |
| 2.5 | 0.62700783 | 0.6270 | 0.95515900 |
| 5.0 | 0.40061546 | 0.4006 | 0.99802681 |

The runtime evaluates the equations directly between and outside these
anchors; tau below 0.3 and above 5, up to the configured limit of 6, do not
have published Table 3 comparison points. At tau=0 the dust-only diffuse
fraction is zero.

This reduction is not the full wavelength-dependent COMIMART model: it does
not integrate a solar spectrum or vary cloud composition, particle size,
surface albedo, or zenith angle. The NIR ratio drives the visible sky's
configurable renderer gain; it is not a calibrated RGB spectral model.
`sky_dome.brightness`, its colors/HDRI, sun intensity scale, and fog density
remain rendering controls. USD light units and rendered pixel values are
not asserted to reproduce measured W/m². Scientific reference agreement and
actual Isaac light/shadow/dust observations are separate evidence.
