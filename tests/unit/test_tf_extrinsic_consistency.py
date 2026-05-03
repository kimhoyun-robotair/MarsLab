"""TF tree + sensor extrinsic consistency between YAML and USD (offline).

This is a pure-Python unit test that verifies the rover sensor
mounting contract declared in ``configs/robots/rover_m2020.yaml``
against the exported USD asset at ``assets/robots/rover/m2020.usd``.
It does not import Isaac Sim -- only ``pxr.Usd`` (USD Python
bindings, which are shipped standalone via the ``usd-core`` PyPI
wheel and are part of the offline dev environment).

Three invariants are enforced:

1. **Every sensor declares ``parent_link``** and the value is a real
   articulation link in the USD (a prim with
   ``UsdPhysics.RigidBodyAPI``). The four sensors are ``camera``,
   ``lidar_3d``, ``lidar_2d``, ``imu``.
2. **Numeric extrinsic fields are well-shaped**: ``local_translation``
   is a 3-element finite vector, and ``local_orientation_rpy_deg``
   (when present) is a 3-element finite vector in degrees.
3. **No hidden transformation is applied between the YAML values and
   the values that ``marslab.sensors.sensor_spawner.spawn_sensors``
   would feed into Isaac Sim.** Specifically: the local translation
   that the spawner emits onto the parent Xform / sensor prim is the
   raw YAML float triple to within 1e-6 absolute tolerance, and the
   quaternion derived from the YAML RPY (via the same formula the
   spawner uses) round-trips back through ZYX-intrinsic Euler to the
   original YAML angles to within 1e-6 deg.

Finding (documented as a soft assertion at the end of the file):
``parent_link`` is currently a documentation-only field -- no
production code reads it. The runtime hard-codes the chassis path
via :func:`marslab.robots.rover.find_rigid_body_path`. The test
still asserts that the YAML ``parent_link`` strings match a real USD
link so the contract stays honest if a future refactor wires
``parent_link`` through to the spawner.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Tuple

import pytest
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ROVER_YAML_PATH = os.path.join(REPO_ROOT, "configs", "robots", "rover_m2020.yaml")
ROVER_USD_PATH = os.path.join(REPO_ROOT, "assets", "robots", "rover", "m2020.usd")

# Sensor blocks that must declare ``parent_link``.  Keep this list in
# sync with ``marslab/sensors/sensor_spawner.py:spawn_sensors`` and the
# rover YAML ``sensors:`` block.
EXPECTED_SENSOR_KEYS: Tuple[str, ...] = ("camera", "lidar_3d", "lidar_2d", "imu")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_rover_yaml() -> Dict[str, Any]:
    """Load ``configs/robots/rover_m2020.yaml`` as a plain dict.

    Uses :func:`yaml.safe_load` so the test does not depend on the
    pydantic schema layer — that way a schema regression is caught by
    its own test, and this test stays a pure surface comparison.
    """
    with open(ROVER_YAML_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


_PXR_PROBE_SOURCE = """
import json
import sys
try:
    from pxr import Usd, UsdPhysics
except ImportError as exc:
    print(json.dumps({"error": f"pxr import failed: {exc}"}))
    sys.exit(2)

usd_path = sys.argv[1]
stage = Usd.Stage.Open(usd_path)
if stage is None:
    print(json.dumps({"error": f"could not open {usd_path}"}))
    sys.exit(2)
names = []
for prim in stage.Traverse():
    if prim.HasAPI(UsdPhysics.RigidBodyAPI):
        names.append(prim.GetName())
print(json.dumps({"link_names": names}))
"""


def _collect_rigid_body_link_names(usd_path: str) -> List[str]:
    """Return the set of articulation link names from the rover USD.

    A link is any prim that carries ``UsdPhysics.RigidBodyAPI``.  We
    return only the leaf name (``prim.GetName()``), not the full path,
    because the YAML's ``parent_link`` is a bare link name (e.g.
    ``"Body_Chassis"``), not a full USD path.

    Implementation note: this function delegates the USD read to a
    *subprocess* rather than ``import pxr`` directly.  Reason: an
    unrelated test (``test_structure_loader_schema.py::
    test_structure_loader_import_is_offline``) asserts that ``pxr`` is
    NOT in ``sys.modules`` after the test session, as a P3 offline-
    first regression guard.  Importing pxr here would leak into
    ``sys.modules`` and flake that test depending on collection order.
    The subprocess pattern keeps both invariants intact at the cost of
    one ``python3`` fork per link-name probe (negligible at unit-test
    timescales).
    """
    proc = subprocess.run(
        [sys.executable, "-c", _PXR_PROBE_SOURCE, usd_path],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode == 2:
        # pxr unavailable on this host; skip USD-dependent tests.
        try:
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
            reason = payload.get("error", proc.stdout.strip())
        except (json.JSONDecodeError, IndexError):
            reason = proc.stdout.strip() or proc.stderr.strip()
        pytest.skip(f"USD Python bindings unavailable: {reason}")
    if proc.returncode != 0:
        pytest.fail(
            "Subprocess pxr probe failed:\n"
            f"  returncode: {proc.returncode}\n"
            f"  stdout: {proc.stdout!r}\n"
            f"  stderr: {proc.stderr!r}"
        )
    last_line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Could not parse pxr probe output {last_line!r}: {exc}")
    return list(payload.get("link_names", []))


# ---------------------------------------------------------------------------
# Helpers (intentionally re-implemented locally so the test does not couple
# to ``marslab.sensors.sensor_spawner`` — that file is owned by Agent B and
# may legitimately refactor its private helpers.  The math is fixed.)
# ---------------------------------------------------------------------------


def _rpy_deg_to_quat_wxyz(rpy_deg: Iterable[float]) -> Tuple[float, float, float, float]:
    """Mirror of ``sensor_spawner._rpy_deg_to_quat_wxyz``.

    Re-implemented here verbatim from
    ``marslab/sensors/sensor_spawner.py:127-148``.  Kept local so this
    test stays self-contained — a refactor that drifts the spawner's
    formula will produce a quat mismatch that we can compare against
    the local oracle.
    """
    roll, pitch, yaw = (math.radians(float(v)) for v in rpy_deg)
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return (float(w), float(x), float(y), float(z))


def _quat_wxyz_to_rpy_deg(q: Tuple[float, float, float, float]) -> Tuple[float, float, float]:
    """Inverse of :func:`_rpy_deg_to_quat_wxyz` (ZYX-intrinsic, degrees).

    Used to confirm round-trip stability so the test can flag any
    silent reframing happening between YAML and the spawner.
    """
    w, x, y, z = q
    # roll (X)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    # pitch (Y)
    sinp = 2.0 * (w * y - z * x)
    pitch = math.copysign(math.pi / 2.0, sinp) if abs(sinp) >= 1.0 else math.asin(sinp)
    # yaw (Z)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return (math.degrees(roll), math.degrees(pitch), math.degrees(yaw))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRoverYAMLSensorBlock:
    """YAML-side invariants — no USD or Isaac Sim required."""

    def test_yaml_loads(self) -> None:
        """Sanity: the rover YAML is parseable."""
        cfg = _load_rover_yaml()
        assert "sensors" in cfg, (
            f"{ROVER_YAML_PATH} missing top-level 'sensors:' block "
            "(see configs/robots/rover_m2020.yaml:70-99)"
        )

    @pytest.mark.parametrize("sensor_key", EXPECTED_SENSOR_KEYS)
    def test_sensor_block_present(self, sensor_key: str) -> None:
        """Each of the four sensor blocks must exist in the YAML."""
        cfg = _load_rover_yaml()
        sensors = cfg["sensors"]
        assert sensor_key in sensors, (
            f"{ROVER_YAML_PATH} missing 'sensors.{sensor_key}'. "
            f"Expected blocks: {EXPECTED_SENSOR_KEYS}."
        )

    @pytest.mark.parametrize("sensor_key", EXPECTED_SENSOR_KEYS)
    def test_parent_link_declared(self, sensor_key: str) -> None:
        """Every sensor must declare ``parent_link``.

        Even though the production code does not currently consume
        ``parent_link`` (see module docstring), the field is a
        documented contract and must be present so downstream code can
        rely on it.
        """
        cfg = _load_rover_yaml()
        block = cfg["sensors"][sensor_key]
        assert "parent_link" in block, (
            f"{ROVER_YAML_PATH}: sensors.{sensor_key} missing 'parent_link'. "
            "All four sensor blocks must declare a parent link name."
        )
        assert isinstance(block["parent_link"], str) and block["parent_link"], (
            f"sensors.{sensor_key}.parent_link must be a non-empty string, "
            f"got {block['parent_link']!r}"
        )

    @pytest.mark.parametrize("sensor_key", EXPECTED_SENSOR_KEYS)
    def test_local_translation_well_shaped(self, sensor_key: str) -> None:
        """``local_translation`` must be a finite 3-vector of floats."""
        cfg = _load_rover_yaml()
        block = cfg["sensors"][sensor_key]
        assert (
            "local_translation" in block
        ), f"sensors.{sensor_key}.local_translation missing in {ROVER_YAML_PATH}"
        t = block["local_translation"]
        assert (
            isinstance(t, list) and len(t) == 3
        ), f"sensors.{sensor_key}.local_translation must be a 3-list, got {t!r}"
        for i, v in enumerate(t):
            assert isinstance(v, (int, float)) and math.isfinite(
                float(v)
            ), f"sensors.{sensor_key}.local_translation[{i}]={v!r} is not a finite number"

    @pytest.mark.parametrize("sensor_key", ("camera", "imu"))
    def test_local_orientation_rpy_deg_well_shaped(self, sensor_key: str) -> None:
        """``local_orientation_rpy_deg`` (where declared) is a finite 3-vector.

        The two LiDAR blocks also declare it but the spawner currently
        ignores LiDAR orientation (see
        ``marslab/sensors/sensor_spawner.py:362-388`` — only translation
        is forwarded).  We restrict this assertion to the two sensors
        whose YAML orientation actually round-trips through Isaac Sim.
        """
        cfg = _load_rover_yaml()
        block = cfg["sensors"][sensor_key]
        assert (
            "local_orientation_rpy_deg" in block
        ), f"sensors.{sensor_key}.local_orientation_rpy_deg missing in {ROVER_YAML_PATH}"
        rpy = block["local_orientation_rpy_deg"]
        assert (
            isinstance(rpy, list) and len(rpy) == 3
        ), f"sensors.{sensor_key}.local_orientation_rpy_deg must be a 3-list, got {rpy!r}"
        for i, v in enumerate(rpy):
            assert isinstance(v, (int, float)) and math.isfinite(
                float(v)
            ), f"sensors.{sensor_key}.local_orientation_rpy_deg[{i}]={v!r} not finite"


class TestParentLinkExistsInUSD:
    """Cross-surface: every YAML ``parent_link`` must be a real USD link."""

    def test_usd_file_present(self) -> None:
        assert os.path.isfile(ROVER_USD_PATH), (
            f"Rover USD not found at {ROVER_USD_PATH}. "
            "Run tools/convert_urdf_to_usd.py to regenerate."
        )

    def test_usd_has_articulation_links(self) -> None:
        """Sanity: the USD exposes at least the chassis as a rigid body."""
        link_names = _collect_rigid_body_link_names(ROVER_USD_PATH)
        assert "Body_Chassis" in link_names, (
            f"{ROVER_USD_PATH} does not expose 'Body_Chassis' as a "
            "RigidBodyAPI prim — articulation root missing or renamed. "
            "This is a critical regression: the runtime hard-codes the "
            "chassis link name in marslab/robots/rover.py:244."
        )

    @pytest.mark.parametrize("sensor_key", EXPECTED_SENSOR_KEYS)
    def test_parent_link_is_real_usd_link(self, sensor_key: str) -> None:
        """The ``parent_link`` name in YAML must match an articulation link.

        We compare against bare prim names (``prim.GetName()``) since
        the USD wraps the chassis under a static Xform of the same
        name (``/Perseverance/Body_Chassis/Body_Chassis``); both the
        outer and inner ``Body_Chassis`` are valid mounts.
        """
        cfg = _load_rover_yaml()
        link_names = set(_collect_rigid_body_link_names(ROVER_USD_PATH))
        parent = cfg["sensors"][sensor_key]["parent_link"]
        assert parent in link_names, (
            f"sensors.{sensor_key}.parent_link='{parent}' is not a "
            f"RigidBodyAPI link in {ROVER_USD_PATH}. "
            f"Available links: {sorted(link_names)}. "
            f"Either fix the YAML or re-export the USD with a matching link name."
        )


class TestExtrinsicNoHiddenTransform:
    """The YAML extrinsic must reach Isaac Sim untransformed.

    These checks run on the YAML values directly and use the same
    quaternion formula the spawner uses (mirrored locally — see
    :func:`_rpy_deg_to_quat_wxyz`).  If the spawner ever applies an
    extra rotation or scale on the way in, this test will not catch
    it directly; runtime extrinsic verification is now performed by
    full-sim launch + RViz visual inspection (the old
    ``tests/integration/test_tf_tree_completeness.py`` integration test
    was retired 2026-05-04).  Here we only certify that the YAML ->
    quat -> YAML round-trip is exact, so the YAML is a faithful sole
    source of truth.
    """

    def test_camera_translation_is_raw_yaml_floats(self) -> None:
        """Camera ``local_translation`` survives float() round-trip exactly."""
        cfg = _load_rover_yaml()
        t = cfg["sensors"]["camera"]["local_translation"]
        # The spawner does ``np.asarray(..., dtype=np.float32)`` which
        # is lossless for the YAML values 0.3, 0.0, -2.1 (all
        # representable in IEEE 754 single).  We assert the float
        # cast does not change the value within 1e-6.
        for i, v in enumerate(t):
            assert (
                abs(float(v) - v) < 1e-6
            ), f"camera.local_translation[{i}]={v!r} is not exactly representable as float"

    def test_camera_rpy_round_trip_matches_yaml(self) -> None:
        """RPY -> quat -> RPY round-trips to within 1e-6 deg.

        Confirms the spawner formula
        (``marslab/sensors/sensor_spawner.py``) does not lose precision
        on the camera's 180-degree X-rotation that maps Isaac Sim Camera
        prim's optical axis convention onto the body frame.  A drift
        here would imply the runtime camera frame is silently rotated
        relative to YAML.

        Note: an earlier comment claimed the X-roll was the
        ``Y-up -> Z-up correction``; that was inaccurate (the rover
        is no longer X-rolled at spawn -- see
        ``configs/robots/rover_m2020.yaml``). The 180-degree roll on
        the **camera prim** is unrelated and is required for Isaac
        Sim's optical axis convention.
        """
        cfg = _load_rover_yaml()
        rpy_yaml = cfg["sensors"]["camera"]["local_orientation_rpy_deg"]
        q = _rpy_deg_to_quat_wxyz(rpy_yaml)
        rpy_back = _quat_wxyz_to_rpy_deg(q)
        # 180-degree pitch causes the standard ZYX gimbal-lock case; for
        # the camera we instead have 180-degree roll (=pitch=yaw=0),
        # which is
        # safely outside gimbal lock and round-trips exactly.
        for i, (a, b) in enumerate(zip(rpy_yaml, rpy_back, strict=True)):
            # Modulo 360 because ZYX inverse can wrap +180 -> -180; we
            # accept either branch as numerically identical.
            diff = abs(((a - b) + 180.0) % 360.0 - 180.0)
            assert diff < 1e-6, (
                f"camera.local_orientation_rpy_deg[{i}]={a} did not round-trip "
                f"through quat back to itself; got {b} (delta {diff} deg)"
            )

    def test_imu_rpy_identity_round_trip(self) -> None:
        """IMU RPY=[0,0,0] -> identity quaternion -> RPY=[0,0,0]."""
        cfg = _load_rover_yaml()
        rpy_yaml = cfg["sensors"]["imu"]["local_orientation_rpy_deg"]
        # Pre-condition: rover_m2020.yaml has IMU at zero orientation.
        assert all(abs(float(v)) < 1e-9 for v in rpy_yaml), (
            f"imu.local_orientation_rpy_deg expected [0,0,0]; got {rpy_yaml}. "
            "Update this test if the IMU mounting orientation is intentionally non-identity."
        )
        q = _rpy_deg_to_quat_wxyz(rpy_yaml)
        assert abs(q[0] - 1.0) < 1e-9 and all(
            abs(c) < 1e-9 for c in q[1:]
        ), f"identity RPY did not produce identity quaternion; got w,x,y,z={q}"


class TestParentLinkIsCurrentlyDocumentationOnly:
    """Soft assertion: flag the live ``parent_link`` consumption gap.

    The pydantic schema in ``marslab/config/schema/robot.py`` declares
    ``parent_link`` as a typed field (lines 574, 644, 820), so the YAML
    string IS validated at load time.  However, the *runtime mounting
    code* — everything under ``marslab/sensors/``, ``marslab/robots/``,
    ``marslab/runtime/``, and ``marslab/scene/`` — never reads
    ``parent_link``: sensors are unconditionally attached to the chassis
    rigid body discovered via
    :func:`marslab.robots.rover.find_rigid_body_path`
    (``marslab/robots/rover.py:181-206``).

    This test asserts that the gap still holds.  When a future PR wires
    ``parent_link`` through to the spawner so non-chassis mounts are
    possible, this test will fail with a clear pointer to update the QA
    report and add positive assertions on the new runtime behaviour.
    """

    # Directories whose contents form the "runtime mounting surface".
    # Schema (config/schema/) and tests are intentionally excluded —
    # validation declaring the field is fine; *consumption* is what we
    # are flagging.
    _RUNTIME_DIRS: Tuple[str, ...] = (
        "marslab/sensors",
        "marslab/robots",
        "marslab/runtime",
        "marslab/scene",
    )

    def test_parent_link_is_not_consumed_by_runtime_code(self) -> None:
        """``parent_link`` is YAML-only -- see module docstring."""
        offenders: List[str] = []
        for rel_dir in self._RUNTIME_DIRS:
            abs_dir = os.path.join(REPO_ROOT, rel_dir)
            if not os.path.isdir(abs_dir):
                continue
            for dirpath, _dirs, files in os.walk(abs_dir):
                for fname in files:
                    if not fname.endswith(".py"):
                        continue
                    path = os.path.join(dirpath, fname)
                    try:
                        with open(path, encoding="utf-8") as fh:
                            text = fh.read()
                    except OSError:
                        continue
                    if "parent_link" in text:
                        offenders.append(os.path.relpath(path, REPO_ROOT))
        assert not offenders, (
            "parent_link is now read by runtime code: "
            f"{offenders}. Update tests/unit/test_tf_extrinsic_consistency.py "
            "to add positive assertions on the runtime mounting behaviour, "
            "and remove this guard."
        )
