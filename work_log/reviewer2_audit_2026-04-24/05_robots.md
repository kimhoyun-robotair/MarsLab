# Reviewer 2 Audit — `marslab/robots/`

## 메타

- **Reviewer role:** Reviewer 2 — hostile external peer reviewer.
- **Date:** 2026-04-24
- **Scope:** `marslab/robots/` (4 files)
  - `/home/hoyunkim/MarsLab/marslab/robots/__init__.py`
  - `/home/hoyunkim/MarsLab/marslab/robots/drive_api_setup.py`
  - `/home/hoyunkim/MarsLab/marslab/robots/rover.py`
  - `/home/hoyunkim/MarsLab/marslab/robots/rover_control.py`
- **Explicit non-scope:** CLAUDE.md, PLAN.md, `.claude/`, `work_log/` (not read).
- **Method:** line-by-line read; cross-referenced external callers
  (`scripts/phase1/run_stage3_monolithic.py`, `scripts/phase1/run_stage4.py`,
  `tests/unit/test_ackermann.py`, `tests/unit/test_drive_api_setup.py`,
  `tests/unit/test_rover_control.py`, `tests/unit/test_rover_module.py`)
  only to validate assumptions.
- **Treat-with-suspicion items:** every docstring that cites an internal
  refactor identifier (`R3-A1`, `R4-3`, `R2-A3`, `§ 7.1-7.5`) —
  comments-as-deodorant smell.

---

## Findings

### CRITICAL

#### C1. Ackermann steer angle uses `arctan` instead of `arctan2` → 180° flip for tight turns

**File:** `marslab/robots/rover_control.py:93-98`

```python
for i, (x_w, y_w) in enumerate(steer_xy):
    dy = R - y_w
    if abs(dy) < _EPS_DY:
        # ICR exactly at wheel lateral position → 90° steer.
        steer_angles[i] = float(np.copysign(np.pi / 2.0, x_w))
    else:
        steer_angles[i] = float(np.arctan(x_w / dy))
```

**Problem.** The geometric steer angle of a wheel rolling around an ICR is
`atan2(x_w, R - y_w)` — it lives on the full `(-π, π]` circle.  The code
uses single-argument `arctan(x_w / dy)`, whose range is `(-π/2, π/2)`.

When the commanded turn radius `R = v/w` makes `dy = R - y_w < 0`
(e.g. tight left turn with `|R| < track_steer/2`, or any point-turn
where `R = 0` and the wheel sits on the positive-y side), the two
formulas differ by exactly π.  The author intends to paper over this by
letting the **velocity sign** flip — at L116 `sign(w*dy)` negates the
commanded wheel speed so the wheel "rolls backward" along a wrong-way
heading to produce the same tangent motion.  That only works if
downstream steer clamping / mechanical limits allow ±90° of travel.
`clamp_steer_angles` (L121-140) documents a typical limit of 40° and the
default in `run_stage3_monolithic.py` clamps via `np.clip(steer_angles,
-max_steer_angle, max_steer_angle)` (L1301).

**Consequence.** Any commanded tight turn (e.g. Nav2 recovery rotation
with `|R| < 1 m` on a rover whose `half_ts ≈ 1.06 m`) yields steer
angles in the wrong half-plane.  After clamping, the wheels point close
to the mechanical stop in the wrong direction while the drive side
reverses to compensate — producing tire scrub, ICR wander, and
non-zero lateral velocity at the commanded point-turn axis.
Tests (`tests/unit/test_ackermann.py`) **do not cover** this regime;
every curve test uses `R = 4 m ≫ half_ts`.

**Fix.** Use `np.arctan2(x_w, R - y_w)` for the geometric angle, then
allow the downstream layer to explicitly decide between
"turn wheel further" vs. "drive in reverse" via an explicit policy.
Add a regression test at `R ∈ {0.0, 0.5·half_ts, 1.0·half_ts}` that
compares the resulting wheel heading + rotation to the ICR tangent.

---

#### C2. Non-scope `velocity sign flip` + hard steer clamp produces silent kinematic divergence

**File:**
- `marslab/robots/rover_control.py:112-116` (Euclidean velocity with
  `sign(w * dy)`).
- `marslab/robots/rover_control.py:121-140` (`clamp_steer_angles`).

```python
wheel_velocities[i] = float(np.copysign(1.0, w * dy)) * abs(w) * dist / wheel_radius
```

**Problem.** The velocity formula only produces the correct tangent
motion when the steer angle is allowed to take the raw
`arctan2`-space value.  The moment any external clamp (40° mechanical
stop, per-step ramp, negate_steer flip in `run_stage3_monolithic.py:1297`)
modifies `steer_angles` after `ackermann_command` returns, the pair
`(steer_angles, wheel_velocities)` no longer satisfies the no-slip
constraint — the wheel is commanded to roll in a direction that does
not match its heading.  Physically: tire scrub, odometry drift,
SLAM/Nav2 instability.

Nothing in the module validates this invariant; the clamp simply
mutates one half of the pair.  The design implicitly assumes the caller
will never clamp, but in practice every caller clamps.

**Fix.** Make `ackermann_command` return the three invariants
(`steer`, `drive_vel`, `R_turn`) together, and provide a single
`clamp_ackermann_pair()` that re-derives both halves under a steer
limit (falling back to skid-steer kinematics when the clamp binds).
Or: document in the docstring that the pair must be consumed
atomically; tests must raise if a caller breaks the contract.

---

### HIGH

#### H1. `_apply_drive_api` return value ignored — silent failure when joint path missing

**File:** `marslab/robots/drive_api_setup.py:113-145`, helper at `46-80`.

```python
def _apply_drive_api(stage, joint_path, ...):
    joint_prim = stage.GetPrimAtPath(joint_path)
    if not joint_prim.IsValid():
        return False               # ← caller discards this
    ...
    return True

# Callers in configure_drives:
for jname in drive_joint_names:
    _apply_drive_api(stage, f"{joints_scope}/{jname}", ...)   # return ignored
for jname in steer_joint_names:
    _apply_drive_api(stage, f"{joints_scope}/{jname}", ...)   # return ignored
```

**Problem.** A typo in YAML joint names, a URDF rename, or a USD-import
merge that hides the joint behind another scope yields
`GetPrimAtPath → invalid prim`, the helper returns `False`, the caller
ignores it, and the rover runs with *missing* drive/steer/suspension
configuration.  No exception, no warning, no log line — the user sees
a rover that "just doesn't move" or "moves slowly" with zero diagnostic
context.  "No silent fallbacks" is textbook Reviewer-2 bait.

**Fix.** Either:
1. Raise `RuntimeError(f"Joint prim missing at {joint_path}")` from
   `_apply_drive_api`, or
2. Collect the failures in `configure_drives` and raise a single
   `RuntimeError` listing all missing joint paths before returning.

Silent-warn is not acceptable because the failure mode is
indistinguishable from bad physics gains.

---

#### H2. `configure_drives` / `reinforce_pd_gains` silently skip suspension when `suspension_damping == 0`

**File:** `marslab/robots/drive_api_setup.py:135`, `177`.

```python
if suspension_damping > 0.0:
    for jname in suspension_names:
        _apply_drive_api(...)       # only runs if damping > 0
```

**Problem.** If `suspension_damping` is `0.0` (or absent → `.get(...,
[])` means damping default `0.0` too), suspension joints receive
**no** DriveAPI at all.  PhysX will then use its USD defaults for the
joint — typically unlimited free-swing — which, on a rocker-bogie
rover, lets the middle links flop uncontrollably as the simulation
starts.  The YAML comment `"Damped passive joint: stiffness=0,
damping>0"` (L137) acknowledges this assumption but the code does not
enforce it.

Meanwhile `reinforce_pd_gains` (L177) has the **same** gate, meaning
the post-reset tensor-path gain reinforcement is also skipped.  A user
who sets `suspension_damping: 0.0` for a "locked" test ends up with a
fully free suspension instead.

**Fix.** Raise if `suspension_names` is non-empty while
`suspension_damping == 0.0`, or — better — require suspension tuning
to be opt-in with an explicit YAML flag (`suspension.enabled: false`),
and remove the silent branch.  Document the intended behaviour in the
docstring rather than hiding it behind a numeric comparison.

---

#### H3. `ramp_wheel_velocities` mis-classifies direction reversals as decel

**File:** `marslab/robots/rover_control.py:200-210`.

```python
delta = tgt - current
is_decel = np.abs(tgt) < np.abs(current)
step_lim = np.where(is_decel, per_step_limit * decel_multiplier, per_step_limit)
delta = np.clip(delta, -step_lim, step_lim)
return (current + delta).astype(current.dtype)
```

**Problem.** `is_decel` is true whenever the **magnitude** of the
target is smaller than the magnitude of the current velocity.
Counter-example: `current = +5 rad/s`, `target = -3 rad/s`.
`|-3| < |5|` → `is_decel = True` → the bigger `decel_multiplier` step
limit applies even though the wheel is being asked to **reverse
direction**.  The jerk the ramp is designed to mitigate is largest
precisely at zero-crossings, so using the brake-rate limit through
zero is exactly backwards.

Docstring (L176-197) says:
> Braking (target magnitude lower than current) is allowed to happen
> decel_multiplier times faster than acceleration.

Technically true to the letter, but the caller intuition ("decel =
slowing down in the same direction") is violated.

**Fix.** Change the condition to `is_decel = np.sign(tgt) ==
np.sign(current) and np.abs(tgt) < np.abs(current)`, vectorised with
`np.logical_and`.  Add a unit test: `current=[5]`, `target=[-5]`
should use the accel limit, not the decel limit.

---

#### H4. Hardcoded chassis link names break silently if URDF changes

**File:** `marslab/robots/rover.py:244, 250`.

```python
chassis_path = f"{prim_path}/Body_Chassis"
apply_mass_properties(
    stage,
    f"{chassis_path}/Body_Chassis",   # → /World/Rover/Body_Chassis/Body_Chassis
    ...
)
```

**Problem.** The code hardcodes the link name `Body_Chassis` *twice*
(nested) and assumes the URDF→USD conversion produced exactly that
layout with `merge_fixed_joints=False`.  The JPL m2020 URDF that
drives this project happens to use that name — but any change (rover
swap, URDF update, future `merge_fixed_joints=True` optimisation, or
using Isaac Lab's `UrdfConverter` with default settings) silently
breaks the path.  `apply_mass_properties` then warns to stderr (easy
to miss) and proceeds without mass/damping overrides; the rover runs
with wrong dynamics.  `configure_drives` later uses
`{chassis_path}/joints` (L111) which also silently yields no valid
prims and — per H1 — ignores the failure.

**Fix.** Either:
1. Make the chassis link name a config key
   (`rover.chassis_link_name: "Body_Chassis"`) and read it from YAML
   (consistent with G5: all configs in YAML), or
2. Traverse the stage for the first `ArticulationRootAPI` under
   `prim_path` and use that path, raising if not found.

---

#### H5. `apply_mass_properties` warns-and-continues when articulation root missing

**File:** `marslab/robots/rover.py:151-158`.

```python
art_root_prim = stage.GetPrimAtPath(art_root_path)
if not art_root_prim.IsValid():
    print(
        f"[marslab.robots.rover] WARNING: {art_root_path} not found; "
        "skipping mass override.",
        file=sys.stderr,
    )
    return
```

**Problem.** If the YAML explicitly sets `com_offset`, `angular_damping`,
or `linear_damping`, the user wants those applied.  Silently skipping
them on a missing prim path hides a configuration mismatch behind a
stderr print and produces a rover whose physics is subtly wrong.

**Fix.** `raise RuntimeError(f"Articulation root missing at
{art_root_path}; cannot apply mass overrides")`.  Never swallow a
user-intent override.

---

#### H6. `find_rigid_body_path` silent fallback attaches sensors to static prim

**File:** `marslab/robots/rover.py:181-206`.

```python
for child in chassis_prim.GetChildren():
    if child.HasAPI(UsdPhysics.RigidBodyAPI):
        return str(child.GetPath())

print(f"[marslab.robots.rover] WARNING: no RigidBodyAPI child under {chassis_path}; "
      "sensors will be static!", file=sys.stderr)
return chassis_path
```

**Problem.** The docstring explicitly says "sensors would then be
static in world space" — a catastrophic failure mode for every
downstream SLAM / Nav2 evaluation.  Yet the function returns
`chassis_path` and keeps running.  Downstream ROS2 IMU/LiDAR/odometry
publishers will emit data, but it'll be permanently zero velocity —
poisoning every benchmark without any hard error.

**Fix.** `raise RuntimeError(f"No RigidBodyAPI child found under
{chassis_path}; sensors cannot be attached to a static prim")`.
Warning-only handling of this failure is reviewer-2 ammo.

---

### MEDIUM

#### M1. `ackermann_command` recomputes half-dimensions before the w=0 early return

**File:** `marslab/robots/rover_control.py:68-77`.

```python
half_wb = wheelbase / 2.0
half_ts = track_steer / 2.0
half_tm = track_middle / 2.0

if abs(w) < _EPS_W:
    steer = np.zeros(4, dtype=np.float32)
    omega = float(v) / wheel_radius
    vel = np.full(6, omega, dtype=np.float32)
    return steer, vel
```

**Problem.** Negligible perf hit, but readability: the early-return
path reads zero geometry variables.  Move the halving below the
early-return, or hoist the early-return above.

**Fix.** Reorder — straight-line path first, then geometry setup for
curve branch.

---

#### M2. `_EPS_DY` single-arm guard only in steer loop, not in drive loop

**File:** `marslab/robots/rover_control.py:94` (steer) vs. `113-116` (drive).

```python
# Steer loop: guarded
if abs(dy) < _EPS_DY:
    steer_angles[i] = float(np.copysign(np.pi / 2.0, x_w))
else:
    steer_angles[i] = float(np.arctan(x_w / dy))

# Drive loop: no guard
for i, (x_w, y_w) in enumerate(drive_xy):
    dy = R - y_w
    dist = np.sqrt(x_w**2 + dy**2)
    wheel_velocities[i] = float(np.copysign(1.0, w * dy)) * abs(w) * dist / wheel_radius
```

**Problem.** If `R` lies exactly on a drive wheel's lateral line
(`dy == 0`), the sign term `copysign(1.0, w * dy)` becomes
`copysign(1.0, 0.0) = +1.0` regardless of `w`'s sign.  For a middle
wheel that lands on the ICR this assigns a direction arbitrarily.
`dist = |x_w|` is fine, but the sign discontinuity means an
infinitesimal parameter change flips the wheel direction.

**Fix.** Apply the same `_EPS_DY` guard in the drive loop: when
`|dy| < _EPS_DY`, the wheel is at the ICR so its linear velocity
vanishes (set `wheel_velocities[i] = 0.0`), with the exception of the
`x_w != 0` case where the wheel still has angular contribution from
spin — correct result is `|w| * |x_w| / wheel_radius` with sign chosen
by the rotation direction around ICR (`sign(w)` if the wheel is on
the positive x-axis side, etc.).

---

#### M3. Rover module's spawn-orientation fallback chain silently accepts null/empty

**File:** `marslab/robots/rover.py:237-241`.

```python
spawn_block = rover_cfg.get("spawn", {}) if isinstance(rover_cfg, dict) else {}
rpy = tuple(
    spawn_block.get("orientation_rpy")
    or rover_cfg.get("spawn_orientation_rpy", [0.0, 0.0, 0.0])
)
```

**Problem.** Three layers of ambiguity:
1. `spawn_block.get("orientation_rpy")` returns `None` if unset *or*
   `[]` if explicitly empty.
2. `... or rover_cfg.get("spawn_orientation_rpy", ...)` silently picks
   the legacy top-level key, which duplicates the schema.
3. Default `[0.0, 0.0, 0.0]` is accepted as truthy (non-empty list)
   — fine — but `[0, 0, 0]` from YAML integer literals would pass
   `tuple()` and hit `float()` in `apply_spawn_pose`.  Works only by
   accident.

Also: `isinstance(rover_cfg, dict)` — what else would it be?  If
pydantic validation already guarantees `dict`, the guard is dead; if
pydantic returns a model object, `dict.get` would have raised, so the
guard silently trims to `{}`.

**Fix.** Use a pydantic-validated `RoverConfig.spawn.orientation_rpy:
Tuple[float, float, float] = (0, 0, 0)` and read a single path.  Drop
the two-tier fallback.

---

#### M4. `configure_drives` has no `drive_type` validation

**File:** `marslab/robots/drive_api_setup.py:109`.

```python
drive_type = str(control_cfg["drive_type"])
```

**Problem.** USD `UsdPhysics.DriveAPI` only accepts `"force"` or
`"acceleration"`.  Typos (`"acceletation"`, `"velocity"`) get passed
through `str()` and fail silently inside PhysX (driveType defaults to
`force`, no error).

**Fix.** Validate:
```python
if drive_type not in {"force", "acceleration"}:
    raise ValueError(f"drive_type must be 'force' or 'acceleration', got {drive_type!r}")
```
or pull the enum through pydantic in `SkidSteerDriveConfig`.

---

#### M5. `_apply_drive_api` duplicates three USD `CreateAttribute` calls

**File:** `marslab/robots/drive_api_setup.py:69-77`.

```python
joint_prim.CreateAttribute("drive:angular:physics:stiffness",  Sdf.ValueTypeNames.Float).Set(float(stiffness))
joint_prim.CreateAttribute("drive:angular:physics:damping",    Sdf.ValueTypeNames.Float).Set(float(damping))
joint_prim.CreateAttribute("drive:angular:physics:maxForce",   Sdf.ValueTypeNames.Float).Set(float(max_force))
```

**Problem.** Fowler's "repeated switch" smell.  Additionally,
creating attributes via `CreateAttribute` on string literals instead of
using the `UsdPhysics.DriveAPI` typed getters (e.g.
`drive_api.CreateStiffnessAttr(...)`) bypasses USD's own schema
validation.  If the attribute already exists with a different type
(e.g. `Double`), `CreateAttribute` with `Float` silently creates a
second attribute.

**Fix.**
```python
for attr_name, value in (("stiffness", stiffness), ("damping", damping), ("maxForce", max_force)):
    drive_api.CreateStiffnessAttr if attr_name == "stiffness" else ...
```
Or use the typed API:
```python
drive_api.CreateStiffnessAttr(float(stiffness), writeSparsely=False)
drive_api.CreateDampingAttr(float(damping), writeSparsely=False)
drive_api.CreateMaxForceAttr(float(max_force), writeSparsely=False)
```

---

#### M6. Circular-import-broken-via-lazy-import architectural smell

**File:** `marslab/robots/drive_api_setup.py:33-43`; `rover.py:28-32`.

```python
# drive_api_setup.py
def _resolve_joint_indices(dof_names, requested):
    from marslab.robots.rover import resolve_joint_indices as _impl   # ← deferred
    return _impl(dof_names, requested)

# rover.py
from marslab.robots.drive_api_setup import (   # noqa: F401
    _apply_drive_api, configure_drives, reinforce_pd_gains,
)
```

**Problem.** `rover.py` imports names from `drive_api_setup.py`, and
`drive_api_setup.py` needs a symbol from `rover.py`.  The cycle is
masked with a function-scope import — works at runtime but is
fragile, slows every `reinforce_pd_gains` call (import lookup), and
confuses static analysers.

**Fix.** Move `resolve_joint_indices` into a neutral module (e.g.
`marslab/robots/_common.py` or `marslab/robots/joint_indices.py`)
from which **both** `rover.py` and `drive_api_setup.py` import
directly.  Eliminates the cycle.

---

#### M7. Public `__all__` exports a private-named symbol

**File:** `marslab/robots/rover.py:34-46`.

```python
__all__ = [
    ...
    "_apply_drive_api",
    ...
]
```

**Problem.** By Python convention, an identifier starting with `_` is
private / implementation detail.  Putting `"_apply_drive_api"` into
`__all__` is internally contradictory — it says "this is private but
also part of the public API".  Any lint rule (`N801`, `PLW0101`) will
flag it, and external callers reasonably expect it to disappear in the
next refactor.

**Fix.** Either drop the leading underscore on `_apply_drive_api` in
`drive_api_setup.py` and re-export the new name, or remove
`"_apply_drive_api"` from `rover.__all__`.

---

#### M8. Tests do not cover tight-turn / zero-crossing ackermann regimes

**File:** `tests/unit/test_ackermann.py:62-104` (curve tests).

**Problem.** The only curve test uses `v=2.0, w=0.5` (`R=4 m ≫
half_ts=1.06 m`), and the only point-turn test is `v=0, w=±1` (`R=0`).
No test covers the critical regime `R ∈ (0, half_ts)` — i.e. tight
turns where the ICR sits between the left-middle and left-steer track
lines.  This is exactly the regime where C1 would surface.

**Fix.** Add:
```python
@pytest.mark.parametrize("R_turn", [0.3, 0.7, 1.0, 1.2])
def test_tight_turn_no_slip(self, R_turn):
    v = 0.5; w = v / R_turn
    steer, vel = ackermann_command(v, w, WB, TS, TM, R)
    # Verify wheel velocity vector = perpendicular to ICR radius
    for i, (x_w, y_w) in enumerate([...]):
        heading = steer[i]  # or 0 for non-steer
        cart_vel = vel[i] * R * np.array([np.cos(heading), np.sin(heading)])
        radius = np.array([x_w, y_w - R_turn])
        # No-slip constraint: cart_vel ⊥ radius
        assert abs(np.dot(cart_vel, radius)) < 1e-3
```

---

### LOW

#### L1. Docstring `copysign(pi/2, x_w)` footgun for `x_w == 0`

**File:** `marslab/robots/rover_control.py:96`.

```python
steer_angles[i] = float(np.copysign(np.pi / 2.0, x_w))
```

**Problem.** Works for the current `steer_xy` list where `x_w = ±half_wb`.
If a future change adds middle wheels to the steer list (mission-5
crab-walk, for instance), `copysign(π/2, 0.0)` returns `+π/2`
regardless of turn direction — a latent discontinuity.  Defensive:
use `np.sign(x_w) or 0.0` + explicit zero branch.

---

#### L2. `GetTypeAttr() or CreateTypeAttr()` relies on USD attribute truthiness

**File:** `marslab/robots/drive_api_setup.py:78`.

```python
type_attr = drive_api.GetTypeAttr() or drive_api.CreateTypeAttr()
```

**Problem.** `UsdAttribute.__bool__` returns True if the attribute is
*defined*.  Works today, but the semantics are USD-version-dependent;
future pxr versions could change when an attribute is considered
defined vs. valid.  Prefer the explicit
`attr = drive_api.GetTypeAttr(); if not attr.IsValid(): attr =
drive_api.CreateTypeAttr()` pattern.

---

#### L3. `print(..., file=sys.stderr)` instead of `logging`

**File:** `marslab/robots/rover.py:152-158, 201-205`.

```python
print(f"[marslab.robots.rover] WARNING: {art_root_path} not found; ...",
      file=sys.stderr)
```

**Problem.** Manual stderr prints bypass any log-level routing; users
can't silence them, correlate them with timestamps, or redirect them
to per-run logs.  `import logging; logger.warning(...)` costs the
same.

**Fix.** Use `logging.getLogger(__name__).warning(...)`.  Better yet,
per H5/H6 make these failures raise, not warn.

---

#### L4. `ramp_steer_angles` / `ramp_wheel_velocities` silently coerce dtype

**File:** `marslab/robots/rover_control.py:164, 200`.

```python
if per_step_limit <= 0.0:
    return target.astype(current.dtype, copy=True)
```

**Problem.** Docstring says "returns `target` unchanged".  If `target`
is `float32` and `current` is `float64`, the caller gets a `float64`
copy with values re-cast.  Subtle dtype promotion.

**Fix.** Either document explicitly ("returns a fresh copy in
`current`'s dtype") or drop the cast and return `target.copy()`.

---

#### L5. Imported-but-only-for-noqa: `rpy_to_quat` re-export with `# noqa: F401`

**File:** `marslab/robots/rover.py:22`.

```python
from marslab.math.quaternion import rpy_to_quat  # noqa: F401
```

**Problem.** The `noqa` disables the "unused import" warning because
the symbol *is* used (at L128).  But re-exporting it for
backwards-compat (to keep
`from marslab.robots.rover import rpy_to_quat` working) plus using
it in the same file means `noqa` is misleading — the import *is*
used, it just happens to also be re-exported.  A reader sees `noqa:
F401` and assumes the symbol is only re-exported.

**Fix.** Drop the `noqa`; ruff won't flag it since it's used at L128.
Add it to `__all__` to document the re-export intent (it already is
on L35 — good — so just drop the noqa).

---

#### L6. `rpy_to_quat` re-export comment is deodorant

**File:** `marslab/robots/rover.py:18-22, 24-33`.

```python
# R3-A1: ``rpy_to_quat`` was relocated to ``marslab.math.quaternion`` as
# the single source of truth.  Re-exported here so every existing import
# site — ``from marslab.robots.rover import rpy_to_quat`` — keeps working
# without modification (tests/unit/test_rover_module.py, sensors/rover_rig.py).
from marslab.math.quaternion import rpy_to_quat  # noqa: F401

# R4-3 (2026-04-22): DriveAPI + PD-gain helpers relocated to
# ``marslab.robots.drive_api_setup``.  Re-exported here so existing
# imports (``from marslab.robots.rover import configure_drives``,
# ``reinforce_pd_gains``) keep working.  Original inline bodies are
from marslab.robots.drive_api_setup import (  # noqa: F401
    _apply_drive_api, configure_drives, reinforce_pd_gains,
)
```

**Problem.** Comments narrate internal refactor stages ("R3-A1",
"R4-3", dates).  External readers don't care; comments become lies as
soon as the next refactor ships.  Also the second comment is
**truncated** mid-sentence: "Original inline bodies are" ← no verb.

**Fix.** Delete the comments.  A module-level docstring can note the
backwards-compat re-exports in one line if needed.  Remove the
dangling fragment at line 27.

---

#### L7. Module docstring at `drive_api_setup.py` is pure refactor history

**File:** `marslab/robots/drive_api_setup.py:1-24`.

**Problem.** 24 lines of module-level prose telling the reader when
the file was extracted, from where, what other file still lives,
what "R4-3" means.  None of this is useful to an outsider.  The
tensor-cache ordering contract is the only content that belongs in
source code, and that content is duplicated inside each function's
docstring (L57-60, L93-95, L156-162) — DRY violation.

**Fix.** Replace with a 2-3 line module docstring that summarises
the public API (`configure_drives`, `reinforce_pd_gains`) and points
to a single "Tensor-cache ordering" section in one of the two
function docstrings (or a top-level design doc outside source).

---

#### L8. Float division documentation drift in `ackermann_command`

**File:** `marslab/robots/rover_control.py:81`.

```python
R = float(v) / float(w)
```

**Problem.** `float(v) / float(w)` is a no-op when `v` and `w` are
already floats (the public signature types them as `float`).  Useless
widening.  If the intent was to defend against numpy scalars, say so.

**Fix.** Just `R = v / w`.  The guard at L73 already rules out
`w == 0`.

---

### DELETE

#### D1. Module docstring history headers (`drive_api_setup.py:1-24`)

Per L7 above — delete refactor-history prose, keep only
tensor-cache ordering statement.

#### D2. `# R3-A1`, `# R4-3` inline comments in `rover.py`

Per L6 above — `rover.py:18-27` both historical comments.  Delete.

#### D3. Truncated sentence `rover.py:27`

```python
# imports (``from marslab.robots.rover import configure_drives``,
# ``reinforce_pd_gains``) keep working.  Original inline bodies are
from marslab.robots.drive_api_setup import (  # noqa: F401
```

The comment ends mid-sentence ("Original inline bodies are"). Either
finish it or delete it; don't commit half-written prose.

#### D4. `_apply_drive_api` from `rover.__all__`

Per M7 — remove the private-named symbol from the public surface,
OR rename it.  One or the other.

#### D5. Duplicated docstring ordering notes across three functions

`drive_api_setup.py:57-60`, `93-95`, `156-162` all restate the
tensor-cache ordering contract.  Keep it once (module docstring),
drop the copies.

---

### WATCHLIST

#### W1. `spawn_rover` takes a `spawn_xyz` triple separately from `rover_cfg`

**File:** `marslab/robots/rover.py:209-214`.

```python
def spawn_rover(
    stage: Any,
    rover_cfg: Dict[str, Any],
    usd_abs: str,
    spawn_xyz: Tuple[float, float, float],
) -> SpawnedRover:
```

Why is `spawn_xyz` a separate argument when `rover_cfg["spawn"]`
already exists and `orientation_rpy` is read from
`rover_cfg["spawn"]["orientation_rpy"]`?  Two sources of truth for
pose means one can diverge from the other without warning.

Watch: consolidate into `rover_cfg["spawn"]["xyz"]` + make
`spawn_rover` a pure `rover_cfg` consumer.

---

#### W2. `rover_cfg: Dict[str, Any]` everywhere — no schema enforcement

**File:** `marslab/robots/rover.py:210, 234`; `drive_api_setup.py:86, 150`.

Both public entry points accept a raw dict.  Comments claim
`SkidSteerDriveConfig` validates at load time (L100-101, L167-168)
but neither function *verifies* — `control_cfg["drive_joint_names"]`
throws plain `KeyError` if absent, not a helpful pydantic message.

Watch: switch signature to accept the validated pydantic model
(`control_cfg: SkidSteerDriveConfig`, `rover_cfg: RoverConfig`) so
missing keys fail at a single typed layer.

---

#### W3. Hardcoded `"/joints"` scope under chassis

**File:** `marslab/robots/drive_api_setup.py:111`.

```python
joints_scope = f"{chassis_path}/joints"
```

USD joint path layout after URDF import depends on converter flags.
If `UrdfConverter` uses a different joints-scope name (e.g.
`"Joints"`, `"articulation/joints"`, inline), every joint path becomes
invalid — silent per H1.

Watch: resolve the joints scope by traversing `UsdPhysics.Joint`
prims under `chassis_path` instead of assuming the literal scope
name.

---

#### W4. `SpawnedRover.rigid_body_path` silently aliases to `chassis_path`

**File:** `marslab/robots/rover.py:256-261`.

```python
rigid_body_path = find_rigid_body_path(stage, chassis_path)
return SpawnedRover(
    prim_path=prim_path,
    chassis_path=chassis_path,
    rigid_body_path=rigid_body_path,
)
```

Per H6, `find_rigid_body_path` can return `chassis_path` on the
failure branch.  Downstream consumers of
`SpawnedRover.rigid_body_path` have no way to tell "found a
rigid-body child" from "failed, aliased to chassis".  Watch for
downstream bugs when ROS2 sensors attach to a static prim.

---

#### W5. `reinforce_pd_gains` allocates `(1, num_dof)` gain tensors every call

**File:** `marslab/robots/drive_api_setup.py:180-191`.

The docstring claims this runs **once** post-reset.  If the caller
actually calls it per simulation step (by mistake), each invocation
allocates a fresh `np.zeros((1, num_dof), dtype=float32)` and uploads
it to PhysX.  No public guard prevents this.

Watch: add a module-level `_GAINS_APPLIED` flag or assertion that
the function is called at most once per articulation lifecycle.

---

## Final Summary (3 lines)

- **Counts:** 2 CRITICAL, 6 HIGH, 8 MEDIUM, 8 LOW, 5 DELETE, 5 WATCHLIST.
- **Top risks:** Ackermann math (`arctan` vs `arctan2` → 180° flip at
  tight turns; see C1/C2/M8) and silent configuration failures across
  DriveAPI / chassis / rigid-body discovery (H1/H4/H5/H6) —
  together these are classic "rover silently mis-behaves in ways that
  poison every SLAM/Nav2 benchmark".
- **Recommended first patch:** add `arctan2`-based test, fix C1/C2,
  convert every `print(..., file=sys.stderr) + return` to
  `raise RuntimeError`, and introduce `marslab/robots/_common.py` for
  `resolve_joint_indices` to break the circular import (M6).
