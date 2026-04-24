# Reviewer 2 — Hostile Audit: `marslab/math/` + `marslab/ros2_bridge/odometry_math.py`

Scope reviewed (every line):
- `/home/hoyunkim/MarsLab/marslab/math/__init__.py` (13 LOC)
- `/home/hoyunkim/MarsLab/marslab/math/quaternion.py` (177 LOC)
- `/home/hoyunkim/MarsLab/marslab/ros2_bridge/odometry_math.py` (100 LOC)

I did not read CLAUDE.md, PLAN.md, `.claude/`, or `work_log/`. Internal
tokens such as "P3 offline-first testing", "R3-A1", and "Oracle twin /
diff=0 policy" appearing inside source docstrings are treated as
private-project marginalia with zero evidentiary value and are flagged
under "lying docstring smell" throughout. Those references ask the reader
to trust conventions established elsewhere in the project; a hostile
outside reviewer cannot audit them and should not be expected to.

## Severity legend

- **BLOCKER** — correctness bug, wrong result under documented inputs
- **HIGH** — latent bug, silent corruption, contract violation
- **MEDIUM** — API/docstring inaccuracy, numerical hazard, weak validation
- **LOW** — style, naming, micro-duplication

---

## BLOCKERS

### B1. `quat_to_rpy` gimbal-lock branch is mathematically wrong (`marslab/math/quaternion.py:168-174`)

```python
# Gimbal-lock threshold: |sin(pitch)| > 1 - 1e-6 ⇒ roll indeterminate.
if abs(sin_pitch) > 1.0 - 1e-6:
    roll = 0.0
    yaw = float(np.arctan2(-2.0 * (x * y - w * z), 1.0 - 2.0 * (y * y + z * z)))
```

**Problem.** At pitch = ±π/2 the denominator `1 - 2·(y²+z²)` collapses
to **exactly 0** and the numerator reduces to ±sin(roll-yaw)·constant,
so `arctan2(·, 0)` always returns ±π/2 **regardless of the input**.
Empirical verification using the very formulas in this file:

| input rpy                | claimed recovery formula | actual returned yaw | correct combined angle |
|--------------------------|--------------------------|----------------------|-------------------------|
| (0.3, π/2, 0.5)          | above                    | **+1.5708**          | yaw−roll = 0.2          |
| (0.7, π/2, 0.1)          | above                    | **−1.5708**          | yaw−roll = −0.6         |
| (0.0, π/2, 0.8)          | above                    | **+1.5708**          | yaw−roll = 0.8          |
| (0.5, π/2, 0.0)          | above                    | **−1.5708**          | yaw−roll = −0.5         |

The function returns a constant ±π/2 on the entire gimbal-lock
manifold; all roll/yaw input information is destroyed. A correct
recovery uses

```python
yaw = 2.0 * np.arctan2(z, w)          # pitch = +π/2
# or
yaw = -2.0 * np.arctan2(z, w)         # pitch = -π/2
```

(or equivalently the signed form with `sign(sin_pitch)`), which I
verified reproduces the true `yaw − roll` combined angle.

**Fix.**

```python
if abs(sin_pitch) > 1.0 - 1e-6:
    roll = 0.0
    sign = 1.0 if sin_pitch > 0 else -1.0
    yaw = float(2.0 * sign * np.arctan2(z, w))
```

Unit tests in `tests/unit/test_rover_module.py` and
`tests/unit/test_odometry_math.py` do not exercise `quat_to_rpy`
(grepped: no call sites), so this bug is completely uncovered.
`quat_to_rpy` itself appears to have **no non-test call sites inside
`marslab/` today** (grep shows only the definition), which is the only
reason the bug has not produced a visible failure.  If and when a
caller starts using it (e.g., publishing odom yaw when the rover is
pitched on a crater slope > 89.9°) the returned yaw will be a
meaningless constant.

### B2. `quat_to_rpy` gimbal-lock citation is false (`marslab/math/quaternion.py:143-147`)

```python
"""
Inverse of :func:`rpy_to_quat`.  Uses the standard ZYX intrinsic
extraction; pitch is clamped to ``[-π/2, π/2]`` and, when the
asin argument saturates (gimbal lock), roll is set to 0 and yaw
absorbs the combined rotation — matching the convention used by
``tf_transformations.euler_from_quaternion(..., 'sxyz')``.
"""
```

I ran `tf_transformations.euler_from_quaternion((x,y,z,w), 'sxyz')` on
the exact quaternion produced by `rpy_to_quat(0.1, -1.5707960, 0.3)`
(i.e., 0.4 µrad off −π/2, well inside the function's own `1e-6`
saturation epsilon):

- `tf_transformations`: `(0.0999999998, -1.570795999, 0.299999999)` —
  recovers roll ≈ 0.1, yaw ≈ 0.3.
- marslab: `(0.0, -1.5707960, 1.5707955)` — collapses to roll=0,
  yaw=±π/2.

So the citation is wrong on two counts: the marslab fallback formula
does not agree with tf's handler, and (per B1) the formula itself is
broken. The docstring is a Fowler "comment as deodorant" — it claims
parity with tf without having been tested against tf.

**Fix.** After B1 is fixed, either re-cite and re-test against
`tf_transformations` / `transforms3d` or drop the citation entirely.

---

## HIGH

### H1. `rpy_to_quat` docstring claim "ZYX intrinsic" is ambiguous and disagrees with scipy (`marslab/math/quaternion.py:115-120`)

```python
"""
Uses the ZYX intrinsic convention (yaw around Z, then pitch around
Y, then roll around X) which is the URDF / ROS standard.  Pure
Python floats out so the result is JSON-serialisable and Isaac-Sim
``Xformable`` orient APIs accept it directly.
"""
```

The formula on lines 133-136 computes `R = Rz(yaw)·Ry(pitch)·Rx(roll)`
(I verified this against a manual matrix-multiply). In robotics
literature this is indeed called "ZYX intrinsic" or "XYZ extrinsic";
however, `scipy.spatial.transform.Rotation.from_euler('zyx', [y,p,r])`
produces a **different** matrix (scipy's "intrinsic zyx" is yet a
third convention). Any reader who sanity-checks the docstring with
`from_euler('zyx', …)` will get a mismatch and reasonably conclude
the code is wrong, even though it is actually right for the
URDF/ROS meaning.

**Fix.** Drop convention-jargon. State the math unambiguously:

```python
"""
The returned quaternion represents the rotation
``R = Rz(yaw) · Ry(pitch) · Rx(roll)``
applied to a column vector expressed in the parent frame.  This
matches the URDF ``<origin rpy="…"/>`` and ROS2
``tf_transformations.quaternion_from_euler(r, p, y, 'sxyz')``
conventions; the result disagrees with scipy
``from_euler('zyx', [y,p,r])`` (a different intrinsic/extrinsic
bookkeeping) — use ``from_euler('XYZ', [r,p,y])`` instead to
cross-check.
"""
```

### H2. `quat_inverse` silently accepts non-unit quaternions and returns garbage (`marslab/math/quaternion.py:35-54`)

```python
def quat_inverse(q: np.ndarray) -> np.ndarray:
    ...
    For a unit quaternion the inverse equals the conjugate: negate the
    vector part, keep the scalar.  The caller is responsible for keeping
    ``q`` unit-norm; this function does not renormalise.
```

This is a time bomb: `quat_inverse` is consumed by `quat_rotate_vec`,
`compute_odom_delta`, and `world_twist_to_body` — all in the hot
odometry publish path. If any upstream caller ever feeds a
non-normalised quaternion (Isaac Sim articulations produce quats that
drift by ~1e-5 over long sims; ROS2 subscribers can receive unnormalised
quats from user code), the result is the *conjugate*, not the
*inverse*, and every downstream pose/twist silently rotates by a
wrong amount. No assertion, no warning, no debug mode.

The policy "caller is responsible" is a C-style contract smell in a
pure-Python numerics module that costs nothing to enforce. At minimum
add:

```python
norm = float(np.linalg.norm(q))
if not 0.99 < norm < 1.01:
    raise ValueError(f"quaternion must be unit-norm, got |q|={norm:.6f}")
```

or, safer, renormalise with a logged warning. Document precisely
which callers have guaranteed unit-norm inputs; right now the chain
is uncheckable from the module itself.

### H3. `quat_rotate_vec` does not validate `q` shape itself, and the error message is misleading (`marslab/math/quaternion.py:100-110`)

```python
    Raises:
        ValueError: If ``v`` does not have shape ``(3,)`` (shape check on
            ``q`` is delegated to :func:`quat_inverse`).
```

The promise is that a malformed `q` produces a `ValueError`, but the
first operation on `q` is `quat_multiply(q, v_quat)` on line 109,
*before* `quat_inverse(q)`. So a bad `q` surfaces as a
`quat_multiply` error, not `quat_inverse`. The docstring is
technically wrong about which function raises, and the call order
here (multiply then invert) forces a double shape re-validation of
`q` (once in multiply, once in inverse) that the docstring tries to
paper over instead of fix.

**Fix.** Either:
1. Validate `q` once at the top of `quat_rotate_vec` and skip the
   delegated check, or
2. Call `quat_inverse(q)` **before** `quat_multiply` and keep the
   delegation language honest.

### H4. Float32 everywhere silently destroys odometry precision (`marslab/math/quaternion.py:51,70-71,104,107,110` and `odometry_math.py:64-71,96`)

Every function forces `dtype=np.float32`. Quaternion composition over
long horizons (e.g., `compute_odom_delta` called at 200 Hz for 20 min
= 240,000 composed rotations) accumulates floating error
proportional to `n·ε`; at float32 `ε ≈ 1.2e-7`, that's ~3e-2 rad of
drift — *dwarfing* any sensor noise. By contrast, only `quat_to_rpy`
on line 158 opts into `float64` (good) — but then the positions going
back to the caller in `compute_odom_delta` are float32 and lose the
precision immediately.

Worse, the inputs coming from Isaac Sim's articulation API are
**float64** by default; the cast to float32 at every call site is
destroying precision the caller already paid for.

**Fix.** Either:
- Preserve caller dtype (`dtype=q.dtype` if array, fallback to
  float64), or
- Use float64 uniformly and document the choice.

The float32 choice appears to be a premature micro-optimisation with
no mentioned rationale anywhere in the file.

### H5. `compute_odom_delta` asymmetric shape validation (`marslab/ros2_bridge/odometry_math.py:64-71`)

```python
cur_pos_world = np.asarray(cur_pos_world, dtype=np.float32)
init_pos_world = np.asarray(init_pos_world, dtype=np.float32)
if cur_pos_world.shape != (3,) or init_pos_world.shape != (3,):
    raise ValueError("position must have shape (3,)")
init_quat_inv = quat_inverse(init_quat_world)
...
delta_quat_odom = quat_multiply(init_quat_inv, np.asarray(cur_quat_world, dtype=np.float32))
```

- Positions are asserted `(3,)` with a decent error message.
- `init_quat_world` validation is delegated to `quat_inverse` (error
  will say "quaternion must have shape (4,)" — no indication *which*
  of the four quaternion parameters was malformed).
- `cur_quat_world` validation is delegated to `quat_multiply`, which
  will report both shapes of its *two* internal arguments — one of
  which is `init_quat_inv`, a name the user never supplied. Reading
  the error message "quaternions must have shape (4,), got (4,) and
  (3,)" will not tell the user that the faulty parameter was
  `cur_quat_world`.

This is a straightforward input-diagnosability regression compared to
the positions.

**Fix.** Validate all four inputs at the top of the function with
parameter-named error strings.

### H6. `world_twist_to_body` performs zero shape validation on its velocity inputs (`marslab/ros2_bridge/odometry_math.py:75-99`)

```python
def world_twist_to_body(
    linear_world: np.ndarray,
    angular_world: np.ndarray,
    cur_quat_world: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    ...
    q_inv = quat_inverse(cur_quat_world)
    linear_body = quat_rotate_vec(q_inv, linear_world)
    angular_body = quat_rotate_vec(q_inv, angular_world)
```

Shape validation for `linear_world` and `angular_world` is delegated
to `quat_rotate_vec`, which only checks `v.shape == (3,)` after
`q_inv` has been computed. Passing `linear_world=np.array([1, 2])`
raises `"vector must have shape (3,), got (2,)"` — fine — but
`angular_world` is never reached if `linear_world` fails, and the
caller has no way to know from the error which parameter was wrong.
Given the trivial two-line fix, the inconsistency with
`compute_odom_delta` is pure oversight.

### H7. NaN / Inf inputs silently propagate through the entire pipeline

Tested: feeding `q = np.array([np.nan, 0, 0, 0])` into `quat_to_rpy`:

- `sin_pitch = 2·(w·y − z·x) = NaN`
- `np.clip(NaN, -1, 1) = NaN`
- `abs(NaN) > 1 − 1e-6` evaluates `False` (IEEE 754 NaN comparison
  rule), so control flow falls into the non-gimbal branch.
- All three returned angles are NaN.

Same behaviour for `inf`. Every function in this module silently
propagates NaN/inf. `odom.pose.pose.position.x = NaN` is published to
ROS2 without complaint; SLAM tooling downstream may then misbehave in
ways that are hard to trace back.

**Fix.** At the top of the odometry-level entry points (`compute_odom_delta`,
`world_twist_to_body`) add

```python
if not np.isfinite(q).all():
    raise ValueError(f"{name} contains non-finite values: {q}")
```

for each input. Low-level quaternion helpers can stay silent for
speed, but the publishable-to-ROS boundary should guard.

---

## MEDIUM

### M1. `rpy_to_quat` has no shape validation (`marslab/math/quaternion.py:113-137`)

Signature is `(roll: float, pitch: float, yaw: float)` but accepts
numpy scalars, arrays of shape `(1,)`, and 0-d arrays, returning
Python floats via `float(...)`. If a 1-d array slips in,
`float(np.array([0.3]))` works; `float(np.array([0.3, 0.4]))` raises
a cryptic `TypeError: only size-1 arrays can be converted to Python
scalars`.

Prefer explicit `roll = float(roll)` cast at the top, or a
`numpy.ndim != 0` check.

### M2. `rpy_to_quat` returns non-normalised quat when caller passes garbage angles (`marslab/math/quaternion.py:129-137`)

For legitimate finite input, the output is mathematically unit-norm
by construction — no issue. But if any input is `np.pi*2 + ε` or
similar, the output remains mathematically unit-norm; if an input is
`nan`/`inf`, the output is `(nan, nan, nan, nan)`. No finite-input
guard. See H7.

### M3. `quat_to_rpy` casts to float64, but surrounding modules cast to float32 (`marslab/math/quaternion.py:158`)

```python
q = np.asarray(q, dtype=np.float64)
```

Inconsistent with `quat_inverse` / `quat_multiply` / `quat_rotate_vec`
which all use `float32`. Either this function is right and the
others are wrong, or vice versa. Decide and unify. (See H4.)

### M4. `marslab/math/__init__.py` documents re-exports but exports nothing (`marslab/math/__init__.py:1-13`)

```python
"""Pure-Python numerical helpers for MarsLab (no Isaac Sim, no ROS2).
...
Current contents:

* :mod:`marslab.math.quaternion` — scalar-first ``[w, x, y, z]``
  quaternion algebra and ZYX intrinsic RPY ↔ quaternion conversion.
"""
```

There is no `from .quaternion import …`, no `__all__`. Users who
try `from marslab.math import quat_inverse` get `ImportError`. If
the intent is a proper sub-package façade, re-export the public
names; if the intent is "users import from the submodule", drop the
"package consolidates…" language because nothing is consolidated at
the package root.

### M5. Naming clash with Python stdlib `math` (`marslab/math/__init__.py`)

Naming this package `marslab.math` is fine in isolation but creates a
hostile import environment: any file inside `marslab/math/` that
tries `import math` will get the package, not the stdlib.
`marslab/math/quaternion.py` dodges this by using `numpy` only, but
any future module in this package that wants `math.sin` will need
`from __future__ import absolute_import` dance or rename. Future
foot-gun; consider `marslab.mathx`, `marslab.numeric`, or
`marslab.linalg`.

### M6. `quat_multiply` wastes a copy on every call (`marslab/math/quaternion.py:70-71`)

```python
q1 = np.asarray(q1, dtype=np.float32)
q2 = np.asarray(q2, dtype=np.float32)
```

`np.asarray(arr, dtype=X)` silently copies when `arr.dtype != X`.
Upstream callers in `main_loop.py` pass float64 arrays from Isaac Sim
every tick; this creates two float32 copies per Hamilton product, at
~200 Hz that's 400 small allocations/sec in the hot path. See H4.

### M7. `quat_rotate_vec` triple-multiplies when a single matrix-rotation would suffice (`marslab/math/quaternion.py:104-110`)

Two nested `quat_multiply` calls = 2 × 16 mul + 12 add = 56 ops,
allocating three intermediate 4-vectors. The standard vector-form
shortcut is

```python
t = 2.0 * np.cross(q[1:], v)
return v + q[0] * t + np.cross(q[1:], t)
```

— 15 mul + 9 add, one allocation, and still pure NumPy. At 200 Hz
odometry with three vec-rotations per tick (pos, lv, av) this is a
3–4× speedup. Non-blocking but leaves performance on the table.

### M8. Lying/non-auditable docstring references to "Oracle twin diff=0 policy" and "R3-A1" (`marslab/math/quaternion.py:16-25` and `marslab/ros2_bridge/odometry_math.py:26-35`)

```python
"""
...
This module is the single source of truth for quaternion helpers
previously duplicated across:

* ``marslab.ros2_bridge.odometry_math`` (quat_inverse / quat_multiply /
  quat_rotate_vec) — now re-exported from here.
* ``marslab.robots.rover`` (rpy_to_quat) — now re-exported from here.
* ``scripts/phase1/run_stage3_monolithic_new.py`` (rpy_to_quat) — now
  imported from here.

The Oracle twin ``scripts/phase1/run_stage3_monolithic.py`` keeps its
local ``rpy_to_quat`` copy (diff=0 policy).
"""
```

Problems:

- "R3-A1" is a private ticket identifier; an outside reader cannot
  audit what it means or whether the promise was kept.
- "Oracle twin diff=0 policy" is unsourced. I verified by grep that
  `scripts/phase1/run_stage3_monolithic.py:91` and
  `:1215-1237` do contain local copies of `rpy_to_quat`,
  `quat_inverse`, `quat_multiply`, `quat_rotate_vec` — so there is
  **active duplicated source** that any future edit to
  `marslab/math/quaternion.py` will silently diverge from. The only
  thing preventing that is human process (the "Oracle diff=0 policy")
  and no CI test enforces equivalence.
- The phrase "now re-exported from here" at the top of
  `odometry_math.py` relies on Python module-level attribute access
  via `noqa: F401` imports; there is no `__all__` declaration, so
  the API surface is defined by imports order and is brittle to
  cleanup ("ruff --fix" could strip the unused imports if the noqa
  is ever removed).

**Fix.**

1. Add `__all__` to `odometry_math.py` to pin the re-export contract
   mechanically.
2. Add a unit test that asserts the three Oracle-local copies in
   `scripts/phase1/run_stage3_monolithic.py` produce byte-identical
   outputs to `marslab.math.quaternion` — so diff=0 is enforced by CI
   rather than by reviewer vigilance.

### M9. `quat_inverse`/`quat_multiply`/`quat_rotate_vec` docstrings use Unicode ⊗ and π (`marslab/math/quaternion.py:58,91,109, others`)

```
"""Hamilton product ``q1 ⊗ q2`` of two ``[w, x, y, z]`` quaternions."""
```

Fine for humans; breaks some doc-rendering pipelines (older
Sphinx+cp1252 on Windows, some grep tooling). Project-wide decision,
but if there's a coding standard against non-ASCII in code, this is
a violation. Note that the RHS of `# Gimbal-lock threshold:
|sin(pitch)| > 1 − 1e-6 ⇒ roll indeterminate.` on line 168 uses
`−` (minus sign U+2212) rather than ASCII `-` — will bite anyone
who copy-pastes that comment into a formula.

### M10. `compute_odom_delta` docstring drops the sign convention (`marslab/ros2_bridge/odometry_math.py:38-63`)

```python
"""Convert a world-frame rover pose into odom-frame pose.

The odom frame is defined as the initial world pose.
```

Missing: what "initial" means — is it `t=0` of the simulation, first
frame after physics warm-up, the frame after Isaac Sim's URDF import
settling, or the nav2 start? Consumers downstream expect a specific
anchor. The top of the module (line 6) hand-waves "the initial world
pose of the rover" but never specifies *when*.

**Fix.** Specify the exact time origin or link to the caller that
seeds `init_pos_world` / `init_quat_world`.

---

## LOW

### L1. `quat_rotate_vec` allocates a shape-(4,) intermediate (`marslab/math/quaternion.py:107`)

```python
v_quat = np.array([0.0, v[0], v[1], v[2]], dtype=np.float32)
```

Python list literal in a hot path. Prefer `np.empty(4, …); v_quat[0]=0; v_quat[1:]=v` or use the formula rewrite in M7.

### L2. Return-dtype cast redundant (`marslab/math/quaternion.py:110`)

```python
return result[1:4].astype(np.float32)
```

`result` is already float32 (line 84 return), so `.astype(float32)`
with default `copy=True` is a pure waste.

### L3. `quat_inverse` array literal instead of conjugate negation (`marslab/math/quaternion.py:54`)

```python
return np.array([q[0], -q[1], -q[2], -q[3]], dtype=np.float32)
```

Prefer `out = q.copy(); out[1:] = -out[1:]; return out`. Minor.

### L4. Type hint `Tuple[float, float, float, float]` imports `Tuple` from typing but Python 3.10+ is specified — use `tuple[float, float, float, float]` (`marslab/math/quaternion.py:30,113,140`)

`from typing import Tuple` is PEP 585-deprecated style. If the
project standard really is "Python 3.10+" (see self-referential
hints in module docstrings), drop the import and use PEP 585 generics.

### L5. `odometry_math.py:22` imports `Tuple` even though only `compute_odom_delta` and `world_twist_to_body` use it (`marslab/ros2_bridge/odometry_math.py:22`)

Same PEP 585 remark as L4.

### L6. Module docstrings contain unverifiable implementation notes (`marslab/ros2_bridge/odometry_math.py:1-18`)

```python
"""Pure-Python quaternion + odometry helpers (no ROS2, no Isaac Sim).
...
    delta_pos_odom = R(q_init_inv) * (pos_world - pos_init_world)
    delta_quat      = q_init_inv ⊗ q_current_world
    body_twist      = R(q_current_inv) * world_twist
```

Good: the derivation is stated inline. Bad: no citation of which
ROS REP or Nav2 doc fixes the `nav_msgs/Odometry`
body-frame-twist convention. Add a pointer to REP 103 or Nav2 so a
future reader doesn't have to re-derive from scratch.

### L7. `test_odometry_math.py` imports helpers from `marslab.ros2_bridge.odometry_math`, pinning the re-export shim (`tests/unit/test_odometry_math.py:8-10`)

```python
from marslab.ros2_bridge.odometry_math import (
    quat_inverse,
    quat_multiply,
    quat_rotate_vec,
)
```

This means removing the `noqa: F401` re-exports in `odometry_math.py`
breaks the test suite even though the helpers' real home is
`marslab.math.quaternion`. Consider migrating the tests to import
from the canonical location and drop the shim later (adds a
follow-up debt if not done).

### L8. No explicit `__all__` anywhere (`marslab/math/quaternion.py`, `odometry_math.py`, `__init__.py`)

Without `__all__`, `from marslab.math.quaternion import *` re-exports
`np` and `Tuple`. Small surface pollution, large principle violation
for a "single source of truth" module.

---

## Summary (3 lines)

1. **B1** — `quat_to_rpy`'s gimbal-lock branch returns a constant
   ±π/2 for all near-polar inputs (denominator collapses to zero);
   untested, uncalled today, but a ticking time bomb for any
   crater/canyon scenario that pitches the rover past ~89.9°.
2. **H-tier** — silent non-unit-quat acceptance, unvalidated quat
   shape in twist/rotate helpers, NaN/Inf pass-through, float32
   forced casts that shed Isaac Sim precision, and parameter-agnostic
   error messages make the odometry pipeline hostile to debug.
3. **Docs/structure** — `marslab.math.__init__` exports nothing while
   claiming to be a "consolidated namespace"; convention citations
   ("ZYX intrinsic", "tf `sxyz` parity") are partly incorrect; "Oracle
   diff=0 policy" is unenforced and genuine source duplication still
   lives in `scripts/phase1/run_stage3_monolithic.py`.
