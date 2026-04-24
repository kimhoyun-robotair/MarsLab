# Reviewer 2 Audit — `marslab/sensors/`

Scope: 5 files (`__init__.py`, `camera.py`, `imu.py`, `lidar.py`, `sensor_spawner.py`).
Reviewer stance: hostile external peer reviewer. Internal-term citations (P1/P3/G5/R4-2/§7.17/§10.8) are treated as deodorant over smells, not as justification.

---

## 1. Two parallel sensor-spawn pipelines that do not know about each other (architectural smell)

**Files:** `camera.py`, `imu.py`, `lidar.py` vs `sensor_spawner.py`

**Problem.** There are **two completely disjoint sensor-attach paths** in this package:

- Path A (`camera.py::attach_camera`, `imu.py::attach_imu`, `lidar.py::attach_lidar`) dispatched through `__init__.py::load_and_attach_sensor` via `_SENSOR_DISPATCH`. Reads YAML with keys `name / mount_link / offset_position / offset_orientation / update_rate / clipping_range / focal_length / horizontal_fov / ...`. Uses `omni.kit.commands.execute("IsaacSensorCreateImuSensor"...)` and `"RangeSensorCreateLidar"`. Prim paths are `{robot_prim_path}/{mount_link}/{name}`.
- Path B (`sensor_spawner.py::spawn_sensors`) used by `scripts/phase1/run_stage3_monolithic_new.py`. Reads a *different* YAML shape with keys `local_translation / local_orientation_rpy_deg / profile / resolution / focal_length / clipping_range`. Uses `isaacsim.sensors.camera.Camera`, `isaacsim.sensors.physics.IMUSensor`, `isaacsim.sensors.rtx.LidarRtx` classes directly (not omni.kit commands). Prim paths are hard-coded `{rigid_body_path}/stage1_camera | stage1_lidar | stage1_lidar_2d | stage1_imu` — *mount_link is completely ignored*.

`__init__.py` exports both (`attach_camera`, `spawn_sensors`) as if they were peers. They are not: they use different Isaac-Sim APIs, different prim-path conventions, different config schemas, and different error semantics. New contributors will attach a sensor in one pipeline and watch it silently fail to appear in the other.

**Fix.** Pick one. Delete the other. `attach_imu` / `attach_lidar` use the old omni.kit command path (`IsaacSensorCreateImuSensor`, `RangeSensorCreateLidar`) which is the legacy range_sensor extension — the stage-3 runtime has already moved to `IMUSensor` / `LidarRtx`. Retire Path A to `delete_later/` and keep `spawn_sensors` as the single surface. If Path A survives because some script still imports `load_and_attach_sensor`, then grep the callers and either migrate them or document that `__init__.py` exposes a strict subset.

---

## 2. IMU "critical test" is never actually tested — docstrings lying about behavior

**File:** `marslab/sensors/imu.py:1-6, 13-16, 62-81`

**Quotes:**
```
"""IMU sensor attachment for Isaac Sim.

Attaches an IMU sensor to robots. At rest on Mars, z-axis must
read 3.72 +/- 0.05 m/s^2 (THE critical test). All parameters
from YAML config (G5). ..."""
```
and later
```
"""...
The IMU automatically reads from the physics scene gravity
(set to Mars 3.72 m/s^2). ..."""
```
and `read_imu` returns a `dict` with `"z should be ~3.72 at rest"` in the docstring.

**Problem.** The file *claims* gravity z ≈ 3.72 m/s² is "THE critical test" and that the IMU "automatically reads from the physics scene gravity (set to Mars 3.72 m/s^2)". Neither claim is enforced by the code:

1. `attach_imu` does **zero verification** that the physics scene gravity is actually 3.72. It does not query `UsdPhysics.Scene.GetGravityMagnitudeAttr()`, it does not warn, it does not fail fast. A caller that forgets to set gravity will get an IMU that happily reports 9.81 and the module will not notice.
2. `read_imu` returns a dict but performs no range-check, no logging, no assertion that z is in [3.67, 3.77]. Given the docstring's own emphasis ("THE critical test"), not even an `logger.warning` when z is out of band is indefensible.
3. The "automatically reads from the physics scene gravity (set to Mars 3.72 m/s^2)" claim is a lie of omission — the IMU reads whatever gravity the scene has. Whether that's 3.72 is the caller's problem, not guaranteed here.

**Fix.**
- Add `_assert_mars_gravity(stage)` invoked from `attach_imu` that reads `UsdPhysics.Scene` gravity and raises `ValueError` with parameter name, actual value, and expected range [3.67, 3.77] if it is out of band.
- In `read_imu`, add a debug-level `logger.warning` when `abs(reading.lin_acc_z - 3.72) > 0.05` while the other axes are near zero. Or — better — extract a `verify_gravity_at_rest(reading) -> bool` helper that's actually unit-testable offline (the point of P3) against fake readings.
- Either make the docstring claims true or delete them. Right now they are deodorant.

---

## 3. `offset_orientation` is documented but never applied — silent spec drift

**Files:** `imu.py:21-22`, `lidar.py:15-28`

**Quotes:**
```python
# imu.py L20-23
"""...
    config: Sensor config dict with keys: name, mount_link,
        offset_position, offset_orientation, update_rate.
"""
```
and `configs/sensors/imu.yaml` L10 supplies `offset_orientation: [0.0, 0.0, 0.0]`.
`configs/sensors/lidar_3d.yaml` L9 supplies `offset_orientation: [0.0, 0.0, 0.0]`.

**Problem.** The IMU and LiDAR docstrings / YAMLs advertise an `offset_orientation` (RPY degrees) parameter. The implementations never read that key:

- `imu.py:43-50` hard-codes orientation to `Gf.Quatd(1.0, 0.0, 0.0, 0.0)` (identity) in the `IsaacSensorCreateImuSensor` call. `offset_orientation` from YAML is silently discarded.
- `lidar.py` does not touch orientation at all; only `AddTranslateOp` is used (L93-94, L104-105) and even that only if there are no existing xform ops.

This is not a niche edge case. If a scientist mounts an IMU 90° rotated on a rocker-bogie arm, MarsLab will happily report bogus axes and the YAML key that *looks* like it should fix it does nothing. This is worse than omitting the key — the key's presence is a promise.

**Fix.**
- Either read `config.get("offset_orientation", [0, 0, 0])`, convert RPY → quaternion via `marslab.math.quaternion.rpy_to_quat`, and pass it into the Isaac command (IMU) or create an OrientOp (LiDAR); or
- Drop the `offset_orientation` key from the documented config schema and from the YAML files, and state in the docstring that "only translational offset is supported".

Pick one. Do not keep the YAML key whose only effect is to convince reviewers it works.

---

## 4. Camera has a `fallback` that re-parents the prim to the robot root when mount_link is missing — silent config bug masking

**File:** `marslab/sensors/camera.py:36-41`

**Quote:**
```python
name, mount_link = config["name"], config["mount_link"]
prim_path = f"{robot_prim_path}/{mount_link}/{name}"

# Fallback if mount_link doesn't exist
if not stage.GetPrimAtPath(f"{robot_prim_path}/{mount_link}").IsValid():
    prim_path = f"{robot_prim_path}/{name}"
```

**Problem.** If the YAML says `mount_link: "camera_arm_link"` but the URDF does not expose that link, the code *silently* re-parents the camera to the robot root. No warning, no log, no error. The camera will appear at the wrong place and the experiment will yield bogus data. This is the exact anti-pattern CLAUDE.md-style projects claim to forbid (`"Never silently swallow exceptions"`). Same pattern is repeated in `imu.py:36-40` and `lidar.py:45-49`.

**Fix.** Either:
- Raise `ValueError(f"mount_link '{mount_link}' not found under {robot_prim_path}")` and let the caller fix the YAML; or
- At minimum `logger.warning(...)` before falling back, and plumb the *actual* chosen parent path back to the caller so downstream code doesn't assume the advertised link.

A silent fallback here is a debugging trap waiting to eat a week.

---

## 5. Camera pipeline: `focal_length / 10.0` magic divisor with no comment

**File:** `marslab/sensors/sensor_spawner.py:162`

**Quote:**
```python
camera.set_focal_length(float(camera_cfg["focal_length"]) / 10.0)
```

**Problem.** Dividing the YAML-supplied `focal_length` by 10 is a unit-conversion smell with zero documentation. Isaac Sim's `Camera.set_focal_length` takes millimeters (per NVIDIA docs) and so does `configs/sensors/depth_camera.yaml` (commented `# mm (35mm film standard)` on `horizontal_aperture`, focal_length = 2.12). So why /10? Two hypotheses:

1. Someone saw `configs/phase1.yaml:87 focal_length: 24.0` and `configs/robots/rover_m2020.yaml:76 focal_length: 24.0` and got 24mm; but the Camera API actually reports something 10× larger (a known Isaac Sim USD-cm vs mm gotcha when reading back via `GetFocalLengthAttr`). The /10 is patching that mismatch.
2. The YAML is in "tenths of mm" for historical reasons.

Either way the code must say which. As-is, this is a load-bearing magic number with zero comment. A reviewer reading this cannot tell if `focal_length: 2.12` in `depth_camera.yaml` (Path A) is consistent with `focal_length: 24.0` in `phase1.yaml` (Path B). Both configs live in the same `configs/sensors/` tree and use the same name for what are *clearly different units*.

**Fix.** Either inline-comment (`# Kit Camera.set_focal_length reads USD focalLength in tenths of mm; divide to convert`) with a reference to NVIDIA docs, or — preferably — make the YAML key explicit (`focal_length_mm`) and drop the divisor. Also reconcile `depth_camera.yaml` (2.12) and `phase1.yaml` (24.0) — one of them is wrong by a factor of 10 or they describe different cameras, and right now the code silently accepts both.

---

## 6. Hardcoded sensor defaults in `.get()` calls — direct G5 violation

**File:** `marslab/sensors/camera.py:43-50`, `marslab/sensors/lidar.py:36-43`, `marslab/sensors/imu.py:33-34`

**Quotes:**
```python
# camera.py
clip_range = config.get("clipping_range", [0.1, 100.0])
...
resolution=tuple(config.get("resolution", [1280, 720])),
translation=np.array(config.get("offset_position", [0.0, 0.0, 0.0]), dtype=np.float64),
frequency=config.get("update_rate", 30),
```
```python
# lidar.py L36-43
offset_pos = config.get("offset_position", [0.0, 0.0, 0.0])
rotation_rate = config.get("rotation_rate", 10.0)
h_fov = config.get("horizontal_fov", [0.0, 360.0])
v_fov = config.get("vertical_fov", [-15.0, 15.0])
h_res = config.get("horizontal_resolution", 0.4)
v_res = config.get("vertical_resolution", 2.0)
max_range = config.get("max_range", 100.0)
min_range = config.get("min_range", 0.4)
```
```python
# imu.py
update_rate = config.get("update_rate", 200)
```

**Problem.** The module docstrings promise "All parameters from YAML config (G5)" (camera.py L4, imu.py L5, lidar.py L4). The implementations then encode concrete numeric defaults for resolution, FOV, rotation rate, clipping range, and IMU rate **inside the Python source**. This is a textbook hardcoded-constants violation and directly contradicts the advertised guideline. The problem is not hypothetical: if the YAML author forgets `max_range`, the LiDAR silently becomes a 100 m Velodyne HDL-64-ish device with 0.4°×2.0° resolution, none of which appears in any config file. You cannot reproduce an experiment whose parameters exist nowhere on disk.

**Fix.** Replace each `.get(key, default)` with a pydantic/dataclass schema (`marslab/config/schema/sensor.py`) where the default lives in a schema file, or with `config[key]` (KeyError is the right outcome for a missing required param). The former is better; either is better than today.

---

## 7. `lidar.py` builds a `lidar_params` dict that is used only for logging

**File:** `marslab/sensors/lidar.py:52-77`

**Quote:**
```python
lidar_params = {
    "min_range": min_range,
    "max_range": max_range,
    "horizontal_fov": h_fov[1] - h_fov[0],
    "vertical_fov": v_fov[1] - v_fov[0],
    "horizontal_resolution": h_res,
    "vertical_resolution": v_res,
    "rotation_rate": rotation_rate,
}
try:
    omni.kit.commands.execute(
        "RangeSensorCreateLidar",
        path=sensor_path,
        parent=None,
        min_range=min_range,
        max_range=max_range,
        ...
        rotation_rate=rotation_rate,
        high_lod=True,
        yaw_offset=0.0,
    )
```

**Problem.** `lidar_params` duplicates every named kwarg that's passed positionally to `omni.kit.commands.execute`. It is only read inside the `except` block's `logger.error` and `RuntimeError` message. This is Fowler-smell *Duplicate Code* and *Data Clump*: two parallel lists of the same values, guaranteed to drift whenever someone adds `draw_points=True` or `yaw_offset=90.0` without updating the dict. The `high_lod` / `yaw_offset` / `draw_points` / `draw_lines` kwargs in the actual call are *already* missing from `lidar_params`, so the error log is *incomplete* the moment it's needed.

**Fix.** Build `lidar_params` once with *all* parameters, then splat it: `omni.kit.commands.execute("RangeSensorCreateLidar", path=sensor_path, parent=None, **lidar_params, high_lod=True, yaw_offset=0.0, draw_points=False, draw_lines=False)`. Or better, merge everything into one dict. One source of truth.

---

## 8. LiDAR: `except Exception as exc:` with half-placeholder, half-raise is contradictory

**File:** `marslab/sensors/lidar.py:78-97`

**Quote:**
```python
except Exception as exc:
    logger.error(...)
    # Still create the Xform placeholder so downstream USD queries do not
    # crash when exception handlers above this frame intentionally continue,
    # but re-raise afterward so the default behavior is a hard failure.
    prim = stage.DefinePrim(Sdf.Path(sensor_path), "Xform")
    xform = UsdGeom.Xformable(prim)
    xform.AddTranslateOp().Set(Gf.Vec3d(*offset_pos))
    raise RuntimeError(
        f"Failed to create RTX LiDAR at {sensor_path} ..."
    ) from exc
```

**Problem.** The comment admits the fix is simultaneously "hard fail" and "create a placeholder in case someone upstream swallows the exception". That is cargo cult. If the caller swallows the RuntimeError, the Xform placeholder will make downstream `GetPrimAtPath(sensor_path).IsValid()` return True — which is worse than a missing prim: the rest of the pipeline will try to read a point cloud from a plain Xform and fail in weirder ways. Either fail hard (then the placeholder is dead) or soft-fallback (then you shouldn't re-raise). Mixing both is indefensible.

Also: `except Exception as exc` is far too wide for a physics API call. `omni.kit.commands.execute` may return a `(bool, obj)` tuple on failure rather than raising — that path isn't caught at all here.

**Fix.** Delete the Xform placeholder lines (92-94). Narrow the catch to `RuntimeError` / the specific kit exception. If `execute` returns `(False, None)` without raising, check the return value explicitly and raise.

---

## 9. LiDAR: `except (ImportError, Exception)` is tautological

**File:** `marslab/sensors/lidar.py:126, 140`

**Quote:**
```python
except (ImportError, Exception) as exc:
```

**Problem.** `Exception` is a superclass of `ImportError`. `except (ImportError, Exception)` is identical to `except Exception`. This is a cosmetic smell that signals the author confused "check for missing optional dep" with "catch everything". Worse: it catches `KeyboardInterrupt`? No — `KeyboardInterrupt` inherits `BaseException`. But it *does* catch `SystemExit`… actually no, same. OK so the set is correct; but the parenthesized listing is dead syntax that will fool future grep-ers into thinking the code treats `ImportError` differently.

Same pattern appears twice (L126, L140), so this is a *copy-paste* on top of a redundancy. If the author intended "try the new API; if unavailable fall through to the legacy API", then `ImportError` alone is the right catch for the import, and a separate narrower `except` (RuntimeError, AttributeError) should wrap the method call.

**Fix.**
```python
try:
    from isaacsim.sensors.rtx import LidarRtx
except ImportError:
    pc = None
else:
    try:
        pc = LidarRtx(lidar_prim_path).get_point_cloud()
    except (RuntimeError, AttributeError) as exc:
        logger.warning(...)
        pc = None
```

---

## 10. `read_lidar_point_cloud` instantiates `LidarRtx(prim_path)` every call — state-leaking loop

**File:** `marslab/sensors/lidar.py:110-132`

**Quote:**
```python
def read_lidar_point_cloud(lidar_prim_path: str) -> np.ndarray:
    ...
    lidar = LidarRtx(lidar_prim_path)
    pc = lidar.get_point_cloud()
```

**Problem.** If this function is called in the runtime loop (by name it will be — "read current LiDAR point cloud"), it creates a fresh `LidarRtx` handle for the same prim every tick. Isaac's wrapper classes typically allocate internal buffers and may re-`initialize()` the sensor. This is O(N_frames) extra allocations and risks double-initialization. Contrast with `sensor_spawner.py::spawn_sensors` which correctly creates `LidarRtx` once and returns the handle in `SensorHandles`.

**Fix.** Signature should accept the `LidarRtx` handle from `SensorHandles`, not a prim path: `def read_lidar_point_cloud(lidar: LidarRtx) -> np.ndarray`. The prim-path variant may stay as a fallback but must cache per-path via `functools.lru_cache(maxsize=8)` or a module-level dict.

---

## 11. Path A vs Path B prim-path conventions are inconsistent — frame_id will drift

**Files:** `camera.py:37` vs `sensor_spawner.py:149-200`

**Quotes:**
```python
# Path A: camera.py
prim_path = f"{robot_prim_path}/{mount_link}/{name}"
```
```python
# Path B: sensor_spawner.py
camera_prim_path = f"{rigid_body_path}/stage1_camera"
lidar_prim_path  = f"{rigid_body_path}/stage1_lidar"
imu_prim_path    = f"{rigid_body_path}/stage1_imu"
```

**Problem.** Path A nests under `mount_link` (e.g. `/World/Rover/base_link/imu_sensor`), Path B hard-codes `stage1_*` directly under the rigid body (e.g. `/World/Rover/base_link/stage1_imu`). The `stage1_` prefix is a historical artifact referenced in docstring `scripts/phase1/run_stage3_monolithic_new.py §7.17` — a comment that is *circular*: it points at a script that was itself refactored from this code. This naming leaks the transition history into the runtime prim namespace. TF and ROS2 frame_id conventions (CLAUDE.md-style projects specify `/{robot_name}/{sensor_type}`) will collide: both Path A and Path B cameras can coexist under the same robot and you will get `/World/Rover/base_link/rgb_camera` and `/World/Rover/base_link/stage1_camera` for the "same" sensor in different scripts. SLAM breaks.

The `sensor_spawner.py` docstring at L37-46 claims `SensorHandles` exposes prim paths needed "later by the OmniGraph sensor_graph orchestrator" — if that orchestrator hardcodes `stage1_*`, any migration to Path A breaks it; if it parameterises, Path B's `stage1_` prefix is already dead weight.

**Fix.** Rename `stage1_camera / stage1_lidar / stage1_lidar_2d / stage1_imu` to semantic names (`camera / lidar_3d / lidar_2d / imu`) — the `stage1_` prefix is meaningless in a multi-stage pipeline; if stage2 spawns more sensors, use a separate mount parent. Better: pass the sensor subprim name via config, matching Path A's convention.

---

## 12. `sensor_spawner.py` imports `rpy_to_quat` from `marslab.robots.rover` — wrong layer

**File:** `marslab/sensors/sensor_spawner.py:114`

**Quote:**
```python
from marslab.robots.rover import rpy_to_quat
```
with justifying comment:
```
# ``rpy_to_quat`` is imported from ``marslab.robots.rover`` on purpose — it is
# a re-export of ``marslab.math.quaternion.rpy_to_quat`` that keeps the existing
# import surface (see marslab/robots/rover.py L39).
```

**Problem.** `sensors/` should not depend on `robots/`. By the module-dependency rules at the top of the tree, `robots/` and `sensors/` are peers. A peer-to-peer `from marslab.robots.rover import rpy_to_quat` is the exact circular-import footgun the rules claim to forbid. Furthermore the comment admits this is literally a re-export — so import the canonical location:
```python
from marslab.math.quaternion import rpy_to_quat
```
The "keeps the existing import surface" argument is non-existent for a brand-new file that has no import surface to preserve.

**Fix.** Change the import to `from marslab.math.quaternion import rpy_to_quat`. Delete the 4-line justification comment. One less coupling edge.

---

## 13. Silent `print(...)` diagnostics instead of `logger`

**File:** `marslab/sensors/sensor_spawner.py:143-147, 189-193`

**Quote:**
```python
print(
    f"[run_stage3_mono] Camera parent Xform: {camera_xform_path} "
    f"rpy_deg={cam_orient_deg}",
    flush=True,
)
...
print(
    f"[run_stage3_mono] 2D LiDAR attached at {lidar_2d_prim_path} "
    f"profile='{lidar_2d_cfg['profile']}'",
    flush=True,
)
```

**Problem.** The prefix `[run_stage3_mono]` is wrong — the code no longer lives in `run_stage3_monolithic_new.py`; it lives in `sensor_spawner.py`. A user who greps logs for sensor issues by module name will miss both lines. `lidar.py` uses `logger = logging.getLogger(__name__)` correctly; `sensor_spawner.py` does not set up a logger and uses `print` with a *lying* prefix.

**Fix.** Replace with `logger = logging.getLogger(__name__)` at module top, and use `logger.info(...)`. Drop the bracket prefix — `__name__` already tells you `marslab.sensors.sensor_spawner`.

---

## 14. `attach_camera` mixes constructor-translation and USD-attribute-set clipping — inconsistent

**File:** `marslab/sensors/camera.py:45-57`

**Quote:**
```python
camera = Camera(
    prim_path=prim_path,
    resolution=tuple(config.get("resolution", [1280, 720])),
    translation=np.array(config.get("offset_position", [0.0, 0.0, 0.0]), dtype=np.float64),
    frequency=config.get("update_rate", 30),
)
camera.initialize()

# Set clipping range via USD
cam_prim = stage.GetPrimAtPath(prim_path)
if cam_prim.IsValid():
    cam_geom = UsdGeom.Camera(cam_prim)
    cam_geom.CreateClippingRangeAttr().Set(Gf.Vec2f(float(clip_range[0]), float(clip_range[1])))
```

**Problem.** Translation goes through the Camera wrapper's constructor, but clipping range bypasses the wrapper and writes directly to USD via `UsdGeom.Camera.CreateClippingRangeAttr()`. Both APIs exist on Camera (`camera.set_clipping_range(near, far)` — see how `sensor_spawner.py:163` uses it). Using two APIs for parameters of the same prim is a smell. Worse: `sensor_spawner.py` explicitly comments that "ANY xformOp modification on the Camera prim itself corrupts the RTX depth pipeline (vertical striping)" (L120-121). If true, then `Camera(..., translation=...)` in `camera.py` may be writing an xformOp to the Camera prim *and* producing vertical striping. Whoever wrote `sensor_spawner.py` knew this. Whoever wrote `camera.py` apparently did not.

**Fix.** Verify the striping claim. If correct, `attach_camera` must follow the parent-Xform pattern from `spawn_sensors`. If wrong, the fear-mongering comment in `spawn_sensors` is dead. Either way these two files cannot both be correct.

---

## 15. Lying `Raises:` in `spawn_sensors` docstring

**File:** `marslab/sensors/sensor_spawner.py:98-100`

**Quote:**
```
Raises:
    KeyError: If required cfg keys (``camera``, ``imu``,
        ``lidar_3d``/``lidar``) are missing.
```

**Problem.** The function does not raise `KeyError` for `lidar_3d`/`lidar`. Line 118 is `lidar_cfg = sensors_cfg.get("lidar_3d") or sensors_cfg.get("lidar")`. If both keys are missing, `lidar_cfg` becomes `None`, and the *actual* failure point is `lidar_cfg["profile"]` (L170), which raises `TypeError: 'NoneType' object is not subscriptable`, not `KeyError`. The docstring lies.

Also the Raises section omits:
- `KeyError` on `ros2_cfg["rates"]["imu"]` (L199) — actually this one does raise KeyError, but the docstring only mentions `sensors_cfg` keys.
- `RuntimeError` / Isaac-Sim exceptions from `camera.initialize()` / `lidar_3d.initialize()` / `imu.initialize()`.

**Fix.** Either make it true: replace `sensors_cfg.get("lidar_3d") or sensors_cfg.get("lidar")` with explicit
```python
if "lidar_3d" in sensors_cfg: lidar_cfg = sensors_cfg["lidar_3d"]
elif "lidar" in sensors_cfg: lidar_cfg = sensors_cfg["lidar"]
else: raise KeyError("sensors_cfg requires 'lidar_3d' or 'lidar'")
```
or remove the Raises section.

---

## 16. Duplication across `camera.py` / `imu.py` / `lidar.py` (known smell, confirmed)

Every `attach_*` function repeats the same 8-line boilerplate:

```python
name = config["name"]
mount_link = config["mount_link"]
parent_path = f"{robot_prim_path}/{mount_link}"
sensor_path = f"{parent_path}/{name}"
offset_pos = config.get("offset_position", [0.0, 0.0, 0.0])

parent_prim = stage.GetPrimAtPath(parent_path)
if not parent_prim.IsValid():
    parent_path = robot_prim_path
    sensor_path = f"{parent_path}/{name}"
```

Present in `camera.py:36-41`, `imu.py:29-40`, `lidar.py:32-49`. Plus each file has a near-identical try/except for the Isaac-Sim import (`from isaacsim.sensors.camera import Camera` with `omni.isaac.sensor` fallback — L31-34 camera.py, L69-71 imu.py, L119-121 lidar.py).

**Fix.** Extract `_resolve_mount(stage, robot_prim_path, config) -> (parent_path, sensor_path)` into a private helper in `__init__.py` or a new `_mount.py`. Extract `_import_isaac_classes()` likewise. Drops 24 lines across the three files and fixes the silent-fallback issue (#4) in one place.

---

## 17. `_read_frame` is a one-liner wrapper over `np.array` — dubious DRY

**File:** `marslab/sensors/camera.py:65-67`

**Quote:**
```python
def _read_frame(data, dtype) -> np.ndarray:
    """Coerce camera frame data to ``np.ndarray`` of ``dtype`` (empty if None)."""
    return np.array([] if data is None else data, dtype=dtype)
```

**Problem.** Saving three characters ("if None" vs explicit check) by funneling both callers through this helper is marginal. But more concerning: when `data is None`, this returns a *1-D empty array of shape `(0,)`*, not `(0, 0, 4)` for RGBA or `(0, 0)` for depth. The docstrings of `read_camera_rgb` / `read_camera_depth` promise "(H, W, 4)" / "(H, W)" shapes. A caller doing `img.shape[0]` will see 0 instead of raising — another silent-fallback that hides a "camera not ready" state as "image is empty". If downstream ROS2 bridge code then tries `cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)`, OpenCV will cheerfully error on a 1-D array with a message unrelated to the root cause.

**Fix.** Return `np.empty((0, 0, 4), dtype=np.uint8)` / `np.empty((0, 0), dtype=np.float32)` explicitly, or raise `RuntimeError("Camera frame not available; was world.step(render=True) called?")`.

---

## 18. Type hint on `load_and_attach_sensor` return is `str | object` — meaningless

**File:** `marslab/sensors/__init__.py:32`

**Quote:**
```python
def load_and_attach_sensor(stage, robot_prim_path: str, config_path: str) -> str | object:
```

**Problem.** `str | object` is equivalent to just `object` because `str` is a subclass of `object`. The type hint tells the reader nothing. The real return type is the union of `attach_camera`'s return (a `Camera` handle), `attach_imu`'s (a `str` prim path), and `attach_lidar`'s (a `str` prim path). So `Union[Camera, str]` — which is itself a mixed-semantic return and a separate smell (#19).

Also `stage` is entirely untyped.

**Fix.** Either:
- Give all three attach functions the same return shape — a `SensorHandle` dataclass with `prim_path: str` and optional `handle: Any` — and type-hint it properly; or
- Write `Union["Camera", str]` with TYPE_CHECKING import.

---

## 19. `attach_camera` returns a `Camera` object, `attach_imu` / `attach_lidar` return `str` — API smell

**Files:** `camera.py:62`, `imu.py:52`, `lidar.py:107`

**Problem.** One sensor returns a live wrapper object, the other two return a prim-path string. The caller has to know which is which. `load_and_attach_sensor` happily returns `str | object` (see #18) and punts the decision. Any generic caller that wants to later read the sensor has to case-split on type. This is Fowler-smell *Primitive Obsession* + *Inconsistent Interface*.

**Fix.** Make all three return the same shape. Either all return the prim path (and `read_*` resolves the handle internally) or all return a `SensorHandle` dataclass. See also #1 — `sensor_spawner.py` *already* defines a `SensorHandles` dataclass. Unify.

---

## 20. No seed propagation — domain-randomization story absent

**Files:** all five

**Problem.** None of `attach_camera / attach_imu / attach_lidar / spawn_sensors` accept a `seed` parameter. The CLAUDE-style rules on this project demand "every randomized process must accept a seed". Sensors don't randomize today, but as soon as noise models land (explicitly called out as "Noise models deferred to Phase D" in `configs/sensors/imu.yaml:3`), the seed plumbing will have to retrofit through five files.

**Fix.** Add `seed: int | None = None` to all `attach_*` signatures now; pass it unused. Future noise-model wrappers will thank you.

---

## 21. No noise models, no wrapper separation — but the module pretends to care

**Files:** all; `configs/sensors/imu.yaml:3`

**Problem.** Reviewer prompt explicitly asks "are noise wrappers properly separated?" — there are no noise wrappers at all. Zero. `read_imu` returns raw sensor data with `read_gravity=True`. `read_camera_rgb / read_camera_depth / read_lidar_point_cloud` return raw arrays. The YAML comment "Noise models deferred to Phase D" is a promissory note against a phase that the module provides no hook to plug into. A future implementer will have to either:
1. Monkey-patch `read_*` (ugly); or
2. Add a wrapper at the ROS2-bridge layer (then noise is coupled to transport, which is wrong); or
3. Add a `wrap_with_noise(handle, noise_cfg)` step to `spawn_sensors` (the right answer, currently impossible because `spawn_sensors` is 1 of 2 disjoint pipelines — see #1).

**Fix.** Before merging noise, unify the two pipelines (#1) and add a `noise: Optional[NoiseCfg] = None` parameter to `SensorHandles`. The dataclass can hold a callable that `read_*` applies if present. Without this, noise will land as a god-patch.

---

## 22. `__init__.py` YAML-dispatch is a mini plugin registry — contradicts its own docstring

**File:** `marslab/sensors/__init__.py:3-4, 25-29`

**Quote:**
```python
"""Sensor attachment for MarsLab.

Dispatches sensor config YAMLs to the correct attach function
based on the 'type' field. No base class, no registry (P1).
"""
...
_SENSOR_DISPATCH = {
    "camera": attach_camera,
    "imu": attach_imu,
    "lidar": attach_lidar,
}
```

**Problem.** "No base class, no registry (P1)" is the claim. `_SENSOR_DISPATCH` **is** a registry — a plain-dict lookup by string key is the simplest form of a registry pattern, which the comment forswears. Either the policy P1 allows it (then delete the comment), or it doesn't (then delete the dict and call the three functions from a flat `if/elif`). As-is, the file is lying about its own design.

**Fix.** Delete the parenthetical "(P1)" if the dict stays; or replace the dict with an if/elif if the policy is real.

---

## 23. `camera.py` fallback Isaac import is already-retired API

**File:** `marslab/sensors/camera.py:31-34`

**Quote:**
```python
try:
    from isaacsim.sensors.camera import Camera
except ImportError:
    from omni.isaac.sensor import Camera
```

**Problem.** `omni.isaac.sensor` is an Isaac Sim 4.x extension path. The project target is Isaac Sim 5.x where `isaacsim.sensors.*` is canonical. Carrying a fallback to the pre-5.x path in every sensor file encourages someone to run against an old kit app and then discover subtle API drifts at runtime (resolution-tuple ordering, translation units). The pre-5.x path is also *not* `omni.isaac.orbit`-class deprecated — `omni.isaac.sensor` still exists — but it's a different API surface with different bugs.

Same pattern in `imu.py:68-71` and `lidar.py:119-121` — triple copy-paste.

**Fix.** Pick one Isaac Sim major version and delete the fallback. If the project truly needs dual support, extract `from marslab.sensors._isaac_compat import Camera, IMUSensorInterface, LidarInterface` and house the version check in one file.

---

## 24. Missing type hints on `stage` parameter everywhere

All attach functions: `stage` has no type hint. The project's own coding standard ("Type hints on all public functions") is the first bullet of the General section. If `stage` is `pxr.Usd.Stage`, type it. If it's `omni.usd.UsdContext`, type that. The reviewer cannot tell from signatures what kind of stage handle is expected — that's why the code has to call `stage.GetPrimAtPath(...)` and pray.

**Fix.** Add `stage: "pxr.Usd.Stage"` everywhere (quoted for offline import compat).

---

## 25. `sensor_spawner.py` return type of `spawn_sensors` assumes 2D LiDAR optional, but `lidar_3d_prim_path` is non-Optional while `lidar_cfg` can be None

**File:** `marslab/sensors/sensor_spawner.py:118, 170`

**Quote:**
```python
lidar_cfg = sensors_cfg.get("lidar_3d") or sensors_cfg.get("lidar")
...
lidar_3d = LidarRtx(
    prim_path=lidar_prim_path,
    config_file_name=lidar_cfg["profile"],
    translation=np.asarray(lidar_cfg["local_translation"], dtype=np.float32),
)
```

**Problem.** If both `lidar_3d` and `lidar` keys are absent, `lidar_cfg is None`, and `lidar_cfg["profile"]` raises `TypeError` at L170 (already flagged in #15). But typing-wise, `SensorHandles.lidar_3d: Any` and `lidar_3d_prim_path: str` — declaring non-Optional — is still honest only because the TypeError cuts the function short. If a future `sensors_cfg.get("lidar_3d") or {}` defensive default lands, the typing will become false.

**Fix.** Explicit early raise with a clear message (#15 fix covers this) and the dataclass types stay correct.

---

## 26. Bare `"lidar"` legacy key accepted silently — spec-drift accelerator

**File:** `marslab/sensors/sensor_spawner.py:117-118`

**Quote:**
```python
# Stage-3 uses "lidar_3d"; Stage-1 phase1.yaml used "lidar". Accept both.
lidar_cfg = sensors_cfg.get("lidar_3d") or sensors_cfg.get("lidar")
```

**Problem.** Dual-key acceptance with zero deprecation warning. If any config file still uses `lidar`, it will keep working forever and the code base ossifies. Meanwhile `configs/sensors/lidar_3d.yaml` uses `lidar_3d` as filename but type `lidar` (see Path A's dispatch), so there are *three* naming conventions floating around: `lidar_3d` (Path B), `lidar` (legacy Path B), `lidar` (Path A dispatch type).

**Fix.** Emit `DeprecationWarning` when the `lidar` key is used. Pin a removal date. Grep the repo and migrate existing configs. Then delete the fallback.

---

## 27. Dead code / delete candidate

**`camera.py` entire file.** If Path B (`sensor_spawner.py`) is the survivor after #1, this file is dead. Move to `delete_later/`. Same for `imu.py`, `lidar.py` `attach_*` functions — but `read_imu` / `read_camera_rgb` / `read_camera_depth` / `read_lidar_point_cloud` are still needed by any caller that has only the prim path. Either:

- Keep `read_*` helpers, delete `attach_*`; or
- Move `read_*` helpers into `sensor_spawner.py` under `SensorHandles.read_imu() / .read_rgb() / ...` methods and delete the individual files.

The latter is cleaner: the data class already knows the handle, and OO-style `handles.camera.get_rgba()` is the Isaac-Sim native way.

---

## 28. Security / safety: `yaml.safe_load` is correct — but `config_path` from user has no sanity check

**File:** `marslab/sensors/__init__.py:50-55`

**Quote:**
```python
abs_path = os.path.abspath(config_path)
if not os.path.isfile(abs_path):
    raise FileNotFoundError(f"Sensor config not found: {abs_path}")

with open(abs_path, "r") as f:
    data = yaml.safe_load(f)
```

**Problem.** `yaml.safe_load` is correctly used (no arbitrary Python object deserialization). `os.path.abspath` is fine. However, `config_path` accepts any absolute path — no sandboxing to `configs/sensors/`. If the runtime script ever takes sensor paths from a web UI / ROS2 parameter / env var, this is classic path-traversal to read arbitrary YAML and spawn whatever sensor type happens to be there. Low severity today because usage is local-only, but *document* it: add `# Security note: config_path is trusted; do not pass user input.` and consider constraining to under a root dir.

**Fix.** Add the comment. Optionally resolve + check `abs_path.is_relative_to(CONFIG_ROOT)`.

---

## 29. Docstring dates / citations that don't match delivered behavior

**File:** `marslab/sensors/sensor_spawner.py:17-19`

**Quote:**
```
Per R4-2 of the MarsLab refactoring plan, this file is the only place
that knows how the four physical sensors are attached to the rover.
```

**Problem.** Reviewer stance: internal-term citations (R4-2, §7.17, §10.8) are not evidence of correctness; they are the author telling themselves "this was reviewed". Also untrue at face value: `marslab/sensors/camera.py`, `imu.py`, `lidar.py` also know how sensors are attached. Either the citation is wrong or the Path-A files should not exist (which is #1). The docstring further says `rpy_to_quat` is imported from `marslab.robots.rover` because of an "import surface" concern (L104-107) — a concern irrelevant to a new file. Both citations read as status-signaling.

**Fix.** Delete the citations; let the code stand on the code.

---

## 30. `__init__.py::_SENSOR_DISPATCH` type `"lidar"` collides with 2D vs 3D LiDAR in `sensor_spawner.py`

**File:** `marslab/sensors/__init__.py:28` vs `sensor_spawner.py:178-193`

**Problem.** Path A dispatches on `type: "lidar"`. Path B distinguishes 2D vs 3D LiDARs with separate config blocks (`lidar_3d`, `lidar_2d`) at the scenario level, not a type string. So if someone drops a 2D LiDAR into the Path A pipeline, they have to write `type: lidar` plus a 2D profile parameter, and Path A's `attach_lidar` blindly creates an RTX-rotary LiDAR via `RangeSensorCreateLidar` — there is no 2D code path. A user who reads the code and sees `lidar_2d.yaml` alongside `lidar_3d.yaml` will believe both are supported by `load_and_attach_sensor`. They are not; only the RTX-rotary 3D profile works.

**Fix.** Either add a dedicated 2D handler to Path A or mark `attach_lidar` as 3D-only in docstring AND in the YAML `type` field (`type: "lidar_3d"`).

---

# Summary (3 lines)

The `marslab/sensors/` package ships two disjoint sensor-spawn pipelines (`attach_*` + `__init__.py` dispatch vs `sensor_spawner.py`) with incompatible YAML schemas, incompatible Isaac-Sim APIs, and three silent `mount_link` fallbacks that hide config bugs as wrong placements — pick one, delete the other. The IMU module's "critical test" claim (z ≈ 3.72 m/s² at rest) is nowhere enforced — no gravity assertion at spawn, no range check at read — and `offset_orientation` is documented+YAML'd for IMU and LiDAR while being silently discarded by both implementations; docstrings are lying. Add seed plumbing and a `SensorHandles`-shaped noise-wrapper slot now before Phase-D noise models, kill the `stage1_*` prim-name artifact, remove the `lidar_params` duplication in `lidar.py`, and replace hardcoded FOV/resolution/update-rate defaults with a proper pydantic schema — the G5 "all in YAML" promise is currently a polite fiction.
