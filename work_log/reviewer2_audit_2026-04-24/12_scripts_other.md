# Reviewer 2 Audit — scripts/ (root + tools/)

**Scope:** `scripts/*.py`, `scripts/tools/*.py`, `scripts/isaac_python.sh`.
Excludes `scripts/phase1/` (audited elsewhere) and `scripts/ros2/` (out of
scope per task brief; a stray `scripts/ros2/scan_header_fix.py` does exist but
was not requested).

**Files reviewed (17):**
analyze_dem_regions.py, blender_generate_rocks.py, check_instruction_sync.py,
color_grade_mars.py, convert_dem.py, convert_urdf.py,
generate_pbr_from_photo.py, generate_rock_meshes.py, hello_isaac.py,
isaac_python.sh, run_marslab.py, visualize_atmosphere.py, visualize_cave.py,
visualize_dynamic_atmosphere.py, visualize_procedural.py,
visualize_scenario.py, visualize_terrain.py, tools/generate_instruction_index.py.

**Context for the verdict column.** CI (`.github/workflows/lint.yaml`,
`unit_tests.yaml`) runs `black`, `ruff`, `pytest tests/unit`. It does NOT invoke
any script under `scripts/`. There is no `.pre-commit-config.yaml` in the repo
root. Therefore every script here is either invoked manually by a developer or
called indirectly during an Isaac Sim session — nothing in this tree is
verified by automation.

---

## 0. Cross-cutting findings (the real story)

### 0.1 Massive duplication of matplotlib + os.makedirs + repo-root bootstrap

Ten files in `scripts/` import matplotlib, call `os.makedirs(..., exist_ok=True)`,
and then call `plt.subplots` / `fig.savefig(..., dpi=150)` /
`plt.close(fig)`. Six of them hardcode the output directory as `"work_log/..."`
or `work_log/scene_generation/...`. Four of them re-implement the
`REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))`
+ `sys.path.insert(0, REPO_ROOT)` boilerplate:

- `scripts/visualize_cave.py:18-20`
- `scripts/visualize_dynamic_atmosphere.py:21-23`
- `scripts/analyze_dem_regions.py:20-22`
- `scripts/run_marslab.py:26-28`
- `scripts/convert_dem.py:17` (variant: `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`)

**Problem:** This is Fowler "shotgun surgery" waiting to happen. Move output
root into the config (already have YAML everywhere — G5 preaches this, and
the devs cite G5 in other places) and put one
`scripts/_common.py` helper with `add_repo_to_sys_path()` and
`ensure_output_dir(subpath)`. The visualize_* group additionally duplicates:
- `--seed` / `--output` argparse flags (inconsistent defaults, some scripts
  have no argparse at all — `visualize_atmosphere.py`, `visualize_procedural.py`,
  `visualize_terrain.py` hardcode everything).
- `fig.tight_layout(); fig.savefig(..., dpi=150); plt.close(fig); print("Saved: ...")`
  — an identical 4-line tail in seven files.

**Fix:** Extract a `scripts/_viz_common.py` with:
```python
def save_figure(fig, rel_path: str, dpi: int = 150) -> str: ...
def standard_argparse(description: str) -> argparse.ArgumentParser: ...  # --seed, --output
```
Collapse visualize_atmosphere + visualize_terrain + visualize_procedural into
a single `visualize.py --mode {atmosphere,terrain,procedural,...}` — they are
literally the same skeleton, no code reuse. This is plain copy-paste, not "flat
P0".

### 0.2 Inconsistent output conventions

| Script | Output base |
|--------|-------------|
| visualize_atmosphere.py | `work_log/` |
| visualize_terrain.py | `work_log/` |
| visualize_procedural.py | `work_log/` |
| visualize_dynamic_atmosphere.py | `work_log/scene_generation/` (absolute via REPO_ROOT) |
| visualize_cave.py | `work_log/scene_generation/` |
| analyze_dem_regions.py | `work_log/scene_generation/` |
| visualize_scenario.py | `_workspace/` (default), caller-specifiable |
| color_grade_mars.py | `assets/materials/mars_terrain_graded` |
| generate_pbr_from_photo.py | `assets/materials/mars_hirise` |
| convert_dem.py | derived from DEM path |

No convention: outputs land under `work_log/`, `work_log/scene_generation/`,
`_workspace/`, and `assets/` depending on the author's mood that week. The
three `visualize_*` that write to `work_log/` collide with artifacts already
sitting at `work_log/atmosphere_visualization.png` (seen in `ls`). Running
these scripts silently overwrites prior runs with no versioning and no dated
subdir.

**Fix:** Adopt one convention (`work_log/figs/{script_stem}_{timestamp}.png`
or `work_log/figs/{script_stem}.png`) and route everyone through a single
helper.

### 0.3 "Comments-as-deodorant" — internal-term citations leak everywhere

The developers cite internal process artifacts in production code comments:

- `scripts/visualize_atmosphere.py:28` — `# R3 G5 literal migration only removes values that belong to the physics.`
- `scripts/visualize_dynamic_atmosphere.py:38-41` — `# R3 (2026-04-22) G5: solar constant and sol length come from YAML so the ... (see refactoring/_risks.md §3.8).`
- `scripts/color_grade_mars.py:5` — `Parameters configurable for iterative tuning (G5).`
- `scripts/generate_rock_meshes.py:5,7` — `Seed-based reproducibility (G5).` / `No Isaac Sim required — runs with system Python + trimesh (P3).`
- `scripts/run_marslab.py:1` — `(R6-2)` in the docstring.
- `scripts/run_marslab.py:75-86` — the `main()` docstring cites "R6-2" and "end-to-end Isaac Sim smoke test" process status.
- `scripts/check_instruction_sync.py:3` — `Phase A-4 of the Instruction-wiki plan.`
- `scripts/tools/generate_instruction_index.py:3,191-192` — `Phase A-3 ... Phase A-4 ... Phase B`.
- `scripts/isaac_python.sh:2,19,24,110,116,121` — `Wk1/Wk2 rescue Phase A1' (2026-04-15)`, `(G3: single-idea inspiration, no code copy.)`.

**Problem:** A new hire or external reader cannot resolve "R3", "R6-2",
"Phase A-4", "Wk1/Wk2 rescue Phase A1'", or "refactoring/_risks.md §3.8"
without the internal plan docs. That is textbook comments-as-deodorant: the
comment exists to reassure the PM, not to help the reader. Worse, the G3/G5/P3
citations are a form of reviewer-gaming: they are pre-emptive defense against
an internal rule rather than documentation of the code.

**Fix:** Strip all `(G3)` / `(G5)` / `(P3)` / `(R3)` / `(R6-2)` / `(Phase A-4)` /
`(Wk1/Wk2 rescue...)` tokens from scripts. If the seed argument matters,
document *what* it does, not that it satisfies rule G5. If the no-GDAL
property matters, say "This script runs without GDAL", not "(P3)".

### 0.4 Security overview

Positive:
- No `shell=True`, no `os.system`, no `eval`, no `exec`, no `pickle`,
  no `yaml.load` (only `yaml.safe_load` via pydantic loader — not in this
  tree).
- No `tempfile.mktemp`.
- Most subprocess usage is absent or safe.

Concerns (expanded in the per-file sections below):
- `generate_pbr_from_photo.py:39` sets `Image.MAX_IMAGE_PIXELS = None`
  globally — disables PIL's decompression-bomb guard, process-wide and
  persistent.
- `check_instruction_sync.py:110-116` runs `git diff --cached` via
  `subprocess.check_output`. Args are a static list, safe. But the Python
  error handler `except (subprocess.CalledProcessError, FileNotFoundError)`
  swallows arbitrary OSErrors and returns a human-readable "[git-error]"
  line — fine for a dev tool.
- `isaac_python.sh` has `set -e` (line 50). Manipulates `LD_LIBRARY_PATH`,
  `PYTHONPATH`, `PATH`, `CMAKE_PREFIX_PATH`, `PKG_CONFIG_PATH` with a
  shell-word-splitting loop. See per-file review below for the quoting
  issues.
- `convert_urdf.py:48` calls `save_as_stage(output_path)` where `output_path`
  is user-controlled. Isaac Sim's `omni.usd.get_context().save_as_stage` will
  happily overwrite any path it has permission for — no confirmation. Low
  risk, but a bare `os.path.abspath(args.output)` with no existence check
  will clobber an existing file silently.

### 0.5 Dead/orphaned references

- `scripts/isaac_python.sh:45-46` (comment) — `Usage: scripts/isaac_python.sh scripts/run_scene.py --config ...`. There is no
  `scripts/run_scene.py` in the repo. The referenced binary was either
  renamed, moved to `scripts/phase1/`, or deleted. The wrapper still works;
  the documentation lies.
- `scripts/run_marslab.py:101` — imports `scripts.phase1.run_stage3_monolithic_new`
  at the bottom of `main()`. This is actually a runtime import of a twin
  script. If `scripts/phase1/run_stage3_monolithic_new.py` is deleted or
  moved (see `git status -s` showing `D scripts/phase1/run_stage3_monolithic_new.py`
  in the session's git state), this whole entry-point dies with a
  `ModuleNotFoundError`. *Already broken in the working tree: the twin is
  listed as deleted by the user.*

---

## 1. Per-file verdicts

### 1.1 `scripts/visualize_atmosphere.py` — **dev-only tool**

**Line 17 / line 97**: `import os` + `os.makedirs("work_log", exist_ok=True)`
— hardcoded relative path. If the script is invoked from any directory other
than the repo root, it silently creates a `work_log/` folder in the user's
cwd. No repo-root resolution (unlike other scripts that at least try
`REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))`).

**Line 29–30**: `_PLOT_TAU_MIN = 0.05`, `_PLOT_TAU_SAMPLES = 100` — module
constants with a 4-line comment justifying why they are not in the config.
The comment is a "comments-as-deodorant" signal: explaining why you broke a
rule instead of either following the rule or rewriting the rule.

**Line 28**: `# R3 G5 literal migration only removes values that belong to the physics.` —
leaks internal process identifiers. Delete.

**Line 38**: `tau_hi = cfg.mars_env.dust_opacity_range[1]` — indexes into a
tuple without validation. If the schema ever changes `dust_opacity_range` to
a single-value dict or a list of length 1, this explodes with
`IndexError`. A named accessor would be clearer. Not a bug today, but
fragile.

**Line 86**: `total = [d / (1.0 - df) if df < 1.0 else d for d, df in zip(direct_part, diffuse_frac)]` —
`df < 1.0` is a magic branch. At `df = 1.0`, total equals direct beam only,
which is physically wrong (100% diffuse means total = diffuse). Also, `df = 1.0`
is reachable at high tau in the COMIMART fit? If not, delete the guard. If
yes, this silently reports a wrong total.

**Line 70**: `compute_sky_dome_params(t, "assets/sky/hdri/")` — second
argument is a literal path. Other scripts resolve the same path via
`os.path.join(REPO_ROOT, "assets", "sky", "hdri")`. Breaks when cwd != repo
root.

**No argparse** — cannot override output path, cannot pick config path
(`"configs/mars_env.yaml"` on line 35 is hardcoded relative). This is a
throwaway dev figure, but it is also the script the paper may eventually
cite.

**Verdict:** dev-only tool today; **production-path if** the figure ends
up in the paper. Needs (a) argparse, (b) repo-root resolution, (c) internal
citation stripped.

---

### 1.2 `scripts/visualize_cave.py` — **dev-only tool**

**Line 18–20**: `REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))`
+ `sys.path.insert(0, REPO_ROOT)`. Duplicated verbatim in four scripts.

**Line 22**: `from marslab.terrain.cave_generator import generate_cave_mesh  # noqa: E402`.
Module path does not match git status (`M marslab/terrain/cave/breakdown.py`,
`M marslab/terrain/cave/features.py`, `M marslab/terrain/cave/geometry.py`,
`M marslab/terrain/cave/mesh.py`). There is a `cave_generator` facade
somewhere, but the audit cannot confirm without reading marslab/terrain — if
the facade is deleted, this script breaks. **Fragile dependency on a facade
that may be mid-refactor.**

**Line 25–41 `parse_args`**: Good. But `--domain` is type `int`; it is passed
as `domain_size=(args.domain, args.domain)`. Negative or zero values are not
validated (`argparse` accepts `--domain=-5`). `generate_cave_mesh` may
behave unpredictably.

**Line 215–223 (OBJ export)**: `trimesh.util.concatenate([tube, floor, surface] + result["skylight_meshes"] + result["debris_cones"])`
then `.export(obj_path)`. Export path is derived by `.replace(".png", ".obj")`
— if the user passes `--output foo.PNG` (capitalized) the replace fails and
the OBJ lands with the wrong suffix. Use `Path(args.output).with_suffix(".obj")`.

**Line 216**: `import trimesh as tm` is inside the `if args.export_obj:`
block. Good lazy-import pattern.

**Line 85–94 `_setup_panel`**: Nested helper is fine. But it accepts `ax`
untyped.

**Line 149**: `mid_y = np.median(tv[:, 1])` — uses median as the
cross-section center. If the mesh is asymmetric about Y, this is not the
tube midpoint; the cross-section is silently off. A docstring would help.

**Verdict:** dev-only tool. Generated figure may appear in the paper (cave
scenario illustration). Needs argparse validation and facade-path audit.

---

### 1.3 `scripts/visualize_dynamic_atmosphere.py` — **dev-only tool**

**Line 31–34**: `OUTPUT_DIR` and `OUTPUT_PNG` are module-level constants.
No argparse at all. Running twice silently overwrites the PNG with no
metadata stamp.

**Line 38–41**: Process-term leak.

**Line 77–86 (sky swatches)**: `min(t, 0.999)` magic number — a 3-digit
clamp to avoid a division-by-zero-like issue at `t=1.0`. No comment
explaining it. Reader must guess. Also: if `compute_sky_dome_params` has a
real singularity at `t=1.0`, *fix the callee*, do not shim it at the caller.

**Line 56–58**: `tau_sine = [compute_tau("sine", t, base_tau=0.5, amplitude=0.3, period_fraction=1.0) for t in t_values]`
— magic numbers `0.5`, `0.3`, `1.0` inline. G5 is preached elsewhere in this
very script (line 38) yet violated ten lines later.

**Line 153–158 `fig.suptitle`**: Hardcodes "Jezero crater 18.4 deg N" in the
plot title. If a user swaps the config to Gale crater, the caption lies.

**Verdict:** dev-only. Figure may appear in paper; if so the suptitle lie
and the absent argparse are blockers.

---

### 1.4 `scripts/visualize_procedural.py` — **delete candidate**

**Line 18–22**: Only three hardcoded presets (`flat`, `crater`, `hills`) with
k values `0.03`, `0.06`, `0.04`. No argparse. No --seed. `seed=42` hardcoded
on line 30 and line 35.

**Line 63**: `fig.savefig("work_log/procedural_terrain_visualization.png", dpi=150)` —
hardcoded output.

This script looks like an early prototype kept around "in case someone wants
to see procedural terrain". `visualize_scenario.py` (1.6 below) is strictly
more general — it reads a scenario YAML and supports DEM *or* procedural
sources (pending the schema). If procedural scenarios are rendered via
`visualize_scenario.py configs/scenarios/procedural.yaml`, this script is
dead.

**Verdict:** delete candidate. Confirm the newer `visualize_scenario.py`
handles procedural, then drop this file.

---

### 1.5 `scripts/visualize_scenario.py` — **production-path (figure source)**

The most structurally honest script in this tree. Real pydantic schema usage,
real docstrings, `sys.exit(main(sys.argv))` with a non-zero exit on missing
args.

**Line 67–70**: `_slope_map` returns `np.degrees(np.arctan(np.sqrt(gx*gx + gy*gy)))`.
Uses `np.gradient` with `resolution` as spacing — correct. `.astype(np.float32)`
before gradient computation is fine.

**Line 91–96 rock sampling**: passes `terrain.rock_sfd_k`,
`terrain.rock_diameter_range`, `terrain.seed`. Seeds propagated. Good.

**Line 120–122**: `rx, ry, _ = config.robots[0].spawn_position` — IndexError
if `config.robots` is empty. No guard — only the `if config.robots:` check
on line 119 catches the empty case, but `config.robots[0]` immediately
follows. Safe only because of the short-circuit. Readable, but could
`robots = config.robots; if robots: ...`.

**Line 156**: `cfa_theory = [compute_cfa(terrain.rock_sfd_k, float(d)) for d in d_theory]` —
no Isaac Sim, no GPU. Good offline testability.

**Line 193 `main(argv: list[str])`**: `argv[1]` / `argv[2]` positional
handling without argparse. Passing `--help` gives a surprise exit-2 (the
`if len(argv) < 2` branch is triggered first). Inconsistent with the
other scripts that use `argparse`. A real tool.

**Line 180**: `os.makedirs(os.path.dirname(output_png) or ".", exist_ok=True)` —
handles the "no parent dir" case. Defensive.

**Verdict:** production-path if cited by paper scenario figures. Would
benefit from (a) argparse over `sys.argv` slicing, (b) explicit `--dpi`.

---

### 1.6 `scripts/visualize_terrain.py` — **delete candidate**

**Line 21**: `REAL_DEM_PATH = "assets/terrain/dem/jezero_crater.tif"` —
hardcoded path. No fallback directory search. If the user converted the DEM
to the per-scenario `_converted/` numpy format (which is the whole point of
`convert_dem.py`) this script *silently falls back to synthetic random data*
(line 37: `rng.uniform(-2500, -2400, (100, 100))`). A reader who runs this
post-conversion gets a plausible-looking but fabricated DEM plot. That is a
correctness trap, not a visualization tool.

**Line 47–49**: `k = 0.05`, `d_range = (0.05, 3.0)`, `seed = 42` — hardcoded.
G5 violation.

This is `visualize_scenario.py` with the scenario hardcoded to "Jezero
before we had scenario YAMLs". **Subsumed.**

**Verdict:** delete candidate. `visualize_scenario.py` does everything this
does, correctly, with a config.

---

### 1.7 `scripts/convert_dem.py` — **production-path (asset pipeline)**

This one feeds into the scenario pipeline. A real tool.

**Line 17**: `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` —
the bootstrap pattern again. Extract.

**Line 76–79 `assert` block**: Round-trip verification uses `assert`
statements. `python -O` strips asserts, turning silent data corruption into
an accepted output. Use `if not ...: raise RuntimeError(...)`.

**Line 83**: `print(f"  Round-trip verification: PASSED | ...")` — the tool
reports success to stdout only. No structured exit signal, no JSON. Fine
for a dev tool, weak for CI.

**Line 42**: if `config.terrain.source != "hirise"` the script *silently
returns without error*. It prints `Nothing to convert.`. If a user
accidentally points `--config` at a procedural scenario, they get a
zero-exit and nothing happens. This behaviour should at least exit with a
non-zero code to prevent silent success in CI-like pipelines.

**Path validation:** no check that `config.terrain.dem_path` is absolute or
that it is within the repo / asset root. A malicious scenario YAML could
reference `../../../../etc/passwd.tif`; GDAL would fail open with a
TIFF-read error, but the Python tool would still `save_converted_dem` to
any `output_dir` the config picks. Low impact (config is user-authored),
but worth a sanity check if scenarios ever come from untrusted sources.

**Verdict:** production-path for DEM preprocessing. Needs (a) `assert` →
`raise`, (b) non-zero exit on "nothing to convert".

---

### 1.8 `scripts/convert_urdf.py` — **production-path (asset pipeline)**

Simplest and tightest script in this set.

**Line 14**: `from isaacsim import SimulationApp`. Correct module path.

**Line 32**: `parser.add_argument("--urdf", required=True, ...)`. Good.

**Line 33–35**: `import_config.merge_fixed_joints = False`, `import_config.fix_base = False`.
Hardcoded. No `--fix-base` / `--merge-fixed-joints` flag. The user memory
(`[Mars rover USD source]`) says the rover is converted once offline; but
for other URDFs (rotorcraft, quadruped, etc., v2.0+ work) the defaults may
be wrong. Today: fine. Tomorrow: footgun.

**Line 43**: `robot_path = result if isinstance(result, str) else result[1]`.
Defensive handling of Isaac Sim's `execute()` return tuple variance. Good.

**Line 48**: `omni.usd.get_context().save_as_stage(output_path)` — no check
that `output_path` exists. Will silently overwrite. Add an `if os.path.exists(output_path) and not args.force: ...` guard.

**No docstrings on main().** `def main() -> None: """Convert URDF to USD."""` —
one line. For an Isaac Sim-dependent script this is thin; caller should at
least see the expected Isaac Sim version.

**Verdict:** production-path for the rover USD. Small tool, acceptable.

---

### 1.9 `scripts/analyze_dem_regions.py` — **dev-only tool**

**Line 34–35**: `WINDOW_SIZE = 200`, `STRIDE = 20` — magic constants at
module scope. No argparse override.

**Line 200 `main()`**: No argparse. Entire pipeline runs with hardcoded
`DEM_DIR`, hardcoded window size, hardcoded "top 3" candidates (line 110
default `n: int = 3`, line 217 `n=3`).

**Line 113**: `w["flat_score"] = w["dz"] + w["mean_slope"] * 2.0` — the
magic weighting factor `2.0` is buried inside a scorer with no docstring
justifying the choice. Cannot tune without editing source. G5 violation
again.

**Line 154–178 `_draw_candidates`**: Nested helper creates matplotlib
patches. Good.

**Line 239–246**: Prints a recommended crop command. Useful, but the output
format is loose text. A `--emit-yaml` mode that dumps a scenario YAML stub
would actually close the loop.

**Verdict:** dev-only tool. One-shot analysis. Should stay in repo, but
add argparse and emit YAML.

---

### 1.10 `scripts/color_grade_mars.py` — **delete candidate / v2.0 only**

**Line 20–29 argparse**: Six tunables. Every one is a magic Mars-regolith
color-grading knob.

**Line 47–54**: Applies per-channel scaling + saturation + brightness
via PIL. No unit test. No determinism proof (PIL version dependency).

**The real question:** is this script used for the v1.0 paper, or is it a
v2.0 photorealism asset tool? Based on the script docstring ("Earth PBR
texture → Mars color grading", assets/materials/mars_terrain_graded output)
and the user's stated v1.0 scope ("good-enough rendering + strong
robotics"), this is v2.0 prep. v1.0 scope says "Do NOT chase photorealism
in v1.0." — see CLAUDE.md "What NOT To Do #2" — and yet the repo carries a
color-grading knob script. If it is not run as part of the paper experiment
pipeline, it is v1.0 clutter.

**Line 5**: `(G5)` citation in the docstring — deodorant.

**Verdict:** delete candidate for v1.0; revisit for v2.0. Alternately, move
to `scripts/v2_photorealism/` if the dev team wants to preserve it.

---

### 1.11 `scripts/generate_pbr_from_photo.py` — **dev-only / v2.0**

**Line 39**: `Image.MAX_IMAGE_PIXELS = None`. This *globally and
persistently* disables PIL's decompression-bomb protection. The setting
persists across process imports. For a batch-conversion tool the comment
says "Allow large HiRISE images", but it also opens a process-level DoS if
the input is attacker-controlled. Low impact for local dev use; bad hygiene.
Set to a generous-but-finite integer instead (e.g. `Image.MAX_IMAGE_PIXELS = 500_000_000`).

**Line 26 `mars_tint: tuple[float, float, float] = (0.72, 0.45, 0.30)`** —
magic default tint. No source citation for why these RGB scalars represent
"Mars regolith". `color_grade_mars.py` has its own different magic values.
The two scripts disagree on what "Mars color" is, with no shared config.
G5 violation and inter-script inconsistency.

**Line 70–93 `albedo_to_normal`**: Sobel-gradient to tangent-space normal,
`np.full_like(gx, 255)` for B channel — "Z (up)" labeled in the comment.
For a real OpenGL normal map, the Z component should be computed from
`sqrt(1 - x^2 - y^2)` after renormalization, not clamped to 255. This
produces an invalid normal map that happens to look plausible in a shader
preview.

**Line 80–81**: Sobel gradients are multiplied by `strength` before the
`+128` bias. If `strength * gx` exceeds 127, the clip on line 88 saturates.
No documentation of the valid `strength` range.

**Line 96–116 `albedo_to_roughness`**: "Brighter areas = rougher" — inverts
the intuitive mapping for dust-covered regolith (bright = dust = smoother).
Physics-backwards with no citation. Either wrong or load-bearing in some
specific visual calibration; either way, no way to know.

**Line 121–133 argparse**: `--input` defaults to `os.path.expanduser("~/Downloads/jezero_ortho_red_c.jp2")`.
The script bakes a specific developer's file path into production code. Any
other developer's machine fails with `FileNotFoundError`. This is a red
flag — the script was written on one laptop and never de-personalized.

**Verdict:** delete candidate for v1.0. Looks like v2.0 asset-gen
experimentation. If retained: fix decompression-bomb guard, Z-normal
math, developer-home path, mars_tint consistency with
`color_grade_mars.py`.

---

### 1.12 `scripts/generate_rock_meshes.py` — **superseded / delete candidate**

**Line 17 `generate_rock_mesh`**: Full numpy-trimesh implementation of
icosphere-deformation.

**But** `scripts/blender_generate_rocks.py` exists and explicitly removes
the trimesh rocks at line 99–102:
```python
for f in os.listdir(output_dir):
    if f.startswith("rock_proto_") and f.endswith(".obj"):
        os.remove(os.path.join(output_dir, f))
        print(f"  Removed old: {f}")
```

So the Blender variant actively *deletes* the output of this script on
every run. Two scripts fighting over the same output directory is a broken
pattern. Either commit to Blender (higher quality per docstring) and delete
this file, or commit to trimesh (no Blender dependency) and delete the
Blender variant.

**Line 5**: `(P3)` deodorant.

**Verdict:** delete candidate — superseded by the Blender variant per the
Blender script's own behaviour.

---

### 1.13 `scripts/blender_generate_rocks.py` — **dev-only tool**

**Line 15**: `import bpy`. Cannot be unit-tested without Blender. Cannot be
imported at all outside Blender's embedded Python.

**Line 32**: `random.seed(seed)` — uses the stdlib `random` module, not
`numpy.random.default_rng`. The rest of the codebase uses numpy RNGs. This
script's determinism is not cross-compatible with the rest of the seed
plumbing.

**Line 48–62 `_apply_displace`**: Inside `generate_rock`, closure over
`obj`. Nested function fine, but the `tex_type == "CLOUDS"` vs else branch
is a magic string. Pass structured enum.

**Line 99–102**: Deletes files on disk. Destructive. No `--dry-run`. No
check for write permissions. A user running this expecting "just preview"
gets old files deleted.

**Line 51–62**: Multiple `random.uniform(...)` and `random.randint(...)`
calls inside `_apply_displace` use the module-global `random` state, so the
outer `random.seed(seed)` on line 32 governs them — OK — but also governs
the main-loop `random.uniform(0.5, 1.5)` calls on line 41–43. So two rocks
generated in sequence with different seeds share the same interleaved RNG
state, making the second rock depend on how many RNG calls the first one
used. Any change to `_apply_displace`'s internal RNG consumption silently
re-numbers every subsequent rock. This is the classic stateful-RNG footgun.

**Line 79–85 `bpy.ops.wm.obj_export`**: Kwarg `export_selected_objects=True`
depends on the selection state set earlier. The `clear_scene()` at the top
of `generate_rock` does a `SELECT_ALL + delete`, then `primitive_ico_sphere_add`
implicitly selects the new object. Fragile ordering dependency.

**Verdict:** dev-only tool. Usable, but needs per-rock numpy RNG and the
destructive deletion guarded.

---

### 1.14 `scripts/hello_isaac.py` — **delete candidate**

**Full file is 30 lines.** It is literally a "hello world" demo: create a
SimulationApp, print stage handle, step 10 times, close. No docstring
beyond "Verifies ... is working". No assertions. No exit code.

If it *passes*, it proves the developer's Isaac Sim is installed. If it
*fails*, it proves nothing about MarsLab, just about Isaac Sim.

**Is it actively useful?** Only for first-time onboarding ("does my Isaac
Sim work at all?"). After that it is dead code. A single integration smoke
test (`pytest tests/integration/test_isaac_boot.py`) would subsume this.

**Line 1–10 docstring** claims it verifies: SimulationApp launches, USD
stage accessible, simulation steps run, clean shutdown. But it does not
assert any of those — it only prints. A reader running the script and
seeing no output could not tell if it verified anything.

**Verdict:** delete candidate. If retained for onboarding, make it a
pytest-integration test that actually fails loudly.

---

### 1.15 `scripts/run_marslab.py` — **production-path (entry point), currently BROKEN**

**Line 101**: `from scripts.phase1.run_stage3_monolithic_new import main as _twin_main`.
The file `scripts/phase1/run_stage3_monolithic_new.py` is listed in the
working-tree git status as `D` (deleted). This entry point is therefore
dead in the current working tree — running
`scripts/isaac_python.sh scripts/run_marslab.py --scenario ...` will
ModuleNotFoundError.

**Lines 1–17 docstring**: "Thin CLI entry point for the MarsLab v1.0 Stage 3
rover runtime (R6-2). This wrapper is the *modular* counterpart to ...
``scripts/phase1/run_stage3_monolithic.py`` (frozen Oracle)." Cites
internal identifiers `R6-2` and `Oracle`. Reader-hostile.

**Lines 86–105**: The entire `main()` mutates `sys.argv` and
re-dispatches. That is a code smell: it means "we promised a modular entry
point in the plan, but we have not actually written it yet, so we are
forwarding to the monolithic one and pretending". The docstring admits as
much: "this function re-dispatches into the twin's main()". A thin
dispatcher wrapped around a deleted file.

**Lines 98–105 try/finally argv swap**: Minor but correct — restores
`sys.argv` on exception path.

**Line 92**: `forwarded: List[str] = ["run_marslab", "--config", scenario]`.
The twin's argparse receives `--config` while the wrapper accepts
`--scenario`. That is two names for the same thing *in the same repo*,
at two layers of entry point. Users will get confused. Pick one.

**Verdict:** currently BROKEN (deleted dependency in working tree).
Production-path intention. Needs: (a) either restore the twin or inline
the real logic, (b) rename args consistently, (c) strip R6-2 etc.

---

### 1.16 `scripts/check_instruction_sync.py` — **orphan tooling, not CI-enforced**

Cross-check against CI: `.github/workflows/lint.yaml` runs only `black`
and `ruff`. `unit_tests.yaml` runs only `pytest tests/unit`. No workflow
runs `check_instruction_sync.py`. No `.pre-commit-config.yaml` exists in
the repo root. **Therefore this tool is not enforced anywhere.** It is a
developer-run ritual.

**Line 107–126 `check_staged_pairs`**: Runs `git diff --cached`. Would be
useful as a pre-commit hook. No pre-commit config exists. Dead tooling
in practice.

**Line 20–21 docstring (exit codes)**: Claims `0 — all good / 1 — drift
detected / 2 — tool error`. But the code actually returns `1` from
`main()` on drift (line 153) and does not have a code path that returns
`2`. `check_staged_pairs` *returns* a `[git-error]` string inside the
error list, which then flows through the normal error-reporting path and
still exits `1`. So the docstring lies about exit code 2.

**Line 42**: `SRC_ROOT / md.relative_to(WIKI_ROOT).with_suffix(".py")`.
Path-reversibility depends on the twin convention. If a `.py` file has a
`.` in the stem (say `cave_geometry.v2.py`), `with_suffix(".py")` replaces
the LAST suffix, silently producing `cave_geometry.v2` → `cave_geometry.md`.
Edge case, not a real bug today.

**Line 34**: `FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)` —
regex-parses YAML frontmatter. For YAML with `---` inside a string value,
this mis-parses. Use a real YAML parser or live with the brittleness.

**Line 51**: `except (OSError, UnicodeDecodeError): return None`. Silently
swallows read errors. A corrupt markdown file produces an "orphan" error
indistinguishable from a genuinely-missing frontmatter — the user will
edit frontmatter that already exists and wonder why the tool still
complains.

**Verdict:** dev-only tool, not CI-enforced = effectively dead tooling.
Either wire into CI or delete.

---

### 1.17 `scripts/tools/generate_instruction_index.py` — **orphan tooling, not CI-enforced**

Same situation as `check_instruction_sync.py`: not referenced by any CI
workflow, not in pre-commit, lives on the developer's manual re-run
ritual. As a documentation-generation tool it is fine craftsmanship, but
MarsLab's `CLAUDE.md` explicitly says "NEVER create documentation files
(*.md) or README files unless explicitly required". This script's sole
purpose is to generate `Instruction/INDEX.md`. Tension with the project
principle.

**Line 29–37 `read_frontmatter`**: Regex-based frontmatter parser again.
Same brittleness as `check_instruction_sync.py`; `FIELD_RE` does not
handle nested YAML, multi-line values, or quoted colons.

**Line 60**: `bool(re.search(r"\b(from|import)\s+(isaacsim|omni|pxr|carb)\b", src))`.
Uses regex to parse Python imports. Why not `ast.walk` over an
`ast.Module`? The AST parse already happens on line 49 (`ast.parse(src)`).
Using AST would catch `from isaacsim.core import SimulationApp` while
regex catches it by luck. Minor, but illustrative of unnecessary
dual-parsing.

**Line 66–77 `progress_bar`**: Builds a unicode progress bar. Cute; not
load-bearing.

**Line 99, 100**: Embeds the file path `scripts/tools/generate_instruction_index.py`
into the generated `INDEX.md` frontmatter. If the tool moves, the
generated INDEX.md becomes self-contradicting until rerun.

**Line 191–195**: Writes hardcoded Korean+English "next steps" into the
generated INDEX. Mixes tool output with editorial content.

**Verdict:** orphan tooling. CLAUDE.md prohibits proactive .md generation
— this tool *exists to generate .md*. Either whitelist it or delete.

---

### 1.18 `scripts/isaac_python.sh` — **production-path (wrapper), works but brittle**

`set -e` is present (line 50). Good.

**Line 56–77 `_purge_colon_path`**: Uses `IFS=':'` + `for entry in $old_val`
word-splitting. The value is not quoted inside the loop:
```bash
for entry in $old_val; do
```
If any path component in `LD_LIBRARY_PATH` contains a space or glob
metachar (unlikely for `/opt/ros/jazzy` but possible if the user has
custom paths), the word-splitting plus unquoted expansion will corrupt it
or trigger glob expansion. Defensively:
```bash
local IFS=':'
read -ra entries <<< "$old_val"
for entry in "${entries[@]}"; do
```

**Line 67**: `if [[ "$entry" != "$bad_prefix"* ]]; then` — correct prefix
test under `[[`.

**Line 79**: `_BAD_PREFIX="/opt/ros/jazzy"` is hardcoded. Not configurable
via env. If the user installs ROS 2 at `/opt/ros/humble`, the wrapper does
nothing. The docstring admits the script targets Jazzy specifically;
hardcoding the prefix just means every non-Jazzy user gets no purge and a
surprise segfault.

**Line 86–94 `unset` block**: Good.

**Line 98**: `ISAAC_SIM_PATH="${ISAAC_SIM_PATH:-$HOME/isaacsim}"`. Good
override path.

**Line 123–128**: Hardcodes `exts/isaacsim.ros2.bridge/jazzy/lib` — same
Jazzy assumption. If Isaac Sim ships a humble bundle, this path does not
exist and the script aborts with the helpful "Install Isaac Sim 5.x" error
on line 126. OK for v1.0 but not future-proof.

**Line 131–141 preflight echo**: Sends to stderr (good, non-colliding with
stdout). Good diagnostic.

**Line 143**: `exec "$ISAAC_PY" "$@"` — proper exec with quoted args.
Good.

**Line 45–46 docstring**: `Usage: scripts/isaac_python.sh scripts/run_scene.py ...`
— there is no `scripts/run_scene.py` in the repo. Documentation lies
(Section 0.5).

**Line 121**: `(G3: single-idea inspiration, no code copy.)` — deodorant.

**Verdict:** production-path wrapper for every Isaac Sim run. Works, but
hardcoded `/opt/ros/jazzy` + `jazzy` bundle assumptions make it
version-fragile. Usage example points at a deleted script.

---

## 2. Summary table

| File | Kind | Verdict |
|------|------|---------|
| visualize_atmosphere.py | figure | (a) dev-only; needs argparse + repo-root; internal citation to strip |
| visualize_cave.py | figure | (a) dev-only; cave_generator facade fragile mid-refactor |
| visualize_dynamic_atmosphere.py | figure | (a) dev-only; hardcoded Jezero suptitle lies on other configs |
| visualize_procedural.py | figure | (c) delete candidate (subsumed by visualize_scenario.py) |
| visualize_scenario.py | figure | (a) production-path; strongest of the set |
| visualize_terrain.py | figure | (c) delete candidate (silently falls back to synthetic) |
| convert_dem.py | asset pipeline | (a) production-path; assert→raise, non-zero exit on no-op |
| convert_urdf.py | asset pipeline | (a) production-path; add --force / existence guard |
| analyze_dem_regions.py | dev tool | (b) dev-only; no argparse, magic weights |
| color_grade_mars.py | v2.0 tool | (c) delete candidate for v1.0; v2.0 photorealism scope |
| generate_pbr_from_photo.py | v2.0 tool | (c) delete candidate for v1.0; decompression-bomb off, bad Z-normal, developer-home path |
| generate_rock_meshes.py | asset gen | (c) delete candidate (superseded by blender variant that deletes its output) |
| blender_generate_rocks.py | asset gen | (b) dev-only; stdlib RNG footgun, destructive delete |
| hello_isaac.py | demo | (c) delete candidate; no assertions, zero value post-onboarding |
| run_marslab.py | entry point | (a) production-path, currently BROKEN (twin deleted in working tree) |
| check_instruction_sync.py | meta-tooling | (c) orphan; not CI-enforced = effectively dead |
| tools/generate_instruction_index.py | meta-tooling | (c) orphan; not CI-enforced + CLAUDE.md prohibits proactive md |
| isaac_python.sh | wrapper | (a) production-path; brittle Jazzy hardcodes, lies about script names |

---

## 3. Reviewer 2 hit list (what a paper committee would jump on)

1. **A production entry point (`run_marslab.py`) imports a module that is
   `D`-deleted in the current working tree.** Reproducibility claim cannot
   survive this. (§1.15)
2. **Two scripts (`visualize_terrain.py`, `visualize_procedural.py`) silently
   produce synthetic/fake data when expected inputs are missing.** A reviewer
   running the visualization scripts post-clone gets *fabricated figures* with
   a single `print("Real DEM not found, using synthetic data")` as the only
   tell. (§1.6)
3. **Four nearly-identical visualize_* scripts, no shared helper.** Claiming
   "Extreme Modularity" while maintaining 4× copy-paste scaffolding is a
   contradiction. (§0.1)
4. **`generate_pbr_from_photo.py` disables PIL decompression-bomb guard
   process-wide** (Image.MAX_IMAGE_PIXELS = None) and bakes a specific
   developer's `~/Downloads/...` path as the default input. (§1.11)
5. **Two orphan "meta-tooling" scripts** (`check_instruction_sync.py`,
   `tools/generate_instruction_index.py`) not invoked by any CI workflow.
   Either wire in or delete. (§1.16, §1.17)
6. **Internal process identifiers (`R3`, `R6-2`, `Wk1/Wk2 rescue Phase A1'`,
   `G3`, `G5`, `P3`, `Phase A-4`, `refactoring/_risks.md §3.8`) leaked into
   production script comments and docstrings.** A reader without the internal
   plan docs cannot decode these. (§0.3)
7. **`hello_isaac.py` has zero assertions** and cannot verify the thing its
   docstring claims to verify. (§1.14)
8. **`isaac_python.sh` hardcodes `/opt/ros/jazzy` and the jazzy bundle path
   of Isaac Sim 5**, so the wrapper only works for the exact environment the
   author has. Also documents a `scripts/run_scene.py` that does not exist.
   (§1.18)

---

## 4. Three-line summary

**Counts:** 18 files audited (17 Python + 1 shell). Production-path: 6 (visualize_scenario, convert_dem, convert_urdf, run_marslab, isaac_python.sh, plus visualize_atmosphere if used for paper). Dev-only: 4 (visualize_cave, visualize_dynamic_atmosphere, analyze_dem_regions, blender_generate_rocks). Delete candidates: 8 (visualize_procedural, visualize_terrain, color_grade_mars, generate_pbr_from_photo, generate_rock_meshes, hello_isaac, check_instruction_sync, tools/generate_instruction_index).

**Criticals:** 1 broken entry point (`run_marslab.py` imports a deleted file), 2 figures silently fabricate data on missing inputs, 2 "meta-tooling" scripts orphaned from CI, 1 decompression-bomb guard globally disabled.

**The pattern:** massive visualize_* duplication with zero shared helper, process-term comments ("R3 G5", "Wk1/Wk2 rescue Phase A1'") across a third of the files, and a split between "real tools feeding the paper pipeline" (convert_dem, convert_urdf, visualize_scenario, isaac_python.sh) vs "dev clutter that should have been deleted three sprints ago" (hello_isaac, visualize_terrain, generate_rock_meshes, color_grade_mars). Prune aggressively before submission.
