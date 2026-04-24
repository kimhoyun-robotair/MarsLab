# Reviewer 2 Audit — marslab/rendering/ + marslab/gui/

## 메타

- **Reviewer:** Reviewer 2 (hostile external peer)
- **Date:** 2026-04-24
- **Scope:** 7 files
  - `marslab/rendering/__init__.py`
  - `marslab/rendering/atmosphere_fog.py`
  - `marslab/rendering/render_settings.py`
  - `marslab/rendering/sky_renderer.py`
  - `marslab/rendering/sun_renderer.py`
  - `marslab/gui/__init__.py`
  - `marslab/gui/atmosphere_panel.py`
- **Explicit exclusions:** `CLAUDE.md`, `PLAN.md`, `.claude/`, `work_log/` (not read).
- **Policy:** Internal jargon (G1-G13, P1/P2/P3, Oracle parity, offline-first, R2/R3/R4, "G5", etc.) is treated as *comments-as-deodorant* smell. Citing a guideline does not close a finding.
- **Severity counts (see below):** CRITICAL 3, HIGH 6, MEDIUM 9, LOW 7, DELETE 2, WATCHLIST 4.

---

## Findings

### CRITICAL

#### C1. `atmosphere_panel.py:166` — unconditional dict key access will raise KeyError in any degraded/alternate caller
`/home/hoyunkim/MarsLab/marslab/gui/atmosphere_panel.py:166`
```python
sol_seconds = self._state["sol_duration_seconds"]
```
**Problem.** The accompanying comment brags that the old `.get("sol_duration_seconds", 88642.0)` fallback was *intentionally deleted* because "build_atmosphere_state always seeds it." This is the textbook "comments as deodorant" anti-pattern: it replaces a safe default with a hard-fail, and the justification is an external invariant that isn't enforced here. The module's own docstring (line 14-16) advertises that the panel "degrades gracefully" when omni.ui is missing, but the inner state contract is now *stricter* than it used to be. Any future caller, mock, unit test, or alternate stage-1 script that constructs an `atmosphere_state` dict without that exact key will crash the UI redraw thread with a `KeyError` mid-frame. Crashing inside a UI callback from the render thread is worse than a stale label.

**Fix.** Revert to a safe default and validate once at construction time:
```python
# in __init__
required = {"tau", "sun_mode", "sun_azimuth_deg", "sun_elevation_deg",
            "time_of_sol", "sol_duration_seconds"}
missing = required - set(atmosphere_state)
if missing:
    raise KeyError(f"atmosphere_state missing required keys: {sorted(missing)}")
```
or accept the legacy default. Either way, do not crash on a hot path.

---

#### C2. `sun_renderer.py:51,93,96` — wrong USD rotation semantics: azimuth/elevation mapped to Euler XYZ is not a directional-light direction
`/home/hoyunkim/MarsLab/marslab/rendering/sun_renderer.py:48-51`
```python
xform = UsdGeom.Xformable(sun.GetPrim())
xform.ClearXformOpOrder()
rot_op = xform.AddRotateXYZOp()
rot_op.Set(Gf.Vec3f(-(90.0 - sun_pos.elevation_deg), 0.0, sun_pos.azimuth_deg))
```
**Problem.** A `UsdLux.DistantLight` shines along its local `-Z`. The code applies an `XYZ`-order Euler rotation where X is "tilt from zenith" and Z is "azimuth". In XYZ-order, X rotates first (in local space *before* Z), so the azimuthal rotation around world-Z is applied *after* an X-tilt that has already moved the light axis off the Y=0 plane. For elevation != 90, the resulting light direction is a *compound* rotation that does **not** correspond to the standard `(az, el)` spherical direction. Notably:

- At `el = 0` (horizon) the light lies in the world XZ plane but its projection onto the ground plane is not along azimuth direction; it is `[sin(az), 0, ...]` rather than `[sin(az), cos(az), 0]`.
- The sign/handedness of `azimuth_deg` assumes CCW around +Z but the convention in `sun_position.py:26` is `0=N, 90=E, 180=S, 270=W`, which is CW viewed from above. The code never negates to match.

This means "sun at east" might illuminate from south, breaking every shadow/Beer's-law visualization claim in the docstring.

**Fix.** Convert `(az_deg, el_deg)` into a direction vector and set an orientation op that maps `-Z` onto that direction (or use `AddRotateZYXOp` / `AddRotateYZXOp` depending on target convention, and negate azimuth explicitly):
```python
# NASA/meteorology: az measured CW from north, el from horizon.
d = _unit_vec_from_az_el(sun_pos.azimuth_deg, sun_pos.elevation_deg)  # shines FROM sun
# Light direction = -d (light shines toward origin)
rot = _rotation_from_minus_z_to(-d)  # use Gf.Rotation.SetRotateInto
xform.ClearXformOpOrder()
xform.AddOrientOp().Set(Gf.Quatf(rot.GetQuaternion()))
```
Add a unit test: for `(az=90, el=30)` the light dir should be `(-cos30·sin90, -cos30·cos90, -sin30) = (-0.866, 0, -0.5)`.

**확인 필요.** Depending on whether MarsLab's world frame is Z-up ENU (common for Mars) or Y-up (Isaac Sim default), the axis mapping differs. Need to verify the stage up-axis before fixing; otherwise fix could be cosmetic but still wrong.

---

#### C3. `atmosphere_panel.py:53,93,98` — Tau/azimuth/elevation slider *min/max* mismatch panel-promised contract, and there is no guard against `sun_mode` ever being initialized
`/home/hoyunkim/MarsLab/marslab/gui/atmosphere_panel.py:127-131`
```python
def _set_sun_mode(self, mode: str) -> None:
    self._state["sun_mode"] = mode
    self._update_slider_enabled()
    if self._mode_label:
        self._mode_label.text = self._format_mode_status()
```
**Problem.** The constructor never establishes `sun_mode` in `self._state` if the caller didn't seed it. The first `_update_slider_enabled()` at line 112 calls `self._state.get("sun_mode") == "manual"` returning False, so sliders are enabled in *auto* mode (line 134: `is_manual = ... == "manual"`). Combined with the fact that the azimuth slider's model always has `add_value_changed_fn(self._on_azimuth_changed)` (line 94) and that callback writes into `self._state` only if `sun_mode == "manual"` (line 120) — this silently drops the first azimuth change if the user nudges the slider before clicking "Manual". Users will think the UI is broken.

**Fix.** Seed `sun_mode` explicitly:
```python
self._state.setdefault("sun_mode", "auto")
```
at the top of `__init__`, and disable the sliders by default (they only make sense in manual mode). Better: gate the slider by `state` reactively and show a hint label "Click Manual to edit".

---

### HIGH

#### H1. `atmosphere_panel.py` — thread safety: omni.ui callbacks and the render loop share a mutable dict with zero locking
The module docstring (lines 9-12) states:
> The panel reads and writes a shared ``atmosphere_state`` dict. The render loop in run_stage2.py checks this dict every N frames and updates the renderers accordingly.

No `threading.Lock`, no `asyncio`-aware handoff, no `carb.events` marshaling. omni.ui callbacks (`add_value_changed_fn`, `clicked_fn`) fire on the Kit main-thread event queue; the render loop (Isaac Sim stage step) is also main-thread, so in practice you are probably fine *today*. But:
- `update_display()` (line 178) is documented as "Called from the render loop". If that render loop is ever moved to a worker thread (e.g. `omni.kit.async_engine`), writes like `self._az_model.set_value(...)` from one thread and slider callbacks from the UI thread will race on the model's internal C++ state.
- `_state` is a plain Python `dict`. Two concurrent writers produce interleaved state at mixed keys — the GIL won't save you from observing `{"tau": 0.3, "sun_mode": "manual_half_written"}` across a read pair.

**Fix.** Document the single-thread contract explicitly in the class docstring, or wrap mutations in a `threading.Lock`, or use `carb.events.IEventStream` / `omni.kit.app.post_to_main_thread_async`. At minimum, add an assertion at the top of `update_display()`:
```python
assert threading.current_thread() is threading.main_thread()
```

---

#### H2. `sun_renderer.py` / `sky_renderer.py` — `existing.IsValid()` without `IsA(UsdLux.DistantLight)` check: type confusion deletes arbitrary prims
`/home/hoyunkim/MarsLab/marslab/rendering/sun_renderer.py:34-36`
```python
existing = stage.GetPrimAtPath(sun_path)
if existing.IsValid():
    stage.RemovePrim(Sdf.Path(sun_path))
```
(Identical pattern in `sky_renderer.py:36-38`.)

**Problem.** Prim paths are user-configurable (`sun_prim_path` / `dome_prim_path` in `RenderingConfig`). If a user or another module has already placed *any* prim at `/World/SunLight` — a camera, an Xform, a mesh — this silently nukes it. The code never verifies the prim is a `DistantLight`/`DomeLight` before deletion.

**Fix.**
```python
existing = stage.GetPrimAtPath(sun_path)
if existing.IsValid():
    if not existing.IsA(UsdLux.DistantLight):
        raise RuntimeError(
            f"Prim at {sun_path} exists but is not a DistantLight "
            f"(got {existing.GetTypeName()}); refusing to overwrite."
        )
    stage.RemovePrim(Sdf.Path(sun_path))
```

---

#### H3. `atmosphere_fog.py:48` — `settings.set("/rtx/fog/fogColor", fog_color)` passes a Python `list[float]` when carb settings expects a 3-tuple/array; behavior is implementation-defined
`/home/hoyunkim/MarsLab/marslab/rendering/atmosphere_fog.py:41-48`
```python
fog_color = rendering_config.fog_color   # list[float] per RenderingConfig schema
settings.set("/rtx/fog/fogColor", fog_color)
```
**Problem.** `RenderingConfig.fog_color` (rendering.py:192) is declared `list[float]`. `carb.settings.set` for color paths historically wants either a `carb.Float3` / `tuple` of 3 floats or a flattened `float[3]` array. Passing a Python `list` is accepted by some carb builds but silently coerced into `float[]` (variable-length) on others, which the RTX renderer may read as 0-length and fall back to black fog. No validation, no defensive conversion.

**Fix.**
```python
settings.set("/rtx/fog/fogColor", tuple(fog_color))
```
Add a unit test (no Isaac Sim): assert `len(rendering_config.fog_color) == 3`. The pydantic `min_length=3, max_length=3` already guards the shape, so this is purely a call-site hygiene fix. Same treatment needed for `sun_color` in `sun_renderer.py`, though that one at least unpacks into `r, g, b`.

---

#### H4. `sun_renderer.py:91-96` — "update in-place" silently rewrites the first xform op regardless of its *type*
`/home/hoyunkim/MarsLab/marslab/rendering/sun_renderer.py:90-96`
```python
xform = UsdGeom.Xformable(prim)
ops = xform.GetOrderedXformOps()
if ops:
    ops[0].Set(Gf.Vec3f(-(90.0 - sun_pos.elevation_deg), 0.0, sun_pos.azimuth_deg))
```
**Problem.** `ops[0]` is not guaranteed to be an `RotateXYZOp`. If another system added a `TranslateOp` first (e.g., to relocate the stage root), setting a `Vec3f` on it moves the prim instead of rotating it. Worse, if `ops[0]` is a `ScaleOp`, the light suddenly collapses. The `configure_sun_light` path `ClearXformOpOrder()` sanitizes this, but `update_sun_light` trusts whatever order exists.

**Fix.**
```python
for op in ops:
    if op.GetOpType() == UsdGeom.XformOp.TypeRotateXYZ:
        op.Set(Gf.Vec3f(...))
        break
else:
    rot_op = xform.AddRotateXYZOp()
    rot_op.Set(Gf.Vec3f(...))
```

---

#### H5. `sun_renderer.py` / `sky_renderer.py` — `diffuse_fraction` parameter is documented as `(0-1)` but never validated; negative or >1 silently pass through to light intensity
`/home/hoyunkim/MarsLab/marslab/rendering/sun_renderer.py:16-32`
```python
def configure_sun_light(
    stage,
    sun_pos: SunPosition,
    intensity: float,
    diffuse_fraction: float,   # claimed (0-1)
    rendering_config: RenderingConfig,
) -> None:
```
And `configure_sky_dome` at `sky_renderer.py:46`: `base_intensity * diffuse_fraction`.

**Problem.** Passing `diffuse_fraction=2.0` doubles dome intensity and nothing complains. A bug upstream (e.g., dividing by zero path in COMIMART) can go straight into the renderer as a garbage brightness value. `sun_renderer.configure_sun_light` *takes* `diffuse_fraction` as a parameter but **never uses it** — so the docstring claim that it "[scales]… by diffuse_fraction" (by implication) is a lie for sun, but true for dome.

**Fix.** Validate at function boundary:
```python
if not 0.0 <= diffuse_fraction <= 1.0:
    raise ValueError(f"diffuse_fraction must be in [0, 1], got {diffuse_fraction}")
```
For `configure_sun_light` and `update_sun_light`: delete the unused parameter (see also L4).

---

#### H6. `atmosphere_fog.py:35` — `carb.settings.get_settings()` is a process-global singleton, called inside a function that takes a `stage` arg; `stage` is never used
```python
def configure_atmosphere_fog(stage, tau, rendering_config) -> None:
    ...
    settings = carb.settings.get_settings()
```
Docstring line 25: `stage: USD stage (unused but kept for API consistency).`

**Problem.** "API consistency" is not a justification — it's a prediction about future state. Dead arguments propagate through every caller and every test double. `set_render_mode()` doesn't take a stage argument at all, so the claimed "consistency" is already broken. The function is actually stage-independent (all effects happen via carb settings keys).

**Fix.** Drop the `stage` parameter:
```python
def configure_atmosphere_fog(tau: float, rendering_config: RenderingConfig) -> None:
```
Update all call sites. If an Isaac Sim API later makes fog stage-scoped, re-add it *then*.

---

### MEDIUM

#### M1. `render_settings.py:23-24` — `mode not in ("path_tracing", "ray_tracing")` duplicates pydantic `Literal["path_tracing", "ray_tracing"]`
```python
if mode not in ("path_tracing", "ray_tracing"):
    raise ValueError(...)
```
`RenderingConfig.mode` (rendering.py:172) is declared `Literal[...]` — pydantic already rejects bad values at construction. The runtime check is dead code. If you keep it for defense-in-depth, sync the allowlist by introspecting `Literal`:
```python
from typing import get_args
_allowed = get_args(RenderingConfig.model_fields["mode"].annotation)
if mode not in _allowed: raise ValueError(...)
```
Otherwise the tuple and the schema will drift.

#### M2. `sky_renderer.py:49-50` — `os.path.isfile` check silently swallows missing-HDRI; no log, no error
```python
if sky_params.hdri_texture_path and os.path.isfile(sky_params.hdri_texture_path):
    dome.GetTextureFileAttr().Set(sky_params.hdri_texture_path)
```
Docstring of MarsLab (and G5, if you care) says configs must fail loud on missing assets. Passing a bad HDRI path yields a colored-but-textureless sky and nothing in the log hints at why. Add a `logging.warning(...)` at minimum. Per the project error-handling standard (raise `FileNotFoundError` with full path), this should probably raise.

#### M3. `sky_renderer.py:80` / `sun_renderer.py:83` — constructing a typed light from a prim without verifying prim type
```python
dome = UsdLux.DomeLight(prim)
```
If some other code replaced the prim at `dome_path` with a non-DomeLight, `UsdLux.DomeLight(prim)` silently returns an invalid schema and the subsequent `.GetColorAttr().Set(...)` raises `pxr.Tf.ErrorException` deep in C++. Wrap:
```python
if not prim.IsA(UsdLux.DomeLight):
    raise RuntimeError(f"Prim at {dome_path} is not a DomeLight (got {prim.GetTypeName()})")
```

#### M4. `atmosphere_panel.py:42` — hardcoded window geometry `width=420, height=340` is a magic number
Counter to the project's own "all configs in YAML" mantra. Should be:
```python
ui.Window("MarsLab Atmosphere Control",
          width=gui_cfg.panel_width, height=gui_cfg.panel_height)
```

#### M5. `atmosphere_panel.py:50,58,62,68,85,102,108` — hardcoded hex ARGB colors (`0xFFDDDDDD`, `0xFFAAAAAA`, `0xFF444444`, `0xFF888888`)
Seven hex literals scattered through `_build_ui` are UI theme colors. G5 style aside, these should live in a theme dict or at least a `_COLORS = {...}` module constant, not inlined at every `ui.Label(..., style=...)`.

#### M6. `atmosphere_panel.py:133-148` — `_update_slider_enabled` swallows AttributeError *and* RuntimeError with `continue`
```python
try:
    widget.enabled = is_manual
except (AttributeError, RuntimeError):
    continue
```
The verbose comment (lines 135-140) *explains* why, but silently swallowing two broad exception types on every slider mode switch is a smell. It will mask regressions in omni.ui that should be reported. At minimum:
```python
except (AttributeError, RuntimeError) as exc:
    logging.debug("slider %s finalized: %s", attr, exc)
    continue
```
Also: the phrase "Model-level gating … already enforces state safety, so silently skipping here is behaviourally equivalent" is comments-as-deodorant: it is only true *right now*. If a future widget repurposes `.enabled` to mean "visible", this justification falls over.

#### M7. `sun_renderer.py:51,93,96` — triple-duplication of the same rotation expression
The formula `Gf.Vec3f(-(90.0 - sun_pos.elevation_deg), 0.0, sun_pos.azimuth_deg)` appears three times. Extract:
```python
def _sun_euler(sun_pos: SunPosition) -> Gf.Vec3f:
    return Gf.Vec3f(-(90.0 - sun_pos.elevation_deg), 0.0, sun_pos.azimuth_deg)
```
Then fix C2 in one place.

#### M8. `sun_renderer.py:40,84` / `sky_renderer.py:45,85` — `rendering_config.sun_intensity_scale` and `dome_brightness_scale` multiplication duplicated between create/update paths
```python
# configure: line 40
sun.GetIntensityAttr().Set(intensity * rendering_config.sun_intensity_scale)
# update: line 84
sun.GetIntensityAttr().Set(intensity * rendering_config.sun_intensity_scale)
```
Same pattern for dome `base_intensity = sky_params.brightness * rendering_config.dome_brightness_scale` at sky_renderer.py:45 and :85. Extract a helper; DRY.

#### M9. `atmosphere_fog.py:32-33` / `sky_dome.py:60-61` — `if tau < 0: raise` but no upper bound
Mars dust opacity is physically `[0, ~6]` (per the project's own config range). `tau=1e9` will happily compute an infinite fog density (`tau * fog_density_scale`). At a minimum document and enforce a soft upper bound in the schema (pydantic `ge=0, le=20`) rather than inside the fog module; currently there is no upper guard anywhere.

---

### LOW

#### L1. `atmosphere_fog.py:9` / `render_settings.py:8` — `import carb` with no exception handling
If the module is imported in a non-Isaac environment (e.g., during test collection), `ImportError` bubbles up. The docstring says "Requires Isaac Sim runtime" — fine — but tests that live under `tests/unit/` may collect this module via `__init__.py` re-exports and fail the whole suite. Guard the import or gate it behind a function-local `import`.

#### L2. `sky_renderer.py:53-78` — `update_sky_dome` falls back to `configure_sky_dome` without logging
The fallback path (line 76-78) can hide a larger architectural bug (prim being deleted behind the back of the update path). Add `logging.info("sky dome prim missing, re-creating at %s", dome_path)`.

#### L3. `sun_renderer.py:14-20` / `configure_sun_light` — docstring names `diffuse_fraction: Fraction of light that is diffuse (0-1).` but the function body ignores it
Lying docstring. Either delete the param (see H5) or *use* it (e.g., apply to a fill-light adjustment). Right now this is a foot-gun: a caller reads the docstring, passes a value, and it's silently discarded.

#### L4. `rendering/__init__.py` — one-liner docstring, no public API export
```python
"""Mars rendering configuration for Isaac Sim."""
```
Doesn't re-export `configure_sun_light`, `configure_sky_dome`, `configure_atmosphere_fog`, `set_render_mode`. Callers must use full paths. Either intentionally "no public surface" (then document it) or add an `__all__`.

#### L5. `atmosphere_panel.py:37` — `self._state = atmosphere_state` stores a non-typed reference
`atmosphere_state: Dict[str, Any]` — consider a `TypedDict`:
```python
class AtmosphereState(TypedDict):
    tau: float
    sun_mode: Literal["auto", "manual"]
    sun_azimuth_deg: float
    ...
```
Would catch C1/C3 class of bugs at type-check time.

#### L6. `atmosphere_panel.py:116-125` — three near-identical one-line callbacks
```python
def _on_tau_changed(self, model): self._state["tau"] = model.as_float
def _on_azimuth_changed(self, model):
    if self._state.get("sun_mode") == "manual": self._state["sun_azimuth_deg"] = model.as_float
def _on_elevation_changed(self, model):
    if self._state.get("sun_mode") == "manual": self._state["sun_elevation_deg"] = model.as_float
```
Extract a generic `_bind_slider(model, state_key, guard=None)` helper; three callbacks become data.

#### L7. `atmosphere_fog.py:37` — `fog_cfg = rendering_config.fog` then `fog_cfg.color` is defined in the schema (default `(0.83, 0.47, 0.28)`) but **ignored** by the function in favor of `rendering_config.fog_color`
Schema comment (rendering.py:75-82) calls this "reserved" for future use. Dead config field. Either wire it up (allow `fog_cfg.color` to override the top-level `fog_color`), or delete it. Reserved config fields rot.

---

### DELETE

#### D1. `rendering/__init__.py` (1 line) — candidate for content expansion, not deletion
Not actually a deletion candidate; I listed it here only because it's a valid 2-line stub. No action required unless the project standard mandates `__all__`.

#### D2. `atmosphere_panel.py:133-148` — the entire `_update_slider_enabled` exception-handling block
Delete the `try/except (AttributeError, RuntimeError)` once it's confirmed the widget lifetimes are actually safe (the comment admits "Model-level gating … already enforces state safety, so silently skipping here is behaviourally equivalent"). If it's behaviourally equivalent, the code that justifies the skip is the code to delete. Keep the loop, drop the try/except, let real bugs surface.

---

### WATCHLIST

#### W1. Module docstrings advertise "no code copying / no naming from reference codebases" compliance
Comments like "Mars-appropriate color", "butterscotch", "Beer's law" on `sun_renderer.py:3-6`, `sky_renderer.py:1-3` — these read like justification-by-provenance. Not a bug, but watch for doc-drift: if the color values change without updating the "Bell et al. 2006 MER Pancam" citation in `rendering.py:141`, the comment becomes a lie.

#### W2. `atmosphere_panel.py` has no integration test for the case where omni.ui is missing
Docstring lines 14-16 promise graceful degradation guarded at import site in `run_stage2.py`. That guarantee is outside this module; I can't verify it here. Author should add a "omni.ui unavailable" unit test at the `run_stage2` boundary.

#### W3. The panel's `_tau_model`, `_az_model`, `_el_model` are never released
omni.ui models outlive the Python wrapper because C++ holds references to their callbacks. If `AtmospherePanel` is re-instantiated (e.g., scenario reload), you leak model/callback pairs. Add a `def destroy(self): self._window.destroy(); ...` method and call it from the scenario teardown.

#### W4. All four renderer functions claim to "avoid flicker during the dynamic atmosphere render loop" by updating in-place, but none of them `stage.Save()` or flush
If the USD layer is set to a composed layer that doesn't propagate attribute sets until the next `stage.Save()` (e.g., a sublayered prim), the update_* functions would no-op. Worth verifying against the stage config.

---

## Summary

- CRITICAL: 3 (dict KeyError hot-path; sun rotation math; uninitialized sun_mode)
- HIGH: 6
- MEDIUM: 9
- LOW: 7
- DELETE: 2 (one trivial, one block)
- WATCHLIST: 4

The rendering layer has working plumbing but is sloppy about (a) USD prim-type verification before mutate/delete, (b) angle convention consistency between `SunPosition` semantics and Euler rotation application, and (c) promised-but-unenforced parameter contracts. The GUI panel is single-threaded-safe by accident of Isaac Kit's event model, not by design; it also includes the kind of comment-laden "we deleted the default because an external invariant holds" change (C1) that is guaranteed to regress under refactor.
