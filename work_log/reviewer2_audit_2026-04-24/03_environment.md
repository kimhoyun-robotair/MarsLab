# 03 — environment (Mars atmosphere physics)

## 메타
- 대상:
  - `/home/hoyunkim/MarsLab/marslab/environment/__init__.py` (1 LOC)
  - `/home/hoyunkim/MarsLab/marslab/environment/diffuse_fraction.py` (55 LOC)
  - `/home/hoyunkim/MarsLab/marslab/environment/light_intensity.py` (38 LOC)
  - `/home/hoyunkim/MarsLab/marslab/environment/sky_dome.py` (91 LOC)
  - `/home/hoyunkim/MarsLab/marslab/environment/sun_position.py` (101 LOC)
  - `/home/hoyunkim/MarsLab/marslab/environment/tau_profile.py` (142 LOC)
  - 합계: 428 LOC
- 리뷰어: Reviewer 2 (hostile external)

## Findings

### CRITICAL (논문 figure 왜곡 / 잘못된 과학 결과)

#### C-1 `marslab/environment/light_intensity.py:38` — Beer's Law uses flat-earth airmass, not Appelbaum & Flood airmass
- 근거:
  ```python
  cos_z = math.cos(zenith_angle_rad)
  if cos_z <= 0:
      return 0.0
  return solar_constant * math.exp(-tau / cos_z)
  ```
  Docstring (L1–6) cites "Appelbaum, J. & Flood, D.J. (1990). Solar radiation on Mars. NASA TM-102299." and docstring (L13) claims "Beer's Law: I = I_0 * exp(-tau / cos(theta_z))".
- 문제:
  1. **Wrong airmass.** Appelbaum & Flood (NASA TM-102299) do NOT use the flat-slab `1/cos(z)` airmass. Their actual Mars formulation uses an airmass `m(z)` (equivalent to Kasten–Young-style correction) to remain finite past z > 70° and sphericity of the atmosphere. `1/cos(z)` diverges for z → 90°; the code band-aids this with a `cos_z <= 0 → 0` early return, but between 70° and 90° the exponent `tau / cos(z)` is *hugely* overestimated, producing artificial near-horizon darkness that will contaminate any τ-vs-irradiance figure in a paper. This is a figure-distorting error.
  2. **Solar constant ignores Mars eccentricity.** Docstring (L18) says "Mars mean at 1.52 AU is ~589 W/m²". Appelbaum's own analysis is explicit that Mars `G_ob` varies by ±19% over a Mars year due to e≈0.0934 orbit. A scalar `solar_constant` parameter hides this; a reader running "Ls sweep" experiments with a constant TOA irradiance will produce figures that do not match published Mars insolation curves.
  3. **Citation is decorative.** The paper is named but its actual formula (airmass m(z) * optical depth, with the Mars-Sun distance factor) is not implemented. A peer reviewer will note the mismatch.
- 제안:
  - Replace `exp(-tau / cos_z)` with Appelbaum's `exp(-tau * m(z))` where `m(z) = 1 / (cos(z) + 0.15 * (93.885 - z_deg)**(-1.253))` (Kasten 1966) or the Appelbaum-specific form. Clamp z ≤ 89°.
  - Expose a `mars_sun_distance_au` or `Ls` parameter and compute `G_ob = solar_constant_1AU / r_mars(Ls)**2` so eccentricity enters. Or at minimum rename the parameter to `toa_irradiance` and document that the caller must pre-correct for orbital distance, with a cross-reference to the value used in the paper.
  - Add a docstring unit test: Appelbaum Table 2 values for (Ls, z, τ) tuples within 5% — currently there is no such test, only a free-form "Beer's Law 5%" claim in the module header.

#### C-2 `marslab/environment/diffuse_fraction.py:17-34` — COMIMART reduced to 1-D τ lookup is scientifically incorrect
- 근거:
  ```python
  # COMIMART lookup table: (tau, diffuse_fraction)
  # Extracted from Vicente-Retortillo et al. (2015) Figure 4.
  _COMIMART_TABLE = np.array([
      [0.0, 0.0],
      [0.1, 0.12],
      ...
      [6.0, 0.96],
  ])
  ```
  And `compute_diffuse_fraction(tau)` has a single scalar input.
- 문제:
  1. **Model mis-specification.** Vicente-Retortillo et al. (2015) COMIMART is a full two-stream radiative-transfer model. The diffuse fraction f_d = I_diff / I_tot depends on (τ, solar zenith angle z, single-scattering-albedo ω, surface albedo A_s, atmospheric aerosol size distribution). Figure 4 of that paper shows multiple curves, one per zenith angle; pulling a single curve (presumably z=0 or z=60°, but the code doesn't say which) and calling it "the COMIMART fraction" is a scientific simplification that is **not** what the paper concludes. For the paper's τ-sweep figures, using this 1-D table will produce diffuse/direct ratios that deviate significantly from COMIMART's actual predictions at non-noon zenith angles.
  2. **Unphysical endpoint.** `[0.0, 0.0]` says "at τ=0 the atmosphere scatters nothing." This contradicts the paper: even at τ=0 the Rayleigh component of Mars CO₂ atmosphere contributes a small but nonzero diffuse fraction (~2–3% depending on z). The zero endpoint forces the rest of the interpolation to undershoot at low τ.
  3. **Source-of-truth missing.** "Extracted from Figure 4" with no zenith-angle disclosure and no reproducibility script. A reviewer cannot verify this table against the paper without guessing which curve was digitised.
- 제안:
  - Either (a) convert to a 2-D lookup `compute_diffuse_fraction(tau, zenith_angle_rad)` by digitising the full family of curves in Fig. 4, or (b) rename the module to `diffuse_fraction_1d_approx` and add a docstring warning that results are only valid for the zenith angle at which the table was digitised.
  - Document which curve (which z, which ω, which A_s) the table represents. Store the digitisation CSV under `data/` with a `__source__` comment so the figure is reproducible.
  - Fix the τ=0 entry to a physically-motivated Rayleigh floor (e.g. 0.02) or remove the τ=0 row entirely and require τ ≥ 0.05.
  - Add a unit test comparing the table to Vicente-Retortillo Fig. 4 within the claimed 5% tolerance.

#### C-3 `marslab/environment/sun_position.py:98-99` — "Linear azimuth sweep" is not first-order for any Mars latitude > 0
- 근거:
  ```python
  azimuth_deg = start_azimuth_deg + (end_azimuth_deg - start_azimuth_deg) * time_of_sol_fraction
  elevation_deg = max_elevation_deg * math.sin(math.pi * time_of_sol_fraction)
  ```
  Docstring (L11–13): "Solar azimuth: sunrise (~90 deg E) -> noon (~180 deg S) -> sunset (~270 deg W). Linear interpolation is a reasonable first-order approximation for Jezero crater latitude 18.4 deg N (Allison & McEwen 2000)."
- 문제:
  1. **Formula does not match the cited paper.** Allison & McEwen (2000) provide the standard spherical-astronomy form: `sin(el) = sin(φ) sin(δ) + cos(φ) cos(δ) cos(H)` and a corresponding azimuth equation. They do NOT endorse linear-in-time azimuth. For Jezero (φ=18.4° N) near equinox (δ≈0), azimuth actually changes very rapidly near noon (the sun transits close to zenith) — the true curve is sigmoidal, not linear. This linear approximation can be wrong by 20–40° of azimuth in the hour before/after solar noon.
  2. **Elevation formula is wrong except at a single special case.** `el = el_max * sin(π t)` only matches the spherical-trig answer when δ=0 AND φ=0. At φ=18.4° N the true elevation curve is **not** a pure half-sine; it is asymmetric if δ≠0 and has a different shape than sin(πt) even if δ=0 (because the arc is projected through latitude). Using this for a "Jezero 18.4° N" scenario produces sun positions that drift from reality over the sol, systematically shifting shadow directions in any rendered figure.
  3. **Docstring claims "first-order" but gives zero-order.** Linearising azimuth is zero-order; first-order would be the small-angle expansion of the hour-angle form. The comment misrepresents the quality of the approximation, which a reviewer will read as overstated rigour.
- 제안:
  - Implement the full Allison & McEwen form. It is one equation each for zenith and azimuth, takes (φ, δ, H) and is ~10 LOC. Store δ as a config (can be fixed to 0 for v1.0 equinox scenarios).
  - If keeping the linear model for v1.0 as an "intentional cartoon," change the docstring to say "crude linear arc, not physically accurate; use only for visualisation" and rename to `compute_sol_sun_position_linear_cartoon`. Do not publish paper figures from it.

### HIGH

#### H-1 `marslab/environment/sky_dome.py:78-83` — Tau→HDRI filename mapping hardcoded, uses `.png` not HDRI
- 근거:
  ```python
  if tau < 0.5:
      hdri_name = "mars_sky_clear.png"
  elif tau < 1.5:
      hdri_name = "mars_sky_moderate.png"
  else:
      hdri_name = "mars_sky_dusty.png"
  ```
  Containing dataclass attribute (L33): `hdri_texture_path: str`.
- 문제:
  1. **Hardcoded thresholds (0.5, 1.5) and filenames** in Python source. The SkyDomeConfig migration (per header comment at `rendering.py:133`) pulled the RGB endpoints and brightness slope into YAML but forgot the HDRI τ-bin thresholds and the filenames. Inconsistent migration.
  2. **File extension is `.png`, not an HDRI format.** HDRI implies high-dynamic-range (typically .hdr, .exr). An 8-bit PNG cannot store HDR sky radiance. Calling it `hdri_texture_path` while pointing to PNG is a lying attribute name, and the rendering pipeline will under-expose the sky if it tries to use these as HDR.
  3. **No file existence check.** `os.path.join(hdri_dir, hdri_name)` is returned whether or not the file exists. At render time a missing texture silently fails back to a default sky, making debugging hard.
- 제안:
  - Move the (tau_threshold → filename) pairs into `SkyDomeConfig` as an ordered list: `hdri_bins: list[tuple[float, str]]`. Loader validates monotonic thresholds.
  - Change filenames to `.hdr` or `.exr` and add pre-flight validation that each referenced file exists at config-load time, raising `FileNotFoundError` with full path.
  - Or, if these are genuinely placeholder PNGs for Phase 1 preview, rename the attribute to `sky_texture_path` and document it will be replaced by proper HDRI in v2.0.

#### H-2 `marslab/environment/sky_dome.py:66` — Hardcoded `tau / 3.0` dusty threshold decouples from `SkyDomeConfig`
- 근거:
  ```python
  # Interpolation factor: 0 at tau=0 (clear), 1 at tau>=3.0 (dusty)
  t = min(tau / 3.0, 1.0)
  ```
- 문제: The "tau at which the sky is fully dusty" is a physical tuning constant equivalent in role to `clear_rgb`/`dusty_rgb`. R2-A1 migration brought the colors out of code but left this denominator behind. A user who wants to say "my rover cam saturates at τ=4, not τ=3" must edit Python, violating config-first discipline. Also inconsistent with `diffuse_fraction.py` which spans τ∈[0, 6].
- 제안: Add `tau_dusty: float = Field(default=3.0, gt=0)` to `SkyDomeConfig` and use it here. Cross-reference the same value in `diffuse_fraction.py` as the interpolation domain so both modules agree on "what does dusty mean."

#### H-3 `marslab/environment/tau_profile.py:102-103` — Sine profile silently clips negative excursions without warning
- 근거:
  ```python
  tau = base_tau + amplitude * math.sin(2 * math.pi * t / period_fraction)
  return max(0.0, tau)
  ```
  Docstring (L82): "Must satisfy amplitude <= base_tau to avoid negative excursions (clamped)."
- 문제:
  1. Docstring says "must satisfy" but there is **no validation** that `amplitude <= base_tau`. The "must" is lied about.
  2. When the constraint is violated, the output is a rectified-sine (truncated at 0), which is **not** a sine oscillation. A user plotting "diurnal τ cycle" will see a waveform with flat floors and report it as a correct sine — this is a silent-swallow bug that corrupts paper figures.
  3. No log/warning on clamp.
- 제안:
  - Validate `amplitude <= base_tau` and raise `ValueError` if violated (per error-handling policy to not silently swallow).
  - Or, if clamping is intentional, rename function to `compute_tau_sine_rectified` and document the clipped shape explicitly with a worked example.

#### H-4 `marslab/environment/tau_profile.py:121,124-127,130-134` — `compute_tau` dispatcher hardcodes magic defaults
- 근거:
  ```python
  if profile == "constant":
      return compute_tau_constant(base_tau=kwargs.get("base_tau", 0.3), t=t)
  elif profile == "ramp":
      return compute_tau_ramp(
          start_tau=kwargs.get("start_tau", 0.3),
          end_tau=kwargs.get("end_tau", 2.0),
          t=t,
      )
  elif profile == "sine":
      return compute_tau_sine(
          base_tau=kwargs.get("base_tau", 0.5),
          amplitude=kwargs.get("amplitude", 0.3),
          period_fraction=kwargs.get("period_fraction", 1.0),
          t=t,
      )
  ```
- 문제:
  1. Six hardcoded numeric defaults (0.3, 0.3, 2.0, 0.5, 0.3, 1.0) buried in dispatcher with no citation or justification. A caller who supplies an incomplete kwargs dict silently gets these values — no warning, no error. This is exactly the "silently swallow" pattern the error-handling policy forbids.
  2. The defaults are inconsistent: `constant` uses `base_tau=0.3`, `sine` uses `base_tau=0.5`. Same-named parameter, different default. Confusing for users reading the code.
  3. `.get(..., default)` pattern masks typos: pass `compute_tau("constant", 0.5, base_ta=2.0)` (typo `base_ta`) and you get τ=0.3 instead of an error.
- 제안:
  - Remove defaults from the dispatcher. Require kwargs explicitly; if missing, raise `KeyError` with profile-specific required-key list.
  - Use `**kwargs` forwarding with a positive whitelist per profile; reject unknown keys.
  - Move profile-level defaults (if any are desired) into the YAML schema layer, not the dispatcher function.

#### H-5 `marslab/environment/sky_dome.py:18` — Module-level pydantic default created at import time
- 근거:
  ```python
  _DEFAULT_SKY_DOME_CONFIG = SkyDomeConfig()
  ```
- 문제:
  - `SkyDomeConfig()` runs at import. If the pydantic schema ever adds a required field without default, `import marslab.environment.sky_dome` starts crashing at the top of every downstream module. Fragile import-time side-effect.
  - Also: the sentinel `None` pattern is an anti-pattern when the dataclass itself already has `default_factory`. Just call `SkyDomeConfig()` inside the function body when `sky_cfg is None`; avoid the module-level object and the global.
- 제안:
  ```python
  def compute_sky_dome_params(tau, hdri_dir, sky_cfg=None):
      if sky_cfg is None:
          sky_cfg = SkyDomeConfig()
      ...
  ```

### MEDIUM

#### M-1 `marslab/environment/sun_position.py:49` — Azimuth accepts both 0 and 360 without normalisation
- 근거:
  ```python
  if not 0.0 <= azimuth_deg <= 360.0:
      raise ValueError(f"azimuth_deg must be in [0, 360], got {azimuth_deg}")
  ```
- 문제: 0° and 360° are the same direction; allowing both without normalisation means downstream equality checks (`if az == 0`) silently miss the 360° case. Also the edge is inclusive on both sides — pick one convention.
- 제안: Normalise with `azimuth_deg = azimuth_deg % 360.0` or clamp range to `[0, 360)`.

#### M-2 `marslab/environment/sun_position.py:95` — `max_elevation_deg` range check excludes 0 but allows near-zero
- 근거:
  ```python
  if not 0.0 < max_elevation_deg <= 90.0:
      raise ValueError(f"max_elevation_deg must be in (0, 90], got {max_elevation_deg}")
  ```
- 문제: `max_elevation_deg = 1e-10` passes validation but produces an effectively horizon-bound sun (degenerate arc). No practical lower bound.
- 제안: Impose a physical minimum (e.g. `>= 1.0` deg or a config-driven `mars_min_max_elevation`).

#### M-3 `marslab/environment/sun_position.py:54` — Zenith computed in radians while inputs in degrees — unit-mixing in a single dataclass
- 근거:
  ```python
  zenith_angle_rad = math.pi / 2.0 - math.radians(elevation_deg)
  return SunPosition(azimuth_deg=azimuth_deg, elevation_deg=elevation_deg, zenith_angle_rad=zenith_angle_rad)
  ```
- 문제: The `SunPosition` dataclass mixes degrees (azimuth, elevation) and radians (zenith). Every caller must remember which field is which unit. A downstream bug of passing `zenith_angle_rad` to a function expecting degrees will produce wrong irradiance with no type error. This is a classic unit-mismatch trap.
- 제안: Either store both in radians with clearly suffixed names (`azimuth_rad`, `elevation_rad`, `zenith_rad`) or provide `@property`-style converters. At minimum, add an invariant-test in the unit suite that `abs(zenith_angle_rad + math.radians(elevation_deg) - math.pi/2) < 1e-9`.

#### M-4 `marslab/environment/diffuse_fraction.py:55` — Lookup extrapolates outside table range silently
- 근거:
  ```python
  return float(np.interp(tau, _COMIMART_TABLE[:, 0], _COMIMART_TABLE[:, 1]))
  ```
- 문제: `np.interp` clamps out-of-range x to the endpoint y values (0.0 and 0.96). A caller passing τ=10 (extreme Mars storm, plausible) silently gets diffuse_fraction=0.96 with no warning — user cannot distinguish "interpolated" from "clamped." For a τ-sweep figure this flattens the curve above τ=6.
- 제안: Raise `ValueError` for `tau > _COMIMART_TABLE[:,0].max()` OR return a flag alongside, OR extend the table by extrapolating to asymptote f_d → 1.0 and document the extrapolation method.

#### M-5 `marslab/environment/light_intensity.py:35-36` — Horizon cutoff is an abrupt step, not a smooth refraction model
- 근거:
  ```python
  if cos_z <= 0:
      return 0.0
  ```
- 문제: On Earth (and Mars) the sun produces nonzero atmospheric illumination even slightly below the geometric horizon (civil/nautical twilight); Mars has a thin atmosphere but scattering still delivers ambient light near sunrise/sunset. An abrupt cutoff at z=90° produces discontinuous light curves, making τ-sweep figures have a kink. Also `cos_z <= 0` means exactly at horizon (cos_z=0) returns 0, but cos_z=+1e-17 would divide-by-near-zero and exp-underflow to 0; behaviour near horizon is inconsistent depending on float rounding.
- 제안: Add a twilight term or, at minimum, limit the zenith check to `z > 89.5° → 0` and document the cutoff. Use `if zenith_angle_rad >= math.pi/2 - 1e-3` for numerical safety.

#### M-6 `marslab/environment/sky_dome.py:12` — `import os` for a single `os.path.join`
- 근거:
  ```python
  import os
  ...
  hdri_path = os.path.join(hdri_dir, hdri_name)
  ```
- 문제: `os.path` in a new module is a code smell. Project-wide practice should use `pathlib.Path` for portability and to expose `Path.exists()` for the missing H-1 check. Also, returning a `str` path (not `Path`) forces downstream code into string manipulation.
- 제안: Switch to `pathlib.Path` and `SkyDomeParams.hdri_texture_path: Path` typed.

### LOW

#### L-1 `marslab/environment/__init__.py:1` — Package init exports nothing
- 근거:
  ```python
  """Mars environmental state computation for MarsLab."""
  ```
- 문제: No `__all__`, no re-exports of public entry points (`compute_sun_position`, `compute_direct_intensity`, `compute_diffuse_fraction`, `compute_sky_dome_params`, `compute_tau*`). Users must know the internal file layout. Not a bug, just API hygiene.
- 제안: Add explicit re-exports and `__all__`.

#### L-2 `marslab/environment/sun_position.py:5-6` — Docstring says "Phase 1 / Phase 2" but no runtime branching
- 근거:
  ```python
  Phase 1: User-configured azimuth/elevation from YAML.
  Phase 1 dynamic: Sol-fraction-based sun sweep (east-to-west arc).
  Phase 2 (future): Allison & McEwen (2000) Ls-based orbital mechanics.
  ```
- 문제: Aspirational roadmap language in source docstring. When a reviewer reads this, they expect a selector; there isn't one. Remove or move to a CHANGELOG-style doc.

#### L-3 `marslab/environment/tau_profile.py:139-142` — Private validator uses same name as shared helper
- 근거:
  ```python
  def _validate_t(t: float) -> None:
      if not 0.0 <= t <= 1.0:
          raise ValueError(f"t must be in [0, 1], got {t}")
  ```
- 문제: Defined at the bottom of the file but called from the top (L37, L59, L94) — requires forward reference. Python allows this, but it's stylistically jarring. Also, error message says "`t` must be..." which is uninformative once propagated; include function name.
- 제안: Move to top of file. Change message: `f"time_of_sol_fraction 't' must be in [0, 1], got {t}"`.

#### L-4 `marslab/environment/diffuse_fraction.py:37` — Return type `float` but receives numpy scalar
- 근거:
  ```python
  return float(np.interp(tau, _COMIMART_TABLE[:, 0], _COMIMART_TABLE[:, 1]))
  ```
- 문제: Already cast to `float`; fine. But passing a numpy scalar `tau` (e.g. `np.float64(0.5)`) is silently accepted despite the type hint `tau: float`; consider explicit `float(tau)` and value validation.

#### L-5 `marslab/environment/tau_profile.py:107` — `**kwargs: float` type hint lies
- 근거:
  ```python
  def compute_tau(profile: str, t: float, **kwargs: float) -> float:
  ```
- 문제: `**kwargs: float` means "each kwarg value is a float"; `profile_fraction` and similar are expected to be floats and that's fine, BUT kwarg *names* are free-form strings. A type checker cannot catch typo `base_ta` vs `base_tau`. Consider a TypedDict for each profile or overloads.

#### L-6 `marslab/environment/light_intensity.py:18-19` — Docstring gives approximate numeric value as normative
- 근거:
  ```python
  solar_constant: Top-of-atmosphere irradiance in W/m^2.
      Mars mean at 1.52 AU is ~589 W/m^2.
  ```
- 문제: 589 W/m² is the commonly cited value (some sources give 590, 586.2, 588.3). The docstring says "~589" as if it were normative; a reader might hardcode it into a YAML config thinking that's the canonical value. No citation.
- 제안: Either cite (Appelbaum Table 1, value 586.2 W/m²) or remove the number from the docstring.

### DELETE CANDIDATES

- **`marslab/environment/__init__.py`** (1 LOC, essentially empty): not a delete candidate — keeps the package importable — but replace with explicit re-exports (L-1).
- **`_COMIMART_TABLE` constants inside `diffuse_fraction.py`** (L17–34): candidate for extraction into `configs/atmosphere/comimart.csv` with `numpy.loadtxt`, so that the lookup is data-driven. If the 2-D correction in C-2 is implemented, the whole 1-D table should be deleted.
- **`compute_sol_sun_position` (sun_position.py:62-101)**: delete if/when replaced by a proper Allison & McEwen implementation (C-3). Cannot be deleted in v1.0 without a replacement, but schedule for removal.
- **`_DEFAULT_SKY_DOME_CONFIG` global (sky_dome.py:18)**: delete; inline the default inside the function (H-5).

### FALSE-POSITIVE WATCHLIST

- **`zenith_angle_rad` stored in `SunPosition` (sun_position.py:33)**: This is *not* a bug per se — the author deliberately pre-computed it. I flagged (M-3) the unit-mix risk but acknowledge this is a design choice. If unit tests cover the invariant, downgrade.
- **`tau_profile.compute_tau_constant` taking an unused `t` (tau_profile.py:24)**: flagged-looking but the docstring explicitly says "unused, for API consistency." Intentional uniform signature for dispatcher. Not a bug.
- **`cos_z <= 0` horizon cutoff (light_intensity.py:35)**: I called this out in M-5 as a physics concern, but as a *code correctness* matter the bare comparison is fine; don't treat as a float-equality bug.
- **`math` vs `numpy` mix across files**: `math` used in sun_position/light_intensity/tau_profile, `numpy` in diffuse_fraction. Looks inconsistent but each usage is justified (scalar math vs vector interp). Not a real issue.
- **`os.path.join` (sky_dome.py:85)**: flagged M-6 for style; it is functionally correct on Linux/macOS. Do not downgrade to a correctness bug.
- **No seed parameter anywhere in this module**: would be a bug in a randomised module, but every function here is deterministic. Not a finding.

## 3-line summary
Three CRITICAL scientific-accuracy issues: Beer's Law uses flat-slab airmass despite citing Appelbaum & Flood (C-1), COMIMART is reduced to a 1-D τ lookup that discards zenith-angle dependence (C-2), and the "first-order Jezero sun sweep" is zero-order linear-in-azimuth with a wrong elevation arc (C-3) — any of these will distort paper figures. High-severity: hardcoded HDRI PNG filenames with wrong extension (H-1), τ/3 dusty threshold outside config (H-2), sine-profile silent rectification (H-3), dispatcher magic defaults (H-4), import-time pydantic side-effect (H-5). Remaining Medium/Low findings are unit-mixing, silent extrapolation, and docstring-vs-code lies; delete candidates limited to inline data extraction and a stale global.
