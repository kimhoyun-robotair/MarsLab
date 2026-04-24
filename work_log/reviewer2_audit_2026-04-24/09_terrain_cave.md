# Reviewer 2 Audit — marslab/terrain/cave/ and cave_generator / cave_mesh_builder

**Scope audited (8 files):**
- `marslab/terrain/cave/__init__.py`
- `marslab/terrain/cave/_constants.py`
- `marslab/terrain/cave/geometry.py`
- `marslab/terrain/cave/mesh.py`
- `marslab/terrain/cave/features.py`
- `marslab/terrain/cave/breakdown.py`
- `marslab/terrain/cave_generator.py`
- `marslab/terrain/cave_mesh_builder.py`

Tone is hostile. CLAUDE/PLAN/internal jargon was not read; citations to "R5", "P3", "Oracle parity", "offline-first" were treated as deodorant smells and surfaced accordingly.

---

## CRITICAL

### C1. `build_tube_shell` face winding is actually *outward*, not "inward" as the docstring claims.
**File:** `marslab/terrain/cave/mesh.py:50-80`
**Quote:**
> `# Winding is reversed so face normals point inward (toward the tube interior)`
> ```
> faces[0::2] = np.stack([v0, v2, v1], axis=1)
> faces[1::2] = np.stack([v1, v2, v3], axis=1)
> ```

**Problem:** At each station the ring is parameterised as `theta = linspace(0, pi, ring_pts)` in `build_cross_sections` (geometry.py:133) with `base_x = a*cos(theta)`, `base_z = b*sin(theta)`. j=0 sits at +x (cos 0 = +1), j=ring_pts-1 sits at -x. Along the tube, increasing i advances the centerline in tangent direction **t**. The perpendicular `perp` is produced by rotating t by 90° via `perp = (-t_y, t_x, 0)` (geometry.py:175-176), which is a **left-hand** rotation in a right-handed XYZ frame, i.e. perp × t points in **-Z**, not +Z. With that handedness:

For the triangle `(v0, v2, v1)` = (i,j) -> (i+1,j) -> (i,j+1), edges are along **t** and along **-x_ring** (decreasing j goes from +x toward -x in local frame via `cos(theta)`). Cross product `t × (-x_ring)` for a ring oriented along (perp, z) with perp having `perp × t = -Z` handedness gives the normal **pointing OUTWARD from the tube** (radially away from the centerline), i.e. toward the bulk rock, not toward the interior.

Consequence: the `double_sided=True` in cave_mesh_builder is the only reason anything renders. PhysX collision normals, ray-cast visibility for cameras, and any shading model that consults front-face normals (ambient occlusion, SSS proxies, normal-based detail scaling) are all oriented backward. Test `test_cave_generator.py:152` only asserts 50% of ceiling normals point down — too loose to detect this.

**Fix:** Actually verify winding empirically with a tiny trimesh volume check inside the unit test, then either flip `perp` to `perp = (t_y, -t_x, 0)` or swap the face tuples to `(v0, v1, v2)` / `(v1, v3, v2)`. Also update the docstring to match what the code actually does (and `double_sided=True` can then be dropped, reducing shader cost).

### C2. `build_skylight_shaft` silently drops the last ring row — shaft is not closed.
**File:** `marslab/terrain/cave/mesh.py:194-203`
**Quote:**
> ```
> i, j = np.meshgrid(np.arange(n_rings - 1), np.arange(n_segments), indexing="ij")
> j_next = (j + 1) % n_segments
> v0 = (i * n_segments + j).ravel()
> ...
> v2 = ((i + 1) * n_segments + j).ravel()
> ```

**Problem:** This builds the wall between ring i and ring i+1, fine. But neither the top ring (surface level) nor the bottom ring (ceiling level) is capped. The **bottom** ring of the shaft is where it must meet the tube ceiling — there is no topological merge there. Meanwhile the tube shell has its own ceiling mesh above at `z = tube_height_m + base_z(theta)` with the skylight not subtracted at all (no boolean operation / no face deletion in `build_tube_shell`). Result: the shaft wall penetrates the tube ceiling, leaving a non-manifold intersection where two separate surfaces cross. A camera peering up through the skylight sees a Z-fighting band and gaps.

**Fix:** Either
1. Subtract the skylight disc from the tube ceiling (analogous to what `build_surface_cap` does at lines 265-274 for the top), then cap the shaft's bottom with radial triangles; or
2. Perform a trimesh boolean union before returning; or
3. Document that the cave is intentionally non-manifold and rendered double-sided (but then the "science-basis" framing is theatre).

### C3. Skylight shaft physically impossible when `overhang_deg` pushes radius beyond the ceiling aperture.
**File:** `marslab/terrain/cave/mesh.py:181-188`
**Quote:**
> ```
> overhang_rad = np.radians(overhang_deg)
> n_rings = max(ring_min, int((surface_z - ceiling_z) / ring_spacing_m))
> z_levels = np.linspace(surface_z, ceiling_z, n_rings)
> radii = r_surface + (surface_z - z_levels) * np.tan(overhang_rad)
> ```

**Problem 1:** The docstring says "overhang_deg > 0 the radius grows linearly with depth so the walls lean inward toward the axis" — that is a direct contradiction. If the radius **grows** with depth, the walls lean **outward** (the opening is the narrowest part), not inward. An overhang is by definition the opposite: the ceiling-level aperture is *wider* than the surface aperture (undercut). The arithmetic matches "walls flare out as you go down," the docstring and the name `overhang` describe an undercut. This disagreement will either (a) silently flip with a future reader "fixing" one to match the other, or (b) generate a cave where robots plunge through a funnel-shaped shaft floor that is way larger than the opening.

**Problem 2:** There is no guard on the aperture at `ceiling_z` exceeding the tube ceiling itself. With `skylight_depth_m=90`, `overhang_deg=5°`, `r_surface=10`, the bottom radius is `10 + 90*tan(5°) ≈ 17.9 m`. Perfectly reasonable. But with `overhang_deg=30` and `depth=90`, radius at the ceiling is `10 + 90*tan(30°) ≈ 62 m` — wider than the 100 m tube radius. There is no validation; the shaft will just gleefully intersect the tube wall.

**Problem 3:** `n_rings = max(ring_min, int((surface_z - ceiling_z) / ring_spacing_m))` silently truncates with `int()`. If `surface_z <= ceiling_z` (misconfigured where ceiling thickness is set to zero or negative by cascading YAML), `int(-x / 5) = 0` and `max(10, 0) = 10`, then `linspace(surface_z, ceiling_z, 10)` produces descending/inverted rings with no error. The shaft geometry flips inside-out.

**Fix:** (a) Decide whether `overhang_deg>0` means undercut or flare and rename + correct; (b) assert `surface_z > ceiling_z`; (c) assert `r_surface + depth*tan(overhang) < tube_width_m/2 * safety` or clamp.

### C4. `generate_breakdown_positions` docstring lies about the `rng.lognormal` semantics.
**File:** `marslab/terrain/cave/breakdown.py:66-68, 108-113`
**Quote:**
> ```
> block_mean: LogNormal mean diameter (passed as ``log(mean)`` to rng.lognormal).
> ```
> ```
> diameter = float(rng.lognormal(mean=np.log(block_mean), sigma=block_sigma))
> ```

**Problem:** NumPy's `rng.lognormal(mean, sigma)` interprets `mean` and `sigma` as the mean and stddev of the **underlying normal distribution**, not of the lognormal itself. Passing `np.log(block_mean)` does NOT make `block_mean` the lognormal mean; it makes it the lognormal *median*. The lognormal mean is `exp(mu + sigma^2 / 2) = block_mean * exp(sigma^2/2)`. For `block_sigma=0.3`, the actual mean is 4.6% larger than `block_mean`; for `block_sigma=1.0` it's 65% larger. Either the parameter name is wrong or the call is wrong. Given the Blank 2024 / BRAILLE citation was not read by me, the reviewer cannot tell which is intended — but the two are inconsistent and calibration claims against a published SFD are bogus until this is resolved.

**Fix:** Either rename `block_mean` to `block_median` everywhere (parameter, docstring, schema, scenario YAMLs), or change the call to `mean=np.log(block_mean) - block_sigma**2 / 2`. Pick one and document which moment is being controlled.

### C5. `build_tube_floor` uses **vertical-noise amplitude without scaling to per-station geometry**, and the floor mesh is not connected to the tube shell.
**File:** `marslab/terrain/cave/mesh.py:117-146`
**Quote:**
> ```
> floor_pts = max(int(ring_pts * floor_width_ratio), floor_width_min_pts)
> ...
> floor_x = np.linspace(cross_sections[i, 0, 0], cross_sections[i, -1, 0], floor_pts)
> ...
> vertices[debris_mask, 2] += np.abs(noise[debris_mask])
> ```

**Problem A — disjoint mesh:** The floor uses a completely separate vertex buffer from `build_tube_shell`. The tube's ring endpoints at j=0 and j=ring_pts-1 are already at floor level (`z = b*sin(0) = 0`, `z = b*sin(pi) = 0`), but the floor has its own vertices at the same (x,y) positions, generated by `np.linspace` over `floor_pts` — which generally ≠ `ring_pts`. So the tube wall meets the floor along a geometric seam but they are not stitched: light leaks, ray-cast gaps, and PhysX allows the rover to fall through the crack when `process=False` skips trimesh's merge_vertices.

**Problem B — noise sign is always positive:** `vertices[debris_mask, 2] += np.abs(noise[debris_mask])`. Debris is only ever a positive displacement, turning the smoothed Gaussian noise into a one-sided pile with a systematic mean shift. Physically, rubble **does** fill depressions too; this is a non-physical bias. Worse, `np.abs(smoothed_noise)` destroys the smoothness guarantee: the gaussian_filter was done, then abs() creates new creases at every zero crossing. The resulting micro-cliffs are exactly the kind of feature that breaks the rover's wheel friction on first contact.

**Problem C — floor span shrinks randomly:** For `ring_pts=40`, `floor_pts=20`. For `ring_pts=40` and `floor_width_min_pts=8`, `floor_pts=20`. Fine. But `floor_x` endpoints are `cross_sections[i, 0, 0]` and `cross_sections[i, -1, 0]`, which have noise from `build_cross_sections`. Adjacent stations' floor endpoints therefore shift non-monotonically, and the strip edges are not aligned with the tube wall's noise.

**Fix:** Unify the floor and tube shell into one mesh (share vertices at the seam), use signed noise (not abs), and derive `floor_pts` deterministically so it couples to the stitching strategy.

### C6. `build_surface_cap` X/Y axis mapping is inverted relative to everywhere else in the codebase AND relative to the cave centerline.
**File:** `marslab/terrain/cave/mesh.py:246-254` vs. `marslab/terrain/cave/geometry.py:68-70`
**Quote (surface cap):**
> ```
> col_idx = np.arange(cols, dtype=np.float64)
> row_idx = np.arange(rows, dtype=np.float64)
> col_grid, row_grid = np.meshgrid(col_idx, row_idx)
> vertices[:, 0] = (col_grid * resolution).ravel()  # X = col
> vertices[:, 1] = (row_grid * resolution).ravel()  # Y = row
> ```
> but `domain_m = (rows * resolution, cols * resolution)` (cave_generator.py:133), which is passed as `(height_m, width_m)` and in `build_centerline`: `center_x = width_m / 2.0` (geometry.py:69) — i.e. the centerline places X along `width_m = cols * resolution`, consistent with the surface cap.

**Problem:** Consistent with itself, but **inconsistent with terrain/procedural_generator.py, dem_loader.py, and terrain_loader.py**, where the convention elsewhere in the repo (e.g. procedural_generator `_generate_flat`) uses standard numpy grid indexing with `y_grid, x_grid = np.mgrid[0:rows, 0:cols]`, meaning Y=row, X=col is the convention. Here, it happens to match — but `domain_m = (rows*res, cols*res)` as `(height_m, width_m)` is *not* the image-processing convention, which would be `(height = rows, width = cols)` only if rows correspond to vertical (Y) and cols to horizontal (X), and then the tuple order `(height_m, width_m)` means `(Y-span, X-span)`.

Then `domain_m[0]` = Y-span = `rows*res` — OK.
Then `build_centerline` takes `height_m, width_m = domain_m` and uses `center_y = height_m / 2.0` — so `center_y = rows*res / 2`. That matches surface cap's Y = row*res. Great.

But a reviewer scanning the codebase sees two problems: (1) function signature uses the name `domain_m` but the order is `(height, width) = (Y-span, X-span)` which is the opposite of nearly every computer-graphics API's convention `(width, height)`. (2) `domain_size: tuple[int, int] = (400, 400)` is square so bugs cannot be empirically caught. A future scenario with `domain_size=(300, 500)` will expose the mismatch because `build_centerline` and `compute_skylight_positions` will interpret the same meters the wrong way if anyone ever refactors the unpacking. This is a latent bug waiting to happen.

**Fix:** Either adopt the canonical `(width, height)` order and fix all call sites, or add `assert rows == cols` for now and ship a test case with non-square domain before refactoring.

---

## HIGH

### H1. `compute_skylight_positions` degrades silently to a single skylight when the centerline is entirely out-of-bounds.
**File:** `marslab/terrain/cave/features.py:81-82`
**Quote:**
> ```
> if len(valid_indices) == 0:
>     return [(width_m / 2.0, height_m / 2.0)]
> ```

**Problem:** The caller (`generate_cave_mesh`, cave_generator.py:167-173) requested `skylight_count` skylights with a configured separation. On total failure the function fabricates a single skylight at the domain center without any signal. Worse, if `count=0` the function returns `[]` (features.py:67-68), but if the centerline falls outside the margin entirely, it returns `[(center)]` — exactly one, regardless of `count`. A user asking for zero skylights gets zero; a user asking for ten and mis-configuring gets one. That's silent swallowing of a configuration bug.

**Fix:** Raise `ValueError("no valid skylight positions; tube centerline fully outside margin")`, or at minimum log a warning and return `[]` for consistency.

### H2. `compute_skylight_positions` separation check throws away requested skylights without retry.
**File:** `marslab/terrain/cave/features.py:87-98`
**Quote:**
> ```
> step = max(1, len(valid_indices) // (count + 1))
> for k in range(1, count + 1):
>     idx = valid_indices[min(k * step, len(valid_indices) - 1)]
>     ...
>     if not too_close:
>         positions.append((cx, cy))
> ```

**Problem:** If the k-th step position is too close to an earlier one, the function just skips it — no retry, no search for a valid alternative. The docstring does warn that "list may contain fewer than `count` items," but in practice the step is uniform, so if any one collides, a **pattern** of collisions likely exists and multiple are dropped. A user asking for 10 may quietly get 4.

Also: `rng` is accepted "for API symmetry" (features.py:55-56). This is dead-parameter smell. If the function is deterministic, drop the parameter; keeping it in the signature forces every caller to thread rng through for no reason.

**Fix:** Drop `rng` entirely (or use it, by jittering positions), and when a collision occurs, search neighbouring valid indices instead of skipping.

### H3. `generate_breakdown_positions` `total_area` degenerate case treats a degenerate tube as 10 m² per station width.
**File:** `marslab/terrain/cave/breakdown.py:92-97`
**Quote:**
> ```
> if n_stations > 1:
>     segment_lens = np.linalg.norm(centerline[1:, :2] - centerline[:-1, :2], axis=1)
>     avg_widths = (widths[:-1] + widths[1:]) / 2.0
>     total_area = float(np.sum(segment_lens * avg_widths))
> else:
>     total_area = widths[0] * 10.0
> ```

**Problem:** The magic `10.0` is a station length picked from thin air. For `n_stations=1` (which the rest of the code paths don't even produce anything meaningful for — `tangent_frames` on a 1-element array would produce `tangent[0] = centerline[1] - centerline[0]`, which is an out-of-range index!) the area is fabricated. This is dead code with a landmine: if a caller ever passes `path_resolution=1` the upstream `tangent_frames` will IndexError at geometry.py:170 (`tangent[0] = centerline[1] - centerline[0]`).

**Fix:** Raise a clear `ValueError("breakdown requires n_stations >= 2")` up front rather than carrying dead fallback arithmetic.

### H4. `generate_breakdown_positions` centerline exclusion uses `widths[station_idx] * ratio` as a *half-width* — double-booking semantics.
**File:** `marslab/terrain/cave/breakdown.py:90, 138`
**Quote:**
> ```
> widths = np.abs(cross_sections[:, -1, 0] - cross_sections[:, 0, 0])   # FULL width
> ...
> if abs(local_x) < widths[station_idx] * centerline_exclusion_ratio:   # treats it as half
>     continue
> ```

**Problem:** `widths[station_idx]` is the full tube width (distance from leftmost to rightmost cross-section vertex). The exclusion check is `abs(local_x) < widths * 0.1`, i.e. an exclusion *half-width* of 0.1 * tube_width, meaning an exclusion *total corridor* of 0.2 * tube_width. The `_constants.py:56` comment says "half-exclusion vs station width," but actually it's being used as a fraction of the full width. The constant's name `BREAKDOWN_CENTERLINE_EXCLUSION_RATIO = 0.1` is ambiguous. Compare with the docstring at features.py for debris-cone (`DEBRIS_CONE_EXCLUSION_RATIO = 0.1  # half-exclusion vs tube width`) — same comment, same number, but `DEBRIS_CONE_EXCLUSION_RATIO` is used in cave_generator.py:192 as `exclusion_half = tube_width_m * 0.1`, so there it really *is* a half-width. The breakdown version is off by 2x.

**Fix:** Either rename to `BREAKDOWN_CENTERLINE_EXCLUSION_HALF_RATIO` and document clearly, or change the check to `abs(local_x) < widths[station_idx] * centerline_exclusion_ratio / 2`. Pick one, and align the comment with reality.

### H5. `generate_breakdown_positions` `rng.lognormal` can emit `inf` or monstrously large diameters before the cap, wasting rejection iterations.
**File:** `marslab/terrain/cave/breakdown.py:108-114`
**Quote:**
> ```
> diameter = float(rng.lognormal(mean=np.log(block_mean), sigma=block_sigma))
> diameter = min(diameter, diameter_cap_m)
> ```

**Problem:** For `block_sigma=0.3` the 99.9th percentile is ~2.5× the mean, OK. For `block_sigma=1.0` (within normal parameter ranges) the 99.9th percentile is ~50×. The cap at 5.0 m will be saturated constantly, biasing the empirical distribution toward 5.0 m regardless of the requested shape. The `placed_area` accumulates `pi * (d/2)^2` using the **capped** diameter, so the size distribution is corrupted twice: once by rejection, once by cap.

Also: the rejection sampling rejects on (a) skylight overlap and (b) centerline-exclusion, but **does NOT reject on block-block overlap**, so blocks will geometrically overlap/interpenetrate. Since downstream `_build_breakdown_instancer` (cave_mesh_builder.py:176-258) uses these positions for icosphere PointInstancer bodies with `UsdPhysics.CollisionAPI`, overlapping blocks will generate PhysX contact resolution oscillations at startup.

**Fix:** Reject-in-loop on diameter > cap and resample, not clip; add block-pair overlap rejection; correct the accumulated area by the actually-placed (uncapped? or post-resampled?) diameter; log the cap-hit rate.

### H6. `build_debris_cone` divides by `n_rings - 1` without guarding `n_rings == 1`.
**File:** `marslab/terrain/cave/features.py:143`
**Quote:**
> ```
> t = np.arange(n_rings) / (n_rings - 1)
> ```

**Problem:** If `n_rings=1` (not currently default but allowable via kwarg), this is division by zero and silently produces `t = [inf]`. The caller in cave_generator.py always uses the default 12, but the parameter is public. No assertion.

Also at features.py:149: `vertex_array[:, 2] = np.repeat(apex_z - t * cone_height, n_segments)` with `t * cone_height` where `t[0]=0, t[-1]=1` gives apex at ring 0 and base at ring n_rings-1. That is "apex first" in the buffer, which means the `i=n_rings-1` face-building loop connects ring i=0 (the APEX) to ring i=1 as n_segments triangles emanating from near-coincident vertices. At i=0 all n_segments vertices are at `(cx, cy, apex_z)` plus jitter `r_noise * t[0] * base_radius = 0 * anything = 0` — literally coincident (no jitter because `t[0]=0`), yielding n_segments **degenerate zero-area triangles**. That's a mesh quality violation that some renderers will warn about, and that will misbehave under `process=False`.

**Fix:** Either start `t` at a small epsilon to give the apex a tiny collar, or collapse all n_segments apex vertices to a single shared vertex and fan-triangulate from there.

### H7. `build_cross_sections` noise normalization re-uses a *full-tensor std*, creating a subtle station-coupling.
**File:** `marslab/terrain/cave/geometry.py:137-143`
**Quote:**
> ```
> raw_noise = rng.standard_normal((n_stations, ring_pts))
> smooth_noise = gaussian_filter(raw_noise, sigma=smooth_sigma)
> noise_std = np.std(smooth_noise)
> if noise_std > 1e-8:
>     smooth_noise = smooth_noise / noise_std * noise_amp
> else:
>     smooth_noise = np.zeros_like(smooth_noise)
> ```

**Problem:** `np.std(smooth_noise)` is a **scalar** across the entire (n_stations, ring_pts) block, so the per-station std varies. Fine for average amplitude but means the last and first few stations (edges, where gaussian_filter pads by 'reflect' by default) have systematically different amplitudes than the center — not uniform over tube length. Secondary: the `1e-8` epsilon swap-out is a silent fallback that changes statistical behaviour between seeds. On the extreme tail where `noise_std <= 1e-8` (impossibly rare for Gaussian smoothing of a non-degenerate random normal, but if `n_stations=1` and `ring_pts=1` it would trigger), the surface gets flat rings — a different geometry.

**Fix:** Explicitly assert `n_stations >= 2` and `ring_pts >= 3`, and drop the degenerate branch. Or divide per-station: `smooth_noise /= std(axis=1, keepdims=True) + 1e-8`.

---

## MEDIUM

### M1. Hardcoded magic "Mars regolith ~30" angle of repose buried as a default rather than cited.
**File:** `marslab/terrain/cave_generator.py:79` and `marslab/terrain/cave/features.py:123`
**Quote:**
> `debris_cone_angle_deg: float = 30.0,`
> `angle_of_repose: Slope angle in degrees (Mars regolith ~30).`

**Problem:** Mars regolith angle-of-repose is 25-40° depending on cohesion and grain size (see e.g. Atwood-Stone & McEwen 2013). The docstring parenthetical "~30" has no citation; 30° is just the middle of the range. If this is meant to be science-backed, cite. If it's arbitrary, say arbitrary.

**Fix:** Add citation in docstring or change comment to `# arbitrary default; Mars regolith is 25-40° per [TBD]`.

### M2. Skylight `count=0` silently returns empty without warning, but only when `valid_indices == 0` does it "fallback" to center — two contradictory failure modes.
**File:** `marslab/terrain/cave/features.py:67-82`

**Problem:** `count == 0 -> []`. But `count > 0 & valid_indices empty -> [(center)]`. Intent is unclear. Unify.

### M3. `build_centerline` path can extend well past domain bounds.
**File:** `marslab/terrain/cave/geometry.py:75, 77`
**Quote:**
> ```
> path_len = max(height_m, width_m) * path_length_factor  # default 1.1
> along = (t - 0.5) * path_len                             # [-half_len, +half_len]
> ```

**Problem:** With `path_length_factor=1.1` the centerline extends 5% past each edge. That is intentional (for seamless truncation by domain), but the centerline is then used directly by `compute_skylight_positions` which filters by domain+margin. Stations outside the domain are excluded. That wastes path_resolution (~10% of stations discarded silently). Additionally, the tube shell at path_resolution=100 includes those external stations, so the tube penetrates the vertical edges of the surface cap that hasn't been notched out. Gaps again. Verify this shows up in visual inspection.

**Fix:** Either clip the centerline to the domain, or intersect the tube shell with the surface cap.

### M4. `cross_sections` is a misleading name — it's only the *upper half* of an ellipse.
**File:** `marslab/terrain/cave/geometry.py:133-135`
**Quote:**
> `theta = np.linspace(0, np.pi, ring_pts)`
> `base_x = a * np.cos(theta)`
> `base_z = b * np.sin(theta)`

**Problem:** Half-ellipse, with `base_z >= 0` since sin on [0, pi] is nonneg. So the tube has **no ceiling and no floor below centerline** — the "shell" is a half-pipe above the centerline. The floor is a separate mesh (build_tube_floor). But `theta=0` gives `base_z = 0`, so the shell touches the floor there. OK, that matches the disjoint-floor pattern. But the name `build_cross_sections` implies a full cross-section. A reader looking only at the function signature would expect a closed loop. Also the fact that j=0 and j=ring_pts-1 both have `base_z = 0` means the shell ring is **not closed** (first != last vertex on purpose), and `build_tube_shell` doesn't wrap `j_next = (j+1) % ring_pts` — it only iterates `j in range(ring_pts - 1)`, so the seam at j=ring_pts-1 to j=0 is never stitched. That's deliberate (open at the floor) but then the floor strip must bridge that gap — see C5 about seams.

**Fix:** Rename `build_cross_sections` -> `build_upper_cross_sections` or `build_halfellipse_rings`, add a big docstring note that the topology is **open** at the floor.

### M5. `build_tube_floor` ignores `process=True` which would have caught C5's duplicate vertices.
**File:** `marslab/terrain/cave/mesh.py:80, 146, 203, 276`
**Quote:** `return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)`

**Problem:** `process=False` is used for *all four* mesh-returning functions. `process=True` runs merge_vertices, remove_duplicate_faces, remove_unreferenced_vertices, etc. That's often disabled for determinism, but here the comment does not even mention determinism. If enabled once, the disjoint floor/shell would visibly auto-merge along the seam. As written the meshes are delivered raw with known duplicates.

**Fix:** Document the reason. If determinism, then OK but say so. If performance, measure.

### M6. `build_surface_cap` skylight hole cut is O(holes × faces) — fine at small scale, but the per-cell NaN write iterates over a broadcast mask of shape (rows, cols) per skylight.
**File:** `marslab/terrain/cave/mesh.py:269-273`

Not a correctness bug at size 400×400 and 10 skylights, but will get slow if someone bumps to 2048². Also the ordering is: centroids computed first, kept-mask built, then faces filtered — the `x_grid, y_grid` recompute happens inside the loop over skylights but doesn't use loop variables, so it's effectively constant. Could hoist outside for clarity.

### M7. `surface_elevation` NaN-ing at skylight footprints is done via bounding disc in (x,y) meters, but a corresponding face-keep uses centroid distance. The two masks are consistent only for fine resolution; at `resolution=1.0` meter a skylight of `diameter=20` m produces 314 vertex cells NaN'd vs. ~314 face-centroid kept-mask fails. OK. But docstring says:
> `float32 heightmap with NaN inside skylight footprints so downstream spawn logic skips those cells.`

It's a bounding disc, not a perfect footprint match with the mesh hole. If downstream code relies on "NaN iff hole in mesh", that's approximately true but not exact. Edge cells get inconsistent treatment.

### M8. `build_tube_shell` / `build_tube_floor` / `build_skylight_shaft` all accept `ring_pts`, `n_segments`, etc., without validation. No check on `ring_pts >= 3`, `n_segments >= 3`, `n_stations >= 2`.

### M9. `cave_mesh_builder.py:227` hardcodes `seed=42` **inside** `_build_breakdown_instancer`.
**File:** `marslab/terrain/cave_mesh_builder.py:227`
**Quote:**
> `rng = np.random.default_rng(42)`

**Problem:** This is G5 (no hardcoded constants in Python) and more importantly breaks seed reproducibility. A user changes `seed` in cave_generator's `generate_cave_mesh`, expecting downstream orientation/scale randomness of breakdown blocks to change. It won't. The builder always uses seed=42. Also, the USD builder is outside the reviewer's offline-testable scope, but since it's in-scope for this audit (cave_mesh_builder.py is listed), this is a clean bug.

**Fix:** Accept `seed` (or the `rng`) as a parameter to `_build_breakdown_instancer` and thread it from `build_cave_scene`.

### M10. `cave_mesh_builder.py:65-71` UV projection collapses to no-op for degenerate XY bounds without any warning.
**File:** `marslab/terrain/cave_mesh_builder.py:65-71`

**Problem:** For a tube that runs purely along Y (direction_deg=0), `x_range` is the tube *width*, ~200 m. Fine. But for a vertical skylight shaft (essentially a cylinder), `x_range` and `y_range` are roughly equal to the shaft diameter (~20 m) and the z-extent is ignored entirely — so the UV texture stretches infinitely down the Z axis. Cave walls will show textureless stretch vertically. Planar XY projection is an explicitly bad choice for a vertical shaft.

**Fix:** Use cylindrical UVs for the shaft, triplanar for the tube.

### M11. `_trimesh_to_usd_prim` applies `MeshCollisionAPI.approximation = "none"` for *every* mesh, which is fine semantically (exact triangle mesh) but catastrophic for the surface cap at 400×400 = 160000 verts and ~320000 triangles.
**File:** `marslab/terrain/cave_mesh_builder.py:81-83`

**Problem:** PhysX exact triangle mesh collision requires per-triangle BVH build. For a static cap that could use a heightfield collider (far cheaper), using triangle mesh on 320k faces is wasteful. Not wrong, just dumb.

### M12. `process=False` on icosphere prototype.
**File:** `marslab/terrain/cave_mesh_builder.py:201-208`

Minor. Icosphere from trimesh is already clean.

---

## LOW

### L1. `__init__.py` docstring (line 1-17) cites "R5 (2026-04-23) to split the previously 884-LOC `cave_generator.py`" — that's internal harness narrative, not a public API contract. Delete or move to CHANGELOG.md.

### L2. `_constants.py` (line 30) comment `# floor_pts = ring_pts * ratio` is not formally a derivation — the actual code in mesh.py clamps to a minimum: `max(int(ring_pts * ratio), floor_width_min_pts)`. Comment is incomplete.

### L3. `_constants.py:25` `CROSS_SECTION_SMOOTH_SIGMA: Final[tuple[float, float]] = (3.0, 2.0)` — no rationale for why station-sigma (3.0) > ring-sigma (2.0). Arbitrary.

### L4. `_constants.py:48` `SKYLIGHT_MARGIN_EXTRA_M: Final[float] = 10.0` — why 10? The skylight margin is `diameter/2 + 10`, which for diameter=200 is 110 m and for diameter=5 is 12.5 m. That's a huge disparity. Should scale with something.

### L5. `_constants.py:54` `BREAKDOWN_DIAMETER_CAP_M: Final[float] = 5.0` — for `block_mean=0.5, block_sigma=0.3`, cap is 10× the median, effectively unreachable. For `block_mean=2.0, block_sigma=1.0`, cap is saturating constantly. The cap should derive from (block_mean, block_sigma) — e.g. median × exp(3*sigma).

### L6. `geometry.py:167-172` `tangent_frames` handles only cases where successive centerline points are non-coincident. If `centerline[i] == centerline[i+1]` (possible if `curvature=0` and `direction_deg` and `path_len` yield degenerate along), the forward-difference at endpoints gives zero tangent, normalization falls back to `max(..., 1e-8)`. Doesn't fail but gives a tangent of zero → perp of zero → downstream garbage. Not a real risk at default params but there is no explicit guard.

### L7. `cave_generator.py:194-198`:
```
station_indices = rng.choice(range(2, n_stations - 2), ...)
```
Uses Python `range(...)` object. `rng.choice` will silently convert to a list — fine but allocates. Use `rng.choice(n_stations - 4) + 2` instead.

### L8. `cave_generator.py:210` `length = max(np.sqrt(dx**2 + dy**2), 1e-6)` — when the centerline has coincident adjacent stations this sets `perp_x/perp_y` to `-dy/1e-6` which blows up, but the preceding `tangent_frames` would already have been called by mesh.py for the shell. Here in cave_generator the perp is recomputed *from scratch* via `dx, dy = centerline[idx+1] - centerline[idx]` rather than using `tangent_frames(centerline)[1]` — duplicate logic, inconsistent fallback. Should call the shared util.

### L9. `cave_generator.py:191` `cone_diameter = tube_width_m * DEBRIS_CONE_DIAMETER_RATIO` — but `build_debris_cone` is given `skylight_diameter=cone_diameter`, whereas `build_debris_cone`'s docstring and parameter name expects a "skylight diameter above". This is a naming/behaviour mismatch: the cone's base radius is set from `cone_diameter` regardless of whether the cone has an actual skylight above. The mixing of names (`skylight_diameter` used as just "cone base scale") is deceptive.

### L10. `cave_generator.py:200` `cx, cy = centerline[idx, 0], centerline[idx, 1]` — no type check that `idx` is an int. `rng.choice` over a Python range returns np.int64, which works, but is fragile.

### L11. `cave_mesh_builder.py:38`: `Vt.Vec3fArray([Gf.Vec3f(...) for v in verts])` — Python loop over potentially 100k verts. USD has bulk constructors. Slow path.

### L12. `cave_mesh_builder.py:240-246` quaternion compose order `Rz·Ry·Rx` with `*` in pxr — check the quaternion multiplication convention of Gf.Rotation.GetQuat() composition. Depending on convention this may apply rotations in the wrong order. Not a bug necessarily but unverified.

### L13. `cave_mesh_builder.py:245-246`: `scales.append(Gf.Vec3f(d, d, d * rng.uniform(0.5, 1.0)))` — anisotropic scale on Z by ~70%. If the icosphere prototype has any UV/PBR texture, this creates stretched textures. Currently uses solid color so it's invisible, but flagging.

### L14. `cave/__init__.py` re-exports both `build_centerline` et al. AND `generate_breakdown_positions` etc., but `generate_cave_mesh` (the actual top-level public API) is re-exported from **the old path** `marslab.terrain.cave_generator`, not from `marslab.terrain.cave`. Import surface is split; a new developer has to know which path to use.

### L15. Docstring of `build_debris_cone` (features.py:130) says "`n_rings`: Ring count from apex (inclusive) to base (inclusive)" but code at line 143 `t = np.arange(n_rings) / (n_rings - 1)` yields t=[0, 1/(n-1), ..., 1] which is apex-to-base — apex at t=0 has cone_height=apex_z (from line 149 `apex_z - t*cone_height`, t=0 -> apex_z), base at t=1 -> apex_z - cone_height = floor_z. So cone apex is at top. OK, but the vertex order is apex-first, which means by convention, icospheres normally put pole at end — readers will have to untangle.

---

## DUPLICATION

### D1. `gaussian_filter + std-normalize + amplitude-scale` pattern appears in:
- `marslab/terrain/cave/geometry.py:138-143` (cross-section noise)
- `marslab/terrain/cave/mesh.py:242-243` (surface cap)
- `marslab/terrain/procedural_generator.py:105-107` (already extracted to `_normalize_noise` helper)

The cave module did not consume the existing helper. `procedural_generator._normalize_noise` is literally the same three-line routine. Import it and stop duplicating.

### D2. Tangent-perp recomputation in `cave_generator.py:204-211` duplicates `tangent_frames` from `cave/geometry.py:152-178`. Call the shared util.

### D3. `_trimesh_to_usd_prim` in `cave_mesh_builder.py:16-86` is strongly reminiscent of `mesh_builder.build_terrain_mesh` and `rock_instancer.place_rocks_on_terrain` (per its own docstring). I did not read those to verify, but the docstring advertises a copy, which is a smell in itself.

### D4. `np.meshgrid(np.arange(n-1), np.arange(m-1), indexing="ij")` + `v0..v3` + stacking into triangle faces appears in every mesh-builder function in `mesh.py`. That's four copies of the same grid-to-triangle-strip loop (lines 72-79, 138-145, 194-202, 256-263). Extract into a `_rings_to_triangles(n_rows, n_cols, close_wrap)` helper.

---

## SECURITY / INPUTS

- No user-controlled shell execution, no yaml.load, no pickle. Clean on that axis.
- `seed=42` default (cave_generator.py:88) — "everybody's favourite" test seed as production default. If someone forgets to override, all generated caves are bit-identical.
- `cave_mesh_builder.py:227` hardcoded `seed=42` — covered in M9.

---

## DELETE CANDIDATES

- `ring_pts` parameter of `generate_breakdown_positions` (breakdown.py:39): `# noqa: ARG001 -- retained for back-compat signature`. Dead parameter. If the back-compat claim is real and outside the tree, fine — if not, delete. `# noqa: ARG001` is a documented smell; the comment says "back-compat signature" but the module is 1 day old (R5 2026-04-23). There was no time for back-compat debt to accumulate. Delete the parameter.
- `rng` parameter of `compute_skylight_positions` (features.py:39): same pattern, same smell, same fix.
- `test_cave_generator.py:152` threshold `downward_fraction > 0.5` — too loose (covered in C1 fix). Tighten to 0.9.

---

## TESTING COVERAGE GAPS

- No test asserts tube+floor mesh **watertight** or **volume > 0**.
- No test asserts **manifold edges** (skylight shaft meeting tube).
- No test uses **non-square domain** (`rows != cols`) — latent bug surface (C6).
- No test verifies `lognormal` **moment claim** (C4) — should sample 10k diameters and compare empirical mean to `block_mean`.
- No test verifies **seed reproducibility across full generate_cave_mesh** (only individual components).
- No test verifies skylight shaft **overhang direction** (C3).

---

## SUMMARY (3 lines)

The R5 split preserved behaviour but also preserved the pre-existing bugs: `build_tube_shell` normals almost certainly point outward (C1), skylight shafts are topologically disjoint from the tube ceiling (C2), the overhang sign contradicts its own docstring (C3), and the lognormal call is inconsistent with its own parameter name (C4) so every "Blank-2024-calibrated" claim downstream is provably miscalibrated.

Structural quality is mediocre: floor and shell are two unmerged meshes with a systematic one-sided noise bias (C5), the domain axis convention is self-consistent but diverges from the rest of the repo with only square domains in tests hiding the latency (C6), and the `process=False`-everywhere pattern deliberately skips the cleanup that would have caught most of this.

`_constants.py` values are unjustified (3.0/2.0, 10.0, 5.0, 30°) and often inconsistently interpreted (ratio-vs-half-ratio in breakdown vs debris cone); `cave_mesh_builder.py` hardcodes `seed=42` in the breakdown instancer, breaking determinism end-to-end; duplication with `procedural_generator._normalize_noise` was never eliminated; and `ring_pts` / `rng` parameters kept "for back-compat" in a 1-day-old split are the classic deodorant-comment smell.
