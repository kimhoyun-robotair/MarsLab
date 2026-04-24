# Reviewer 2 Audit — `marslab/terrain/` (core, non-cave)

## 메타

- **Date:** 2026-04-24
- **Scope:** 9 top-level Python files in `marslab/terrain/`, excluding cave.
  Specifically: `__init__.py`, `dem_loader.py`, `elevation_loader.py`,
  `material_applicator.py`, `mesh_builder.py`, `procedural_generator.py`,
  `rock_instancer.py`, `rock_placer.py`, `terrain_loader.py`.
- **Role:** Hostile external peer reviewer. I have not read CLAUDE.md,
  PLAN.md, `.claude/`, or `work_log/`. Internal jargon in docstrings
  ("Wk1 #40", "R3-A3", "Option-B facade", "P3", "G5", "Oracle") is a
  **comments-as-deodorant** smell and is flagged below on its own.
- **Method:** Read every line of every file. Cross-checked with grep
  for duplication patterns and dtype consistency. Ran a small numpy
  experiment to validate the `np.gradient` axis ordering claim.
- **Severity counts:** CRITICAL 3 · HIGH 6 · MEDIUM 8 · LOW 7 ·
  DELETE 2 · WATCHLIST 4.

---

## CRITICAL

### C1. `dem_loader.crop_dem` silently miscomputes `origin_y` for north-up DEMs (and most HiRISE tiles)

**File / line:** `marslab/terrain/dem_loader.py:217-218`

```python
cropped_meta["origin_x"] = origin_x + col * res_x
cropped_meta["origin_y"] = origin_y - row * res_y
```

**Problem.** `origin_x` / `origin_y` here are the GDAL affine origin
(`gt[0]`, `gt[3]`) but the **sign** of the step-in-rows direction is
thrown away at load. In `load_hirise_dem` the code does
`"resolution_y": abs(gt[5])` — but the sign of `gt[5]` carries the map
orientation. For a standard north-up GeoTIFF `gt[5]` is **negative**
(y decreases as row increases). The crop code then assumes that and
hardcodes `-row * res_y`. That's correct for north-up rasters but
silently wrong for the (admittedly rare) south-up case where `gt[5]`
is positive. Worse, the metadata the caller sees has already lost the
sign, so a downstream consumer cannot even detect the orientation.

Even for the common case, the two sign conventions (always-positive
`resolution_y`, minus-sign hardcoded in crop) create a hidden
coupling: change `load_hirise_dem` to keep the raw `gt[5]` (a
perfectly reasonable refactor) and every cropped origin silently
flips.

**Fix.** Store the raw `gt` or a `y_step_sign` (or keep the signed
`gt[5]` as `resolution_y_signed`) in metadata, and in `crop_dem` use
`origin_y = origin_y + row * resolution_y_signed`. Document the
assumption loudly if you choose to keep the north-up-only path.

---

### C2. `dem_loader.load_hirise_dem` nodata comparison loses precision for double-valued sentinels

**File / line:** `marslab/terrain/dem_loader.py:63, 66-69`

```python
elevation = band.ReadAsArray().astype(np.float32)
...
nodata = band.GetNoDataValue()
if nodata is not None:
    elevation[elevation == np.float32(nodata)] = np.nan
```

**Problem.** `GetNoDataValue()` returns a Python `float` (64-bit). The
array was already cast to `float32`. Casting the sentinel back to
`float32` and comparing with `==` works *only* when the sentinel
survives float32 quantization bit-exactly. Common Mars HiRISE nodata
values (`-3.4028234663852886e+38`, the float32 min) do survive, but
others (`-9999.0` in double precision downcast to float32 is fine;
`-1e+36`, `-3.4e38`) can differ from the re-cast float32. Result: some
nodata pixels bleed through as absurdly large finite values and
corrupt `elevation_min/max` and every downstream normalization.

Secondarily, for Int16 / UInt16 raw bands the nodata is an integer
whose float representation may disagree with the cast-then-compare.

**Fix.** Either (a) read as native dtype first, apply the nodata mask
*before* casting:

```python
raw = band.ReadAsArray()
nodata = band.GetNoDataValue()
mask = (raw == nodata) if nodata is not None else None
elevation = raw.astype(np.float32)
if mask is not None:
    elevation[mask] = np.nan
```

or (b) use `np.isclose(elevation, np.float32(nodata), rtol=0, atol=0)`
**only after documenting** the float32 quantization assumption. Path
(a) is strictly safer.

---

### C3. `compute_mesh_arrays` zeroes NaN-after-normalisation, which injects 0-valued holes into the physics collider

**File / line:** `marslab/terrain/mesh_builder.py:58-60`

```python
valid_min = np.nanmin(elev)
elev -= valid_min
elev = np.nan_to_num(elev, nan=0.0)
```

**Problem.** `valid_min` is the non-NaN minimum; subtracting it puts
the valid floor at 0. Then `nan_to_num(..., nan=0.0)` replaces nodata
holes with 0.0 — i.e., it plants the hole **exactly at the terrain
floor elevation**. Any rover/robot traversing through a nodata region
walks into an invisible pothole (or cliff, if the real surrounding
elevation is above 0). Normals are then computed from these spurious
zeros via `np.gradient`, producing fake vertical walls at the hole
boundary that will break PhysX collision contacts.

`dem_loader.crop_dem` guards against NaN in crops, but the non-cropped
path in `build_terrain_mesh` does not, and `compute_mesh_arrays` is a
public API with its own docstring. The docstring brags about the
"spawn-z coupling bug" fix (line 25-27) while simultaneously doing a
worse thing with holes.

**Fix.** Either (a) refuse NaN inputs with `ValueError`, or (b)
fill using `scipy.ndimage.distance_transform_edt` nearest-neighbor
interpolation so holes match the surrounding terrain, or (c) fill with
`np.nanmean(elev)` as a last resort. Silently replacing with zero is
the worst option.

---

## HIGH

### H1. Rock count is biased low: Poisson is drawn per-bin from a derived-expected count that divides by *circle area* of a single rock instead of integrating per-rock contribution

**File / line:** `marslab/terrain/rock_placer.py:126-138`

```python
bin_edges = np.logspace(np.log10(d_min), np.log10(d_max), n_bins + 1)
d_lo = bin_edges[:-1]
d_hi = bin_edges[1:]
d_mid = (d_lo + d_hi) / 2.0
delta_cfa = k * np.exp(-q * d_lo) - k * np.exp(-q * d_hi)
expected = area_m2 * delta_cfa / (np.pi / 4.0 * d_mid**2)
```

**Problem.** The Golombek CFA formula gives *fractional area covered
by rocks ≥ D*. Differencing gives the fractional area contributed by
rocks in `[d_lo, d_hi]`. Dividing that **total covered area** by the
average rock footprint `π/4 · d_mid²` gives expected *count*. Using
`d_mid` (arithmetic mean of bin edges on a logspace) systematically
overestimates the average area per rock (because `E[D²]` over a
truncated exponential within the bin is **not** `d_mid²`). That makes
`expected` systematically **too low**, so the sampler under-populates
every scene.

For bin widths this wide (50 log-spaced bins across 1-2 decades) the
error is 5-15% per bin and compounds over the full population. That
is already outside the 10% Golombek validation tolerance that the
docstring implicitly claims by citing the paper.

**Fix.** Either make `d_mid` the log-mean or use `E[D² | bin]`
computed from the exponential tail (analytically, since it is an
exponential). Or use many more, finer bins (e.g. n_bins = 500) and
document the bias is <1%.

Also consider: rather than bin-and-Poisson, draw the *total* expected
count once from Poisson, then sample diameters from the truncated
exponential directly via inverse-CDF. That is both more accurate and
simpler code.

### H2. Rock placer does not enforce rock non-overlap — populations at high k produce overlapping / intersecting rocks

**File / line:** `marslab/terrain/rock_placer.py:139-143`

```python
for _ in range(count):
    d = rng.uniform(d_lo[i], d_hi[i])
    x = rng.uniform(0, side)
    y = rng.uniform(0, side)
    rocks.append(RockPlacement(x=x, y=y, diameter=d, height=height_ratio * d))
```

Placements are independent uniform draws. At k ≥ 0.08 (VL1-like) the
expected rock-coverage fraction is 8%; the expected number of
pairwise overlaps is O(N²·(area per rock)²/total_area), which for a
20×20 m² plot and 500+ rocks produces dozens of intersecting pairs
per seed. In downstream `rock_instancer`, these become interpenetrating
colliders that will NaN the physics step or spawn the rover on top of
a stacked-rock tower.

**Fix.** Poisson-disc sampling (e.g. Bridson 2007) or rejection
sampling with a min-separation of `max_diameter * 1.1`.

### H3. Rock placer silently drops bins whose log-spaced upper edge exceeds `d_max` and uses list.append in a tight loop

**File / line:** `marslab/terrain/rock_placer.py:132-143`

```python
expected = np.where(expected > 0, expected, 0.0)

rocks: list[RockPlacement] = []
for i in range(n_bins):
    if expected[i] <= 0:
        continue
    count = rng.poisson(expected[i])
    for _ in range(count):
        ...
        rocks.append(RockPlacement(...))
```

Two issues:

1. `np.where(expected > 0, expected, 0.0)` is a no-op for non-negative
   Poisson inputs that are always ≥ 0; the previous line
   `area_m2 * delta_cfa / (...)` cannot be negative since all factors
   are positive. This is defensive code paranoia against an impossible
   condition — delete it.
2. For large populations (N > 10 k, common for a 100×100 m Mars plot
   with k=0.06), the per-rock `rocks.append(RockPlacement(...))`
   loop is a Python-level loop that dominates runtime. Vectorize:
   `rng.poisson(expected)` once per bin, then `rng.uniform(d_lo[i],
   d_hi[i], count)` — collect into numpy arrays, construct dataclasses
   at the end or return a pandas-style dict.

### H4. `material_applicator.apply_terrain_material` and `apply_cave_material` are 95% identical — copy-paste smell

**File / line:** `marslab/terrain/material_applicator.py:15-68` vs
`71-117`.

Both functions: identical validation, identical `rng = default_rng(seed);
albedo = uniform(...)`, identical OmniPBR creation, identical
`set_reflection_roughness(0.8 or 0.85)`, identical texture-apply,
identical bind logic. The only differences are the material path
suffix (`/material` vs `/cave_material`), material name, color tint
coefficients (`[2.5, 1.8, 1.2]` vs `[1.2, 1.0, 0.9]`), roughness
(`0.8` vs `0.85`), and default albedo range (cave has its own
default).

**Fix.** Parameterize into one private `_apply_pbr(stage, path, tint,
roughness, albedo_range, seed, name, texture_dir)` and make the two
public functions one-liner adapters. Saves 50 LOC and removes the
guaranteed divergence the next time someone tunes the Mars terrain
tint and forgets the cave branch.

### H5. `rock_instancer._apply_rock_material` duplicates the texture-apply block from `material_applicator._apply_textures` verbatim

**File / line:** `marslab/terrain/rock_instancer.py:177-196` vs
`material_applicator.py:131-154`.

```python
# rock_instancer.py:177-196
shader = material.shaders_list[0]
albedo_path = os.path.join(texture_dir, "albedo.png")
if os.path.isfile(albedo_path):
    material.set_texture(os.path.abspath(albedo_path))
    material.set_project_uvw(True)  # <-- only real difference
normal_path = os.path.join(texture_dir, "normal.png")
if os.path.isfile(normal_path):
    shader.CreateInput("normalmap_texture", Sdf.ValueTypeNames.Asset).Set(...)
...
```

Same five texture inputs, same albedo/normal/roughness keys, same
file naming convention. The only functional delta is
`set_project_uvw(True)` vs `set_project_uvw(False)`. The reviewer
grep confirms the pattern across `material_applicator.py` (2 call
sites) and `rock_instancer.py` (1 call site) — that is **three**
copies of the same ~25-line block.

**Fix.** Extract into a public helper in `material_applicator.py`
(or a new `mars_materials.py`) and have `rock_instancer` import it.
Signature: `apply_pbr_textures(material, texture_dir, project_uvw: bool)`.

### H6. `_euler_to_quath` implementation is not obviously equivalent to any published XYZ/ZYX convention — no unit test, no reference, silent wrong rotations possible

**File / line:** `marslab/terrain/rock_instancer.py:208-223`

```python
def _euler_to_quath(roll_deg, pitch_deg, yaw_deg) -> Gf.Quath:
    roll = np.radians(roll_deg); pitch = np.radians(pitch_deg); yaw = np.radians(yaw_deg)
    cr, sr = np.cos(roll/2), np.sin(roll/2)
    cp, sp = np.cos(pitch/2), np.sin(pitch/2)
    cy, sy = np.cos(yaw/2),   np.sin(yaw/2)
    w = cr*cp*cy + sr*sp*sy
    x = sr*cp*cy - cr*sp*sy
    y = cr*sp*cy + sr*cp*sy
    z = cr*cp*sy - sr*sp*cy
    return Gf.Quath(float(w), float(x), float(y), float(z))
```

This is the intrinsic ZYX (yaw-pitch-roll) formula, but the argument
order is `(roll, pitch, yaw)`. The formula and order together happen
to be self-consistent, but there is:

1. No docstring naming the convention (intrinsic vs extrinsic, which
   axis is yaw, Tait-Bryan vs proper Euler).
2. No cross-check against `pxr.Gf.Rotation.SetEulerAngles` or
   `scipy.spatial.transform.Rotation` — Pixar USD ships its own
   helper that nobody is using.
3. Pitch range (`±20°`) where all three angles are applied from a
   single `np.random.default_rng` consumption order: yaw, pitch, roll,
   roll-of-next-rock, ... — this couples the RNG state to iteration
   order in a way that is not obvious from the caller's point of view
   (see `rock_instancer.py:85-88`).

**Fix.** Replace with:

```python
from scipy.spatial.transform import Rotation as R
q = R.from_euler("xyz", [roll_deg, pitch_deg, yaw_deg], degrees=True).as_quat()
# scipy returns [x,y,z,w]; USD wants Quath(w,x,y,z)
return Gf.Quath(float(q[3]), float(q[0]), float(q[1]), float(q[2]))
```

Or use `pxr.Gf.Rotation(Gf.Vec3d.XAxis(), roll_deg) * ...`. Either
way, cite the convention in the docstring and add a unit test
(`assert Rotation.from_euler("xyz", [90, 0, 0]).as_quat() ==
[0.707, 0, 0, 0.707]`).

---

## MEDIUM

### M1. `build_terrain_mesh` materializes every point/normal through a Python list comprehension, defeating numpy

**File / line:** `marslab/terrain/mesh_builder.py:229-232`

```python
points_vt = Vt.Vec3fArray([Gf.Vec3f(float(p[0]), float(p[1]), float(p[2])) for p in points_np])
normals_vt = Vt.Vec3fArray([Gf.Vec3f(float(n[0]), float(n[1]), float(n[2])) for n in normals_np])
```

For a 2000×2000 DEM (= 4 M vertices — a reasonable HiRISE crop)
this is 4 M × 3 Python float() calls = ~10 seconds of pure Python
per mesh. `Vt.Vec3fArray` accepts a numpy array directly via
`Vt.Vec3fArray.FromNumpy(points_np)` (or via the `UsdGeom.Mesh`
schema's native numpy setter in recent USD). Same for normals and
the UV Vec2fArray at line 249.

**Fix.** Use `Vt.Vec3fArray.FromNumpy(points_np)` — ~100× faster.

### M2. `compute_mesh_arrays` returns `face_indices` as a Python list via `.tolist()` — O(6 N) Python objects

**File / line:** `marslab/terrain/mesh_builder.py:115`

```python
"face_indices": face_indices.tolist(),
```

Then `build_terrain_mesh:237` passes the list straight into USD. For
a 2000×2000 mesh that is 24 M ints. Keep it numpy; USD's
`GetFaceVertexIndicesAttr().Set(Vt.IntArray.FromNumpy(arr))` works.

### M3. `crop_dem` blind-copies `nodata` into cropped metadata but asserts cropped region has no NaN

**File / line:** `marslab/terrain/dem_loader.py:203-214`

Cropped array is guaranteed NaN-free (check at line 203), yet
`cropped_meta = dict(metadata)` preserves `nodata: <value>`. Downstream
consumers will see a nodata sentinel that cannot actually occur.
Either null it out (`cropped_meta["nodata"] = None`) or document that
the cropped-metadata-nodata is historical only.

### M4. `terrain_z_at` silently clips to grid edges instead of erroring

**File / line:** `marslab/terrain/mesh_builder.py:172-179`

```python
col_f = float(np.clip(x / resolution, 0.0, cols - 1.0))
row_f = float(np.clip(y / resolution, 0.0, rows - 1.0))
```

A caller that asks for `terrain_z_at(elev, 1.0, -5.0, -5.0)` gets the
`elev[0, 0]` value silently, with no warning. For rover-spawn or rock
placement this means a bug in position computation returns a seemingly
reasonable z and the physics mis-spawns instead of failing fast.

**Fix.** Raise `ValueError` for out-of-bounds queries, or at least log
a warning. Clipping should be opt-in.

### M5. `procedural_generator._generate_canyon` uses `rows - 1` nowhere, `cols - 1` nowhere — frequency formula divides by `rows * resolution` which is fine, but the centerline indexing assumes `y_grid = np.mgrid[0:rows]` returns integer indices matching `row_coords` exactly. OK in practice but brittle.

**File / line:** `marslab/terrain/procedural_generator.py:229-232`

```python
y_grid, x_grid = np.mgrid[0:rows, 0:cols]
x_m = x_grid.astype(np.float64) * resolution
centerline_2d = centerline_m[y_grid]  # <-- fancy-indexing a 1-D array with 2-D int grid
```

This does work (broadcasting + fancy indexing), but is a readability
foot-gun. Use `centerline_m[:, None]` broadcast instead:

```python
centerline_2d = centerline_m[:, None]
dist = np.abs(x_m - centerline_2d)
```

Same result, no int-index detour, ~2× faster.

### M6. `_generate_canyon` crater rim formula is subtly wrong — uses `cr_dist[cr_rim_mask] - cr_radius) / (cr_radius * 0.3)` but the rim mask uses `cr_radius * 1.3` — OK, but the crater profile is *added* to `elevation` (line 283) while the main crater **overwrites** floor regions (line 247). Mixed overwrite-vs-add semantics create asymmetric rim behavior near the canyon wall.

**File / line:** `marslab/terrain/procedural_generator.py:277-283`

```python
crater_profile = np.zeros_like(elevation)
crater_profile[cr_inside] = -cr_depth * (1.0 - (cr_dist[cr_inside] / cr_radius) ** 2)
...
elevation += crater_profile
```

If a crater is placed near the floor-wall boundary (the floor-mask
selection at line 265 picks `floor_cols_at_row` which can be adjacent
to the wall), the crater rim bump can land on a wall pixel that was
just set by the smoothstep formula, creating a bump on top of a steep
slope. Unlikely to matter for navigation, but the docstring claims
"small craters on the floor for obstacle avoidance testing" — in
reality they can leak into walls.

**Fix.** Multiply `crater_profile` by `floor_mask` before adding.

### M7. `elevation_loader._load_cave` mutates the caller's `terrain_cfg` by stashing `_cave_data` into it

**File / line:** `marslab/terrain/elevation_loader.py:91-92`

```python
# Stash so scene builder can pick it up without a second generation pass.
terrain_cfg["_cave_data"] = cave_data
return elevation, metadata, resolution
```

Side-effect-on-input-dict is a surprise for a function that otherwise
looks pure. Any caller that re-uses the config (YAML-loaded dict
passed to multiple scenarios, memoization, config validation
roundtrip) gets a huge numpy blob silently injected. Worst case: the
YAML dumper tries to serialize this and explodes.

**Fix.** Return `cave_data` as a fourth tuple element, or expose a
separate `load_cave_mesh` path, or at minimum namespace it under a
clearly private sidecar mapping rather than the raw config dict.

### M8. `rock_placer.compute_q` docstring says "For Mars applications, practical k values range from 0.001 to 0.15" but `compute_q` itself accepts `k in (0, 1]` while `sample_rocks_golombek` enforces `k in (0, 0.15]`. Inconsistent bounds across the same module.

**File / line:** `marslab/terrain/rock_placer.py:53-55` vs `113-114`.

Either enforce `(0, 0.15]` consistently or document the relaxation in
`compute_q`/`compute_cfa` explicitly. Otherwise a caller is free to
call `compute_cfa(k=0.5, ...)` and get a result that is mathematically
consistent but physically meaningless for Mars.

---

## LOW

### L1. Internal jargon in docstrings — "comments-as-deodorant" smell

Examples:
- `mesh_builder.py:9`: "See work_log Wk1 #40 for the root cause..."
- `elevation_loader.py:79-82`: "``geometry`` (R5) is a nested block..."
- `terrain_loader.py:1-10`: "R3-A3", "Option-B facade", "(P3)",
  "inherited through the underlying loader's type hints" (confusing).
- `rock_placer.py:42-43`: "This is a general mathematical function" —
  explaining-why-not-explaining-what.

External reviewers can't cross-reference `Wk1 #40` or `R3-A3`. These
should be either dropped or replaced with content-level explanations
("previously the winding was CW — PhysX reported inverted normals and
objects fell through the mesh").

### L2. `terrain_loader.py` docstring cites exact line numbers in a different file that will rot

**File / line:** `marslab/terrain/terrain_loader.py:65-68`

> "Absorbs the `os.path.join(REPO_ROOT, ...)` assembly that previously
>  lived inline in `run_stage2.py` (L266-274, L304-312) and
>  `run_stage3_monolithic_new.py` (L443-451, L481-483, L507-512)..."

Line-number references in prose go stale on the next `black` run.
Drop them or replace with a function reference.

### L3. `material_applicator.apply_terrain_material` docstring says "If texture_dir is provided and contains texture files, applies full PBR textures" — but the function will happily create and bind an OmniPBR material even if `texture_dir` points at an empty directory. The wording suggests a fallback to color, but in fact *color is always applied* first and textures are layered on top.

**File / line:** `marslab/terrain/material_applicator.py:23-27`.

Docstring mis-describes behavior. Either change the wording ("color
is always applied; PBR textures are layered on top when available")
or change the code.

### L4. `_add_micro_detail` has a silent seed dependency — `rng.standard_normal(...)` inside consumes N=rows*cols draws per call, and `_generate_hills`/`_generate_crater` etc. each call it at the end. This means changing `_add_micro_detail` amplitude or sigma does **not** change the micro-detail noise pattern, but re-ordering the functions does. Brittle.

**File / line:** `marslab/terrain/procedural_generator.py:110-117`.

Fix with a derived-seed pattern or explicit per-stage `Generator`.

### L5. Type hints on public APIs inconsistently use `tuple[...]` (PEP 585, py 3.9+) vs `Tuple[...]` (typing, pre-3.9)

Examples:
- `dem_loader.py:13`: `tuple[np.ndarray, dict]` — py 3.9+.
- `elevation_loader.py:22`: `Tuple[np.ndarray, Dict[str, Any], float]`
  — `from typing import Tuple, Dict`.
- `terrain_loader.py:16`: `from typing import Any, Dict, Optional,
  Tuple` — same as above.

Pick one convention (PEP 585 since you already use it in `dem_loader`)
and stick to it.

### L6. `material_applicator._apply_textures` has `material: OmniPBR` as the first-arg type hint, but imports `OmniPBR` only for name-binding. Fine, but the function is not re-usable from outside this module because it is underscore-prefixed. And yet `rock_instancer.py` re-implements the same logic. Decide: make it public or move to a shared module.

See H5 for the fix.

### L7. `rock_placer.sample_rocks_golombek` returns `list[RockPlacement]` but the list is immediately re-sorted by the caller — why not document the sort order or return a tuple?

Minor. The docstring does say "sorted by diameter descending", but a
downstream consumer re-sorting is a code smell that suggests the sort
is spurious (and indeed `rock_instancer.place_rocks_on_terrain` does
not rely on the order). If nobody relies on the sort, drop it.

---

## DELETE

### D1. `np.where(expected > 0, expected, 0.0)` at `rock_placer.py:132`

Dead paranoia — `expected` is a product of non-negative quantities.
Delete.

### D2. Docstring pseudocode at `procedural_generator.py:86-92` is longer than the function body (`_normalize_noise`)

```python
def _normalize_noise(...):
    """Draw Gaussian noise, smooth it, and rescale to the requested amplitude.

    Internally: ``rng.standard_normal((rows, cols))`` ->
    ``gaussian_filter(..., sigma)`` -> divide by std (``+1e-8`` guard) ->
    multiply by ``amplitude``. ...
    """
    raw = rng.standard_normal((rows, cols))
    smooth = gaussian_filter(raw, sigma=sigma)
    return smooth / (np.std(smooth) + 1e-8) * amplitude
```

The pseudocode is a line-by-line restatement of the body. Keep only
the Args/Returns and a single-line summary. The "extracted so the
six call sites" is fine.

---

## WATCHLIST

### W1. `Gf.Vec3f` / `Gf.Vec2f` / `Gf.Quath` literal construction at runtime

All three of `mesh_builder.py:229`, `rock_instancer.py:82`,
`rock_instancer.py:103` construct USD types one-at-a-time in Python
loops. For small meshes (64×64) this is fine. For a full HiRISE
crop or a high-density rock field (10 k+ instances) it will dominate
load time. Watch for the complaint "scene load takes 30s"; that is
where the time goes.

### W2. `cave_generator.py` — out of scope for this audit but referenced at `elevation_loader.py:73`

`from marslab.terrain.cave_generator import generate_cave_mesh`. Lazy
import hides the dependency from offline unit tests but also hides
the coupling from reviewers. The separate cave auditor should look
at whether `_cave_exclude = {"wall_albedo_range", "geometry"}` is
actually an exhaustive list of non-kwargs, or if silent key drop can
happen when a new cave config option is added.

### W3. `elevation_loader._load_procedural` filters kwargs by prefix `canyon_`

**File / line:** `marslab/terrain/elevation_loader.py:104`

```python
preset_params = {k: v for k, v in terrain_cfg.items() if k.startswith("canyon_")}
```

…but only the canyon preset uses `canyon_*` keys. What about future
presets that want configurable params (e.g. `crater_*`, `hills_*`)?
The current prefix filter is canyon-specific and will silently drop
all non-canyon preset params. Either whitelist per-preset or pass
the whole dict.

### W4. `dem_loader.save_converted_dem` writes JSON without any version stamp

**File / line:** `marslab/terrain/dem_loader.py:109-110`

```python
with open(os.path.join(output_dir, "metadata.json"), "w") as f:
    json.dump(metadata, f, indent=2)
```

No schema version key. Next time `load_hirise_dem` changes its
metadata shape (adds a field, renames a field), every cached
`metadata.json` on every developer's disk is silently wrong and
backward-incompatible. Add `"_schema_version": 1`.

---

## 3-line summary

- Output path: `/home/hoyunkim/MarsLab/work_log/reviewer2_audit_2026-04-24/08_terrain_core.md`
- Severity counts: CRITICAL 3 · HIGH 6 · MEDIUM 8 · LOW 7 · DELETE 2 · WATCHLIST 4
- Top concerns: NaN/nodata hole-injection into physics collider (C3), DEM nodata float32 comparison precision loss (C2), DEM crop origin_y sign convention coupling (C1), Golombek SFD bin-mean bias & lack of non-overlap enforcement (H1/H2), and three-way duplication of the OmniPBR texture-apply block across `material_applicator` and `rock_instancer` (H4/H5).
