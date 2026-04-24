# Reviewer 2 Audit — tests/integration + configs/ + pyproject.toml + .github + repo root

Scope: package hygiene, CI config, YAML correctness. Hostile external review. Internal-doc
citations in comments (e.g. "R2-A1 (2026-04-22)", "P1-1b", "Wk2 #6", "G5 §3.5") are noise —
comments-as-deodorant. Changelog/provenance belongs in `CHANGELOG.md` or git history, not in
docstrings of a production codebase.

---

## 1. pyproject.toml

File: `/home/hoyunkim/MarsLab/pyproject.toml` (49 lines total — already a smell for a claimed
"iSpaRo 2026 submission" project).

### 1.1 Missing author / maintainer
- **Location:** `pyproject.toml:1-14`
- **Quote:** project metadata block declares `name`, `version`, `description`,
  `requires-python`, `license` — nothing else.
- **Problem:** PEP 621 metadata omits `authors = [...]`, `maintainers = [...]`, `readme`,
  `urls` (homepage / repository / issue tracker / documentation), `keywords`, `classifiers`.
  An installed wheel from this project has no author string, no homepage, no PyPI
  classifiers. A reviewer who `pip install`s and runs `pip show marslab` sees a blank.
- **Fix:** Populate `authors = [{name = "Hoyun Kim", email = "..."}]`,
  `readme = "README.md"`, `urls = {Homepage = "https://github.com/.../MarsLab", Issues = "..."}`,
  `classifiers = ["License :: OSI Approved :: Apache Software License", ...]`,
  `keywords = ["mars", "simulation", "robotics", "isaac-sim"]`.

### 1.2 License declared but LICENSE file does not exist
- **Location:** `pyproject.toml:6` — `license = "Apache-2.0"`
- **Problem:** The repo root has **no `LICENSE` file** (confirmed via `ls`). Apache-2.0
  requires the full license text to be distributed with the source. Declaring
  `license = "Apache-2.0"` in pyproject.toml is not a substitute; Apache-2.0 §4(a)
  requires you to "give any other recipients of the Work or Derivative Works a copy of
  this License". GitHub's license detection also fails without the file. This is a
  **legal** defect, not just a packaging nit.
- **Fix:** Commit a `LICENSE` file containing the canonical Apache-2.0 text. Pre-2026
  PEP 639 style `license = "Apache-2.0"` is also fine, but the file is non-optional.

### 1.3 Dependency pinning — upper bounds missing
- **Location:** `pyproject.toml:7-22`
- **Quote:**
  ```
  dependencies = [
      "pydantic>=2.0",
      "pyyaml>=6.0",
      "numpy>=1.24",
      "GDAL>=3.8",
      "scipy>=1.10",
      "trimesh>=4.0",
  ]
  ```
- **Problem:** Every dependency is a floor only. `numpy 2.x` is a known breaking release;
  `pydantic 3.x` when it lands will break the `model_validator` decorators littered across
  `marslab/config/schema/`. `GDAL>=3.8` with no upper bound is particularly hazardous —
  `GDAL 4.x` ships incompatible Python bindings. No `requirements*.lock` / `uv.lock` /
  `pip-tools` snapshot either, so the "it worked on my machine last week" failure mode is
  baked in.
- **Fix:** Cap the known-risky majors: `pydantic>=2.0,<3`, `numpy>=1.24,<3`,
  `GDAL>=3.8,<4`. Provide a committed `requirements.lock` generated via `pip-compile` or
  `uv pip compile` for reproducibility.

### 1.4 Python version mismatch: code targets 3.10, CI uses 3.12
- **Location:** `pyproject.toml:5` — `requires-python = ">=3.10"`
- **Location:** `pyproject.toml:34` — `[tool.black] target-version = ["py310"]`
- **Location:** `pyproject.toml:38` — `[tool.ruff] target-version = "py310"`
- **Location:** `.github/workflows/lint.yaml:17` and `.github/workflows/unit_tests.yaml:17`
  both pin `python-version: "3.12"`.
- **Problem:** CI tests 3.12 only. 3.10 — the declared minimum — is never exercised. If
  a contributor uses a 3.11-only syntax (e.g. `typing.Self` at module scope, `except*`,
  PEP 695 type parameters) it will pass CI and break every Ubuntu 22.04 user still on
  3.10.12. The ISPAro paper claim of "Python 3.10+" is therefore an untested claim.
- **Fix:** Run CI as a matrix `python-version: ["3.10", "3.11", "3.12"]`. Keep lint on
  one version (3.12) if you want speed but run tests on all three.

### 1.5 Pytest config ignores testpaths/unit split
- **Location:** `pyproject.toml:46-48`
- **Quote:** `testpaths = ["tests"]` with no markers and no default opts.
- **Problem:** `testpaths = ["tests"]` pulls in `tests/integration/`. The `tests/integration/`
  directory contains only an empty `__init__.py` (see §5), but the CI workflow explicitly
  runs `pytest tests/unit/`, not `pytest` — the testpaths declaration and the CI command
  disagree. Additionally there is **no `markers = [...]`** declaration, so any future
  `@pytest.mark.slow`/`@pytest.mark.gpu`/`@pytest.mark.integration` marker triggers
  pytest `PytestUnknownMarkWarning`. **No `addopts = "--strict-markers"`** either, so
  typo'd markers silently become no-ops.
- **Fix:** `addopts = "-ra --strict-markers --strict-config"` and
  `markers = ["gpu: requires CUDA device", "integration: requires Isaac Sim"]`.

### 1.6 Tool sections absent — coverage, mypy, pytest-cov not configured
- **Problem:** No `[tool.coverage.*]`, no `[tool.mypy]`, no `[tool.pytest.ini_options.log_cli]`.
  Yet `/home/hoyunkim/MarsLab/.coverage` (69 KB binary file) sits at repo root —
  coverage is being collected somehow but nothing in pyproject.toml configures the exclusion
  list. That means `.coverage` database uses default filters and collects coverage for
  `tests/*` itself, polluting metrics.
- **Fix:** Add `[tool.coverage.run]` with `source = ["marslab"]`, `omit = ["tests/*"]`,
  and gitignore the generated `.coverage` DB (see §6.2).

### 1.7 Ruff rule set is dangerously narrow
- **Location:** `pyproject.toml:40-41`
- **Quote:** `select = ["E", "F", "W", "I"]`
- **Problem:** `E`, `F`, `W`, `I` are pycodestyle errors, pyflakes, warnings, isort. That's
  it. No `B` (flake8-bugbear — catches mutable default args, useless `except` blocks, raw
  strings that don't need to be), no `UP` (pyupgrade — suggests modern Python idioms), no
  `SIM` (flake8-simplify), no `RUF`, no `N` (pep8-naming), no `ARG` (unused arguments),
  no `PL` (pylint). A codebase of 40+ Python files and 12+ YAML schema models deserves
  at minimum `B`, `UP`, `SIM`, `N`.
- **Fix:** `select = ["E", "F", "W", "I", "B", "UP", "SIM", "N", "RUF", "PL"]` — start
  here and add `--ignore` per-rule as false positives surface.

### 1.8 Packages.find too narrow; tests not discoverable
- **Location:** `pyproject.toml:28-30`
- **Quote:** `[tool.setuptools.packages.find] where = ["."]; include = ["marslab*"]`
- **Problem:** `include = ["marslab*"]` excludes `tests/`, which is fine, but it also means
  `configs/` and `assets/` are not part of the distribution. If a user runs
  `pip install marslab` from PyPI, they get the Python package with **zero YAML configs**
  — none of the seven mission scenarios, none of the robot YAMLs. The README claims
  "Configuration: All parameters are in `configs/mars_env.yaml`" but a wheel install has
  no `configs/` directory. This is an integration bug, not merely a packaging nit.
- **Fix:** Either (a) add `[tool.setuptools.package-data] marslab = ["../configs/**/*.yaml"]`
  (fragile), or (b) move canonical configs into `marslab/_configs/` and adapt the loader,
  or (c) document clearly that MarsLab requires a git clone, not `pip install` (and add
  `classifiers = ["Development Status :: 3 - Alpha"]`).

---

## 2. .github/workflows/

### 2.1 lint.yaml — no action pinning by SHA
- **Location:** `.github/workflows/lint.yaml:13,15`
- **Quote:**
  ```
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
  ```
- **Problem:** `@v4` / `@v5` are **floating major tags**. GitHub's own security guidance
  (SLSA, OSSF Scorecard) mandates pinning actions by full commit SHA to defend against
  tag-move supply-chain attacks (cf. tj-actions/changed-files April 2025 incident). For
  a research codebase this is lower-priority than for production, but the project claims
  Apache-2.0 publication; downstream consumers who fork and run the same CI inherit the
  vulnerability.
- **Fix:** Pin SHAs and add `# v4.2.2` comments. Enable dependabot for `github-actions`.

### 2.2 lint.yaml — pip install without version lockfile
- **Location:** `.github/workflows/lint.yaml:20`
- **Quote:** `run: pip install black>=24.0 ruff>=0.4`
- **Problem:** (a) Shell argument `black>=24.0` is not quoted, which means the `>` is a
  shell redirection operator in some shells (bash on GHA Ubuntu tolerates this only because
  the tokens parse to a filename that doesn't resolve, but this is brittle — `pip install
  "black>=24.0" "ruff>=0.4"` is correct). (b) Every CI run resolves the latest black/ruff
  floating over 24.x / 0.4.x, so a new ruff release that adds a rule can break CI without
  any code change. (c) No pip cache — GitHub Actions has `actions/cache@v4` for this.
- **Fix:** Quote the arguments. Add pip caching. Or better: `pip install -e ".[dev]"` to
  reuse the pyproject-declared pins.

### 2.3 lint.yaml — no concurrency group
- **Problem:** Multiple pushes to the same branch queue behind each other. Waste of CI
  minutes and reviewer time.
- **Fix:**
  ```yaml
  concurrency:
    group: lint-${{ github.ref }}
    cancel-in-progress: true
  ```

### 2.4 lint.yaml — `branches: ["*"]` runs on all branches, no fork PR protection
- **Location:** `.github/workflows/lint.yaml:4-7`
- **Problem:** `on: pull_request: branches: ["*"]` runs the workflow for every PR. If any
  future job uses `secrets.*` (e.g. deploy, slack notify, artifact upload to private
  registry), a malicious PR from a fork can harvest them. Currently no secrets are used,
  so this is latent — flag for future.
- **Fix:** Split into `pull_request` (runs on forks, no secrets) and
  `pull_request_target` (restricted; requires manual review).

### 2.5 unit_tests.yaml — same issues as lint.yaml
- **Location:** `.github/workflows/unit_tests.yaml:13-15,20,22`
- **Problems (combined):**
  - Actions not SHA-pinned (`@v4`, `@v5`).
  - `sudo apt-get update && sudo apt-get install -y libgdal-dev gdal-bin` — no apt cache,
    no version pin. A Jammy ubuntu-latest minor-rev apt-cache refresh can pull a new GDAL.
  - `pip install -e ".[dev]"` — no pip cache, dependencies not locked.
  - Only one Python version (3.12), only `ubuntu-latest`, single arch — no macOS / Windows
    matrix. The project declares `requires-python = ">=3.10"` but 3.10 / 3.11 are never
    tested (duplicate of §1.4).
  - No step-level timeout (`timeout-minutes:`) — a hung pytest blocks the runner for 6h.
- **Fix:** Matrix Python 3.10/3.11/3.12, SHA-pin actions, cache pip + apt,
  `timeout-minutes: 15` on the test job.

### 2.6 No coverage upload, no test artifact retention
- **Problem:** `pytest tests/unit/ -v --tb=short` produces no junit XML, no coverage report.
  There is a `.coverage` in the repo root but it's never uploaded anywhere. PR reviewers
  have zero observability into test trend.
- **Fix:** `--junit-xml=report.xml --cov=marslab --cov-report=xml`, then
  `actions/upload-artifact@<sha>` for the XML; optionally `codecov/codecov-action@<sha>`.

### 2.7 No separate workflow for pre-commit, type-check, security
- **Problem:** The project has lint + unit tests. Nothing else. Missing:
  - `pip-audit` / `safety` run on pyproject dependencies (CVE scanner).
  - `mypy` / `pyright` — no static type check despite declaring type hints on public
    functions (cf. CLAUDE.md "Type hints on all public functions").
  - `pre-commit` — no `.pre-commit-config.yaml` exists (§6.1). Users must remember to run
    black+ruff manually.
- **Fix:** Add `type-check.yaml`, `security.yaml`, and commit a `.pre-commit-config.yaml`.

---

## 3. configs/mars_env.yaml

### 3.1 Magic number: `sun_intensity_scale: 30.0` — no citation
- **Location:** `configs/mars_env.yaml:61`
- **Quote:** `sun_intensity_scale: 30.0          # W/m^2 → Isaac Sim path-tracing units (calibrated 2026-04-16)`
- **Problem:** "Calibrated 2026-04-16" is not a reference. It's a timestamp. What
  procedure? What Isaac Sim version? What luminance target? The conversion from "W/m²" to
  "Isaac Sim light units" is not 30.0× in any published Isaac Sim documentation —
  `IntensityAPI` on a `DistantLight` expects cd/m² in path-tracing and lux in ray-tracing;
  30.0 is a fudge factor. A reviewer cannot reproduce a paper figure from an unsourced
  fudge factor.
- **Fix:** Replace the "calibrated 2026-04-16" comment with the measurement protocol:
  "Value chosen so that a Lambertian surface with albedo 0.25 at normal incidence
  produces N cd/m² at sun elevation 45°, matching Appelbaum & Flood (1990) within 5%."
  Or move calibration into a regression test.

### 3.2 Magic number: `dome_brightness_scale: 5000.0` — same problem
- **Location:** `configs/mars_env.yaml:64`
- **Quote:** `dome_brightness_scale: 5000.0      # sky dome multiplier (calibrated 2026-04-16 for path-tracing)`
- **Fix:** Same as §3.1.

### 3.3 Magic number: `fog_density_scale: 0.002` — dimensional analysis missing
- **Location:** `configs/mars_env.yaml:65`
- **Quote:** `fog_density_scale: 0.002           # tau → fog density`
- **Problem:** tau is dimensionless (optical depth). "fog density" in Isaac Sim RTX fog is
  m⁻¹. So 0.002 has units of m⁻¹ per tau unit. No citation, no derivation. If the tau
  sweep in the paper goes from 0.3 to 4.0, fog density goes 0.0006 to 0.008 m⁻¹, which
  corresponds to visibility 5 km — 0.4 km (Koschmieder's law: V ≈ 3.912 / sigma). Is that
  the intent? Undocumented.
- **Fix:** Derive from Koschmieder + Pollack 1979 Mars dust extinction coefficient; cite.

### 3.4 `physics_dt` has the wrong precision and wrong comment
- **Location:** `configs/mars_env.yaml:17`
- **Quote:** `physics_dt: 0.016666666666666666   # s (60 Hz engine tick; P6 G5 migration)`
- **Problem 1:** "P6 G5 migration" is internal nomenclature that means nothing to a
  reader. The comment says what should be in the commit message or `CHANGELOG.md`, not in
  the config.
- **Problem 2:** 16 decimal digits of a float when Python float has 15-17 significant
  decimal digits anyway. `0.0166666666666666666` rounds to `1.0 / 60.0` exactly. Why not
  write `1.0 / 60.0` in the loader and expose `physics_hz: 60` in the config?
- **Problem 3:** Hz-based config would be validated by the schema (`ge=10, le=1000`) — dt
  is backwards.
- **Fix:** Replace with `physics_hz: 60` in YAML; compute `dt = 1.0 / hz` in the loader.

### 3.5 Contradictory tau defaults between static and dynamic blocks
- **Location:** `configs/mars_env.yaml:9` — `dust_optical_depth: 0.3`
- **Location:** `configs/mars_env.yaml:27-28` — `tau_constant: base_tau: 0.3`
- **Location:** `configs/mars_env.yaml:33-35` — `tau_sine: base_tau: 0.5, amplitude: 0.3`
- **Problem:** When `dynamic_atmosphere.enabled = false` (the default), runtime uses
  `dust_optical_depth`. When `enabled = true` with `tau_profile = "constant"`, runtime
  uses `tau_constant.base_tau`. Both default to 0.3 — coincidence, not a constraint.
  Nothing in the schema enforces consistency. A user who edits `dust_optical_depth: 2.0`
  but leaves `tau_constant.base_tau: 0.3` gets different τ depending on the `enabled`
  flag, silently. For domain randomization sweeps this is a nightmare to debug.
- **Fix:** Add a `model_validator` on `MarsEnvConfig` that when
  `dynamic_atmosphere.enabled = false` warns if `dust_optical_depth !=
  dynamic_atmosphere.tau_constant.base_tau`. Or unify: delete `dust_optical_depth` and
  route everything through `dynamic_atmosphere` with `enabled=false, tau_profile=constant`.

### 3.6 Dead key: `surface_albedo_range` never enforced on terrain
- **Location:** `configs/mars_env.yaml:11` — `surface_albedo_range: [0.10, 0.40]`
- **Problem:** This field is in the `mars_env` block but terrain / rock albedo is set
  separately in the `terrain` block and scenario YAMLs. Nothing in the loader or
  renderer cross-checks that `terrain.rock_color` reflectance falls within
  `surface_albedo_range`. Dead informational key.
- **Fix:** Add a validator that checks computed rock albedo ∈ `surface_albedo_range`, or
  delete the field.

### 3.7 Commented-out terrain source
- **Location:** `configs/mars_env.yaml:39-41`
- **Quote:**
  ```yaml
  # source: "hirise"
  # dem_path: "assets/terrain/dem/jezero_crater.tif"
  # converted_dem_dir: "assets/terrain/dem/jezero_crater_converted"
  source: "procedural"
  ```
- **Problem:** Commented YAML is a smell — dead config that can diverge from live config
  and be uncommented accidentally. Either the file supports both (document the switch) or
  delete the comments.
- **Fix:** Delete commented lines. If both presets are valuable, split into
  `configs/mars_env_procedural.yaml` and `configs/mars_env_hirise.yaml`.

### 3.8 Schema redundancy: literal `1.0/60.0` exists in schema default vs yaml literal
- **Location:** `configs/mars_env.yaml:17` vs `marslab/config/schema/mars_env.py:178`
- **Problem:** The schema's `physics_dt` default is `1.0 / 60.0` (exact), but the YAML
  uses a long decimal. These two values round to the same float, but a pydantic equality
  check `mars_env.physics_dt == MarsEnvConfig.model_fields['physics_dt'].default` is not
  guaranteed reliable across 3.10/3.11/3.12 due to float round-off. If any code compares
  "is the YAML override equal to schema default?" to skip work, there's a latent bug.
- **Fix:** Single source of truth (§3.4).

### 3.9 Invariant commentary mixes YAML values with Python literals
- **Location:** `configs/mars_env.yaml:68-73`
- **Quote:** "sun_prim_path / dome_prim_path: override when a scenario needs multiple
  lights. Defaults match the historical paths used in sun_renderer.py / sky_renderer.py
  (2026-04-16)."
- **Problem:** Cross-references the Python source file by line number with a date stamp.
  That's a brittle link that future refactors will not update. The schema docstring says
  the same thing; repeating it in YAML comments duplicates maintenance burden.
- **Fix:** Move rationale into the pydantic `Field(... description=...)` (already done
  there, so the comment is redundant) and delete the YAML comment.

---

## 4. configs/scenarios/*.yaml

### 4.1 MASSIVE DUPLICATION — `mars_env` block copied 7 times verbatim
- **Location:** `configs/scenarios/cave_lava_tube.yaml:7-30`,
  `cerberus_canyon.yaml:7-30`, `cerberus_canyon_easy.yaml:7-30`, `jezero_crater.yaml:6-29`,
  `jezero_flat.yaml:6-29`, `jezero_rocks.yaml:6-29`, `mars_base.yaml:17-40`,
  `procedural_canyon.yaml:7-30`, `spacecraft_landing.yaml:19-44`.
- **Quote (representative, jezero_flat.yaml:6-29):**
  ```yaml
  mars_env:
    gravity: 3.72
    atmo_pressure: 610
    atmo_density: 0.020
    dust_optical_depth: 0.3
    solar_constant_mean: 589
    surface_albedo_range: [0.10, 0.40]
    surface_temp_mean: -60
    sol_duration_seconds: 88642
    dust_opacity_range: [0.5, 2.0]
    sun_azimuth_deg: 180
    sun_elevation_deg: 45
    seed: 42
    dynamic_atmosphere:
      enabled: True
      time_scale: 200.0
      sun_sweep:
        start_azimuth_deg: 90
        end_azimuth_deg: 270
        max_elevation_deg: 60
      tau_profile: "constant"
      tau_constant:
        base_tau: 0.3
      update_interval_frames: 10
  ```
  Identical blocks appear in 8 of 9 scenario files. `spacecraft_landing.yaml` differs only
  in `sun_azimuth_deg: 135` / `sun_elevation_deg: 40`; `mars_base.yaml` differs only in
  `sun_elevation_deg: 50`.
- **Problem:** ~200 lines of duplicate YAML across the scenarios directory. The `rendering`
  block is also duplicated with identical values (cf. `rendering.sun_intensity_scale: 30.0`
  repeated 7× verbatim). When the next calibration pass changes
  `dome_brightness_scale`, the dev must edit 7 files — and *will* miss one. User memory
  already notes MarsLab fought at least one regression where scenario YAMLs drifted from
  `mars_env.yaml` defaults (see `configs/phase1.yaml` rover block vs
  `configs/robots/rover_m2020.yaml` note "Blocks here mirror the legacy
  `configs/phase1.yaml` rover block verbatim" — self-acknowledged duplicate).
- **Fix:** Use YAML anchors, or a proper `!include` loader (PyYAML doesn't have one by
  default — `hiyapyco` or manual merge in the loader). The scenario loader
  (`marslab/config/scenario_loader.py`) already does deep-merge for `rover.base_config`
  per the rover_m2020.yaml comment — extend the same pattern to `mars_env:` and
  `rendering:` via a `base_mars_env: "configs/mars_env.yaml"` scenario field.

### 4.2 Inconsistent boolean casing across scenario files
- **Location:** `configs/scenarios/jezero_flat.yaml:20` — `enabled: True`
- **Location:** `configs/scenarios/cerberus_canyon_easy.yaml:21` — `enabled: true`
- **Location:** `configs/scenarios/mars_base.yaml:31` — `enabled: True`
- **Location:** `configs/scenarios/spacecraft_landing.yaml:35` — `enabled: True`
- **Problem:** YAML 1.1 treats `True`/`true`/`yes`/`on` all as truthy, but YAML 1.2 (which
  PyYAML does NOT fully implement by default) only recognises `true`/`false`. Mixed
  casing also bothers linters. The fact that `jezero_flat.yaml` uses `True` (Python-style)
  while `cerberus_canyon.yaml:21` uses `true` (lowercase) tells me these files were
  hand-copied from different sources without review. This is exactly the drift risk of
  §4.1.
- **Fix:** Pin to lowercase `true`/`false` everywhere. Add `yamllint` to CI with
  `truthy: {allowed-values: ['true', 'false']}`.

### 4.3 `jezero_flat.yaml` has `rock_sfd_k: 0` but declares `rock_diameter_range`
- **Location:** `configs/scenarios/jezero_flat.yaml:40-41`
- **Quote:** `rock_sfd_k: 0` followed by `rock_diameter_range: [0.20, 3.0]`
- **Problem:** With `rock_sfd_k = 0`, no rocks are placed (CFA = 0). Therefore
  `rock_diameter_range` is irrelevant — dead field. But the schema
  (`terrain.py:268-272`) has `rock_sfd_k: ge=0, le=0.15` which accepts 0; nothing in the
  validator says "if `rock_sfd_k == 0`, warn that rock_* fields are ignored".
  `mars_base.yaml:51` and `spacecraft_landing.yaml:55` have the same inconsistency.
- **Fix:** Either drop the ignored fields in scenarios with no rocks, or promote
  `rock_sfd_k == 0` to a sentinel and enforce in the validator.

### 4.4 `spacecraft_landing.yaml` references assets that do not exist
- **Location:** `configs/scenarios/spacecraft_landing.yaml:95-125`
- **Quote:** `asset_path: "assets/structures/spacecraft/insight_lander.usd"` (×5 variants)
- **Quote (YAML comment):** "Placeholder asset paths — the actual USD assets under
  `assets/structures/spacecraft/` are produced out-of-band by the artist team"
- **Problem:** The scenario YAML commits paths to files that do not exist. Running
  `run_stage3_monolithic.py --config configs/scenarios/spacecraft_landing.yaml` will
  pydantic-validate fine and then crash at structure_loader time with a
  `FileNotFoundError`. The comment acknowledges this but does nothing to protect the user.
  The integration test suite has no test that exercises spacecraft_landing or mars_base,
  so CI never catches missing assets. A reviewer running the paper's 7 scenarios will hit
  a crash on scenarios 6 and 7.
- **Fix:** (a) Skip those scenarios in any "smoke all scenarios" suite until the assets
  land. (b) Emit a single clear `FileNotFoundError` from `structure_loader.py` that lists
  every missing file up-front rather than the first one. (c) Document asset status in the
  README with a clear "spacecraft_landing and mars_base require artist assets — currently
  not shipped" line.

### 4.5 `mars_base.yaml` same asset problem
- **Location:** `configs/scenarios/mars_base.yaml:91-131`
- **Quote:** Same placeholder pattern: `assets/structures/base/habitat_module.usd` etc.
- **Fix:** Same as §4.4.

### 4.6 `assets/structures/LICENSES.md` referenced but not verified
- **Location:** Both scenarios reference `assets/structures/LICENSES.md` in comments.
  Reviewer did not read that file (outside scope), but a quick `ls` confirms
  `/home/hoyunkim/MarsLab/assets/structures/` existence would be needed to back the
  Apache-2.0 claim.
- **Fix:** Validate that `LICENSES.md` lists every bundled asset and its license.

### 4.7 `procedural_canyon.yaml` is missing `seed` at the top level — inconsistency
- **Location:** `configs/scenarios/procedural_canyon.yaml:32-55` (terrain block)
- **Quote:** Terrain block declares `seed: 42` correctly but the **canyon_* fields
  (lines 39-45)** have no `Canyon*Config` pydantic model — cross-referencing
  `marslab/config/schema/terrain.py` shows `TerrainConfig` has no `canyon_depth`,
  `canyon_floor_width`, `canyon_total_width`, `canyon_curvature`, `canyon_craters`,
  `canyon_crater_radius_range`, `canyon_crater_depth_range` fields.
- **Problem:** Pydantic v2 by default ignores extra fields unless `model_config =
  ConfigDict(extra="forbid")` is set. None of the MarsLab schemas set that.
  Therefore every `canyon_*` key in `procedural_canyon.yaml` is **silently discarded**
  by the schema validator. Whatever is reading these values is either reading raw YAML
  dict (bypassing pydantic) or the procedural canyon generator hardcodes defaults. Either
  way, the YAML declares intent the schema cannot validate — a cardinal offense.
- **Fix:** Add a `ProceduralCanyonConfig` nested model mirroring `CaveConfig`'s pattern,
  then declare `canyon: ProceduralCanyonConfig | None = Field(...)` on `TerrainConfig`.
  Set `model_config = ConfigDict(extra="forbid")` on every pydantic model so any future
  typo fails loudly.

### 4.8 `procedural_canyon.yaml` lacks `seed` at scenario level
- Redundant with §4.7 — noting inconsistency: every other scenario has
  `terrain.seed: 42` at line ~49; `procedural_canyon.yaml:38` has it correctly, but it
  has no top-level `terrain.seed: 42` consistent with peers (`mars_env.seed: 42` is
  present).

### 4.9 `cave_lava_tube.yaml` — hardcoded skylight coordinates in comment
- **Location:** `configs/scenarios/cave_lava_tube.yaml:95-107`
- **Quote:** "For seed=42 skylight #4 lands at (181.2, 190.5) — spawn directly beneath"
  then `xy: [181.2, 190.5]`.
- **Problem:** The comment admits the spawn coordinates are tied to `terrain.seed=42`.
  Change the seed and the rover spawns in a wall. Nothing in the schema or loader
  cross-validates this. Domain-randomization across seeds breaks this scenario silently.
- **Fix:** Add a `spawn.mode: "beneath_skylight"` mode to the rover spawn spec and have
  the scenario loader recompute xy from the generated skylight layout. Or at minimum,
  raise a hard error when both `terrain.seed` and `rover.spawn.xy` are set on a cave
  scenario.

### 4.10 `cerberus_canyon.yaml` DEM coords unverified
- **Location:** `configs/scenarios/cerberus_canyon.yaml:36-40`
- **Quote:** `row: 8000, col: 2800, height: 500, width: 500`
- **Problem:** No test in the loader checks that the HiRISE DEM at
  `assets/terrain/dem/cerberus_fossae_converted` has at least `row + height = 8500` rows
  and `col + width = 3300` cols. If the DEM is smaller, the crop returns a smaller array
  or crashes depending on the GDAL wrapper. For the paper, you want a loader-time assert:
  "requested crop (8000:8500, 2800:3300) exceeds DEM bounds (N_rows × N_cols)".
- **Fix:** Add a loader-time bounds check in `dem_loader.py` when `dem_crop` is set.

---

## 5. tests/integration/

### 5.1 tests/integration/ IS EMPTY
- **Location:** `/home/hoyunkim/MarsLab/tests/integration/`
- **Contents:** `__init__.py` (0 bytes) and a `__pycache__` directory with a stale
  `.pyc`. No actual test files.
- **Location:** `.gitignore:73`
- **Quote:**
  ```
  # ROS2 플러그인 충돌로 인해서 pytest 실행 불가 > scripts/run_integration_test.py로 대체
  tests/integration/test_robot_spawn.py
  ```
- **Problem:** The integration test file `test_robot_spawn.py` is in `.gitignore`. The
  project has no integration tests in version control whatsoever. The README (§3.2)
  promises three integration entry points:
  > scripts/run_integration_test.py, scripts/run_scene_test.py,
  > scripts/run_multi_robot_test.py
  None of those exist under `tests/integration/` (the conventional path) and none of them
  run in CI. The CLAUDE.md-declared "11 integration tests" count is therefore
  unverifiable — if the tests live only on the author's laptop, they're not tests, they're
  folklore. This is a **reproducibility defect** for a paper codebase.
- **Fix:** (a) Remove the `.gitignore` exclusion. (b) Commit the actual integration
  entrypoint scripts. (c) Tag tests with `@pytest.mark.integration` and add a CI job that
  runs `pytest -m integration` on a self-hosted GPU runner or clearly marks the suite as
  `manual-only`. (d) If ROS2 plugin conflict is real, document the repro in a
  `tests/integration/README.md` including the failing pytest command and the workaround
  (`scripts/run_integration_test.py`) — then put that README in the repo, not hidden in
  `work_log/`.

### 5.2 Integration test directory has no visual inspection harness
- **Problem:** CLAUDE.md mentions `tests/visual_inspection/checklist.md` —
  `/home/hoyunkim/MarsLab/tests/visual_inspection/` exists but Reviewer did not descend
  into it (out of scope). Flagged only: there is no automated cross-link between
  integration-style tests and the visual_inspection checklist.

### 5.3 No test for configs/*.yaml validating end-to-end
- **Problem:** A 9-file scenario directory has no "load every YAML under configs/ and
  call `MarsLabConfig.model_validate(yaml)`; assert no ValidationError" test. This is a
  30-line test that would catch every §3, §4 finding above. Its absence is the single
  highest-value gap in the test suite.
- **Fix:** Add `tests/unit/test_config_schema.py::test_all_scenarios_validate` that
  globs `configs/**/*.yaml` and loads each through the aggregator.

---

## 6. Repo root — missing hygiene files

### 6.1 No .pre-commit-config.yaml
- **Location:** does-not-exist at repo root.
- **Problem:** CLAUDE.md declares black + ruff + pytest as the three required checks but
  nothing wires them into a git hook. Contributors who forget to run them push broken
  commits and wait for CI, wasting reviewer time. DELETE from any wishlist; add the file.
- **Fix:** Create `.pre-commit-config.yaml` with repos for `pre-commit-hooks` (trailing
  whitespace, end-of-file-fixer, check-yaml, check-added-large-files), `black`, `ruff`
  (with `--fix`), and optionally `yamllint`. Wire `pre-commit install` into the README
  setup step.

### 6.2 .coverage binary committed / not gitignored
- **Location:** `/home/hoyunkim/MarsLab/.coverage` (69 KB)
- **Location:** `.gitignore` — no entry for `.coverage` or `htmlcov/`.
- **Problem:** `.coverage` is a sqlite binary generated by coverage.py. It was modified
  at `Apr 24 16:12` — very recent — and is tracked (`git status` shows it under working
  tree; author should confirm). Committing this file pollutes diffs and leaks the author's
  local test layout.
- **Fix:** Add to `.gitignore`:
  ```
  .coverage
  .coverage.*
  htmlcov/
  coverage.xml
  ```
  and `git rm --cached .coverage` if tracked.

### 6.3 No LICENSE file (legal defect, see §1.2)
- Already flagged. Re-listing because it's the single highest-severity finding.

### 6.4 No CHANGELOG.md
- **Problem:** `pyproject.toml:3` declares `version = "0.1.0"`. A research codebase
  shipping a paper MUST track a changelog so reviewers can pin the exact revision against
  a paper claim. Every internal commit comment in the YAML/schema files references dated
  events ("R2-A1 (2026-04-22)", "Wk2 #6 (2026-04-14)") — that work belongs in
  CHANGELOG.md, not scattered across 30 files as commit archaeology.
- **Fix:** Adopt Keep a Changelog (https://keepachangelog.com) format; track
  Unreleased / 0.1.0 / 0.2.0 sections.

### 6.5 No CONTRIBUTING.md, no CODEOWNERS, no SECURITY.md
- **Problem:** Public Apache-2.0 repo with no issue-triage policy. For iSpaRo submission,
  SECURITY.md is low-priority, but CONTRIBUTING.md (how to run tests, how to format,
  where to file issues) is basic hygiene.
- **Fix:** 20-line CONTRIBUTING.md pointing at `pre-commit install`, the three-check
  commands, and the `work_log/` location for change history.

### 6.6 README references directories that don't match reality
- **Location:** `README.md:105-136` — project structure tree claims:
  ```
  ├── marslab/                    # Main Python package
  │   ├── environment/            # Mars physics (pure Python, no Isaac Sim)
  │   │   ├── sun_position.py     # Sun azimuth/elevation
  ```
- **Verification:** `ls marslab/` actually shows many more directories than documented
  (`runtime/`, `scene/`, `sensors/`, `sim/`, `ros2_bridge/`, `gui/`, `terrain/cave/`,
  etc.). The README tree is stale — drifted from the codebase. Prospective contributors
  get a misleading map.
- **Fix:** Regenerate the README tree via `tree -L 3 marslab/ | head -N`; commit
  consistently. Or delete the tree from README and link to an auto-generated docs page.

### 6.7 README references pip install classifiers that don't exist
- **Location:** `README.md:158-167` "Current Status" table. Claims "config/ Complete 27;
  environment/ Complete 30; terrain/ Complete 46". Yet `ls marslab/environment` would be
  needed to confirm. Out of scope — flagged because numbers are quoted, these are
  auditable claims, but there's no script producing them and no test asserting them. Stale
  on day 1.

### 6.8 README has Korean-only trailing commands uncommitted into docs structure
- **Location:** `README.md:177-181`
- **Quote:**
  ```
  scripts/isaac_python.sh scripts/phase1/run_stage3_monolithic.py --config configs/scenarios/jezero_flat.yaml
  # 여기서 YAML 파일 이름만 바꿔가면서 진행하면 됨.

  scripts/isaac_python.sh scripts/phase1/run_stage2.py --config configs/mars_env.yaml
  scripts/isaac_python.sh scripts/phase1/run_stage3_monolithic_new.py --config configs/scenarios/jezero_flat.yaml
  ```
- **Problem:** Dangling appendix after the "References" section with Korean comments and
  no section header. Reads like a scratch note that landed in the README by accident.
- **Fix:** Move to `docs/development.md` or delete; at minimum wrap in a "Developer notes"
  section with English translation.

### 6.9 .gitignore contains mixed English/Korean noise + typos
- **Location:** `.gitignore:42` — `*.txt`
- **Problem:** Ignoring **every .txt file** is almost always wrong. Kills
  `requirements.txt`, `authors.txt`, `README-legacy.txt`, etc. For a codebase that
  might ship a `LICENSE.txt` this is especially bad.
- **Location:** `.gitignore:66` — `내가궁금해서정리하는.md` (Korean: "md I'm organising out
  of curiosity")
- **Location:** `.gitignore:70` — `삭제대상/` (Korean: "to-be-deleted/")
- **Problem:** Personal-scratch names baked into a public repo's gitignore. Tolerable but
  noisy.
- **Fix:** Remove `*.txt`. Replace Korean personal entries with a single
  `# Developer scratch (personal)` block and scope names.

### 6.10 No `.editorconfig`
- **Problem:** Mixed-language team (Korean + English commentary), indentation/ending
  consistency is not enforced at editor level. Low priority but free hygiene.
- **Fix:** Add a 10-line `.editorconfig` with `indent_style = space`, `indent_size = 4`,
  `end_of_line = lf`, `insert_final_newline = true`.

---

## 7. Missing packaging hygiene (pre-commit, mypy, pip-audit)

This section collects the three explicit reviewer asks into one block.

### 7.1 pre-commit absent
- **Severity:** HIGH. §6.1.
- **Evidence:** No `.pre-commit-config.yaml` at repo root. No reference to `pre-commit`
  in `pyproject.toml` `[project.optional-dependencies]` or in `.github/workflows/*.yaml`.
- **Impact:** Every contributor must remember to manually run `black` + `ruff` before
  committing. The CLAUDE.md instruction "Every code change must pass all three checks
  before completion" is enforced by **culture only**, not by tooling. Predictable outcome:
  reviewer time wasted catching auto-fixable nits.
- **Fix:**
  1. Add `pre-commit` to `[project.optional-dependencies] dev`.
  2. Commit `.pre-commit-config.yaml`:
     ```yaml
     repos:
       - repo: https://github.com/pre-commit/pre-commit-hooks
         rev: v4.6.0
         hooks:
           - id: trailing-whitespace
           - id: end-of-file-fixer
           - id: check-yaml
           - id: check-added-large-files
             args: [--maxkb=1024]
       - repo: https://github.com/psf/black
         rev: 24.4.2
         hooks:
           - id: black
       - repo: https://github.com/astral-sh/ruff-pre-commit
         rev: v0.4.9
         hooks:
           - id: ruff
             args: [--fix]
     ```
  3. Document `pre-commit install` in README setup.
  4. Add a CI job `pre-commit run --all-files --show-diff-on-failure`.

### 7.2 mypy absent
- **Severity:** HIGH.
- **Evidence:** No `[tool.mypy]` in `pyproject.toml`. No `mypy.ini`. No mypy invocation in
  any CI workflow. No `py.typed` marker in `marslab/`.
- **Impact:** Public functions declare type hints (per CLAUDE.md mandate) but zero
  static checking occurs. Pydantic models are exercised at runtime only. Typos in
  type-annotated code like `list[int]` vs `List[int]`, `Optional[X]` vs `X | None` drift
  silently. Downstream users of the library get no IDE type support because there's no
  `py.typed` marker.
- **Fix:**
  1. Add to `pyproject.toml`:
     ```toml
     [tool.mypy]
     python_version = "3.10"
     strict = true
     warn_return_any = true
     warn_unused_ignores = true
     plugins = ["pydantic.mypy"]

     [[tool.mypy.overrides]]
     module = ["GDAL.*", "trimesh.*", "omni.*", "pxr.*", "isaacsim.*"]
     ignore_missing_imports = true
     ```
  2. Touch `marslab/py.typed` (empty file).
  3. Add to `[project.optional-dependencies] dev`: `mypy>=1.10`, `pydantic>=2.0`
     (already present — plugin auto-discovered).
  4. Add CI job:
     ```yaml
     - name: Type check
       run: mypy marslab/
     ```
  5. Expect ~50+ findings on first run; fix or `# type: ignore[specific-code]`.

### 7.3 pip-audit / safety absent
- **Severity:** MEDIUM.
- **Evidence:** No `pip-audit`, no `safety`, no `trivy`, no `osv-scanner` in any
  `.github/workflows/*.yaml`. No dependabot config (`.github/dependabot.yml`) either.
- **Impact:** Supply-chain vulns in `pyyaml`, `trimesh`, `pydantic` (CVE-2024-3568
  example) ship unnoticed. For a public Apache-2.0 codebase that downstream roboticists
  may install into production rover test harnesses, this is irresponsible. At minimum a
  weekly cron scan.
- **Fix:**
  1. Commit `.github/dependabot.yml`:
     ```yaml
     version: 2
     updates:
       - package-ecosystem: "pip"
         directory: "/"
         schedule:
           interval: "weekly"
       - package-ecosystem: "github-actions"
         directory: "/"
         schedule:
           interval: "weekly"
     ```
  2. Add `.github/workflows/security.yaml`:
     ```yaml
     name: Security
     on:
       schedule: [{cron: "0 3 * * 1"}]
       pull_request:
     jobs:
       audit:
         runs-on: ubuntu-latest
         steps:
           - uses: actions/checkout@<sha>
           - uses: actions/setup-python@<sha>
             with: {python-version: "3.12"}
           - run: pip install pip-audit
           - run: pip-audit --strict --requirement <(pip install -e ".[dev]" --dry-run)
     ```
  3. Optionally add `codecov/codecov-action` for test coverage signal — separate issue.

---

## 8. Summary of severity

| Severity | Count | Representative findings |
|---|---|---|
| CRITICAL | 2 | §1.2 (no LICENSE file), §5.1 (no integration tests in VCS) |
| HIGH     | 9 | §1.3 (unpinned deps), §1.4 (Python matrix miss), §1.7 (ruff narrow), §4.1 (mars_env dup ×7), §4.4/§4.5 (missing spacecraft/base assets), §4.7 (extra YAML keys silently dropped — no `extra="forbid"`), §5.3 (no YAML-validates-in-CI test), §7.1 (no pre-commit), §7.2 (no mypy) |
| MEDIUM   | 10+ | §2.1 (action SHA pinning), §2.5 (apt+pip cache), §3.1-§3.3 (unsourced magic numbers), §3.5 (tau dual-defaults), §4.2 (True vs true), §4.9 (cave spawn seed-coupled), §6.2 (.coverage committed), §6.6 (stale README tree), §7.3 (no pip-audit) |
| LOW      | 10+ | §1.1 (missing authors metadata), §1.5 (pytest markers), §2.3 (concurrency group), §2.6 (no test artifacts), §3.4 (physics_dt precision), §3.6 (dead albedo range), §3.7 (commented YAML), §4.3 (rock_sfd_k=0 dead fields), §6.5 (CONTRIBUTING), §6.8 (dangling README appendix), §6.9 (.gitignore `*.txt`), §6.10 (.editorconfig) |

---

## 9. Three-line summary

1. **CRITICAL:** No `LICENSE` file despite Apache-2.0 declaration in `pyproject.toml`; and
   `tests/integration/` contains only an empty `__init__.py` with `test_robot_spawn.py`
   in `.gitignore` — the "11 integration tests" claim in README is unverifiable.
2. **HIGH:** ~200 lines of duplicated `mars_env` + `rendering` blocks across 9 scenario
   YAMLs (no anchors, no includes), pydantic schemas lack `extra="forbid"` so
   `procedural_canyon.yaml` silently drops seven `canyon_*` keys, and packaging hygiene
   (pre-commit, mypy, pip-audit, Python matrix, SHA-pinned actions) is entirely absent.
3. **MEDIUM:** Unsourced calibration magic numbers (`sun_intensity_scale=30.0`,
   `dome_brightness_scale=5000.0`, `fog_density_scale=0.002`) cite a date instead of a
   derivation, mars_env and dynamic_atmosphere carry contradictory τ defaults, and
   `spacecraft_landing.yaml` + `mars_base.yaml` reference USD assets that do not exist —
   the YAMLs validate but the scenarios will crash at runtime.
