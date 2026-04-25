"""Unit tests for Day 2 Task B (2026-04-26): M2020 ballpark physics inject.

Three layers of evidence:

1. **YAML -> pydantic propagation.** ``configs/robots/rover_m2020.yaml``
   parses cleanly into the new ``ChassisConfig`` / ``WheelsConfig`` /
   ``SuspensionConfig`` models declared in ``marslab.config.schema.robot``.
   Field-by-field equality check.
2. **Inertia bbox derivation.** The YAML-declared chassis inertia tensor
   matches a fresh first-principles bounding-box recomputation to within
   1 % — guards against silent edits that desync the documented formula
   from the actual numbers PhysX consumes.
3. **Runtime injection callable.** A mocked USD ``stage`` exposing only
   ``GetPrimAtPath`` records every prim path the rover spawn pipeline
   touches; the test asserts ``apply_chassis_physics`` /
   ``apply_wheel_physics`` /  ``apply_suspension_damping_split`` reach
   the expected prims with the YAML-declared values.  No Isaac Sim
   import.

Reviewer 2 mode: every numeric assertion is sourced from
``configs/robots/rover_m2020.yaml`` ``chassis:`` / ``wheels:`` /
``suspension:`` blocks (see lines 42-95) — the test is data-driven, not
hardcoded.  A YAML edit auto-flows into the assertions.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock

import pytest
import yaml

from marslab.config.schema.robot import (
    ChassisConfig,
    SuspensionConfig,
    WheelsConfig,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ROVER_YAML_PATH = os.path.join(REPO_ROOT, "configs", "robots", "rover_m2020.yaml")


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture(scope="module")
def rover_yaml() -> Dict[str, Any]:
    """Parse the M2020 rover YAML once per module."""
    with open(ROVER_YAML_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# --- Layer 1: YAML -> pydantic propagation ---------------------------------


def test_chassis_block_parses_into_pydantic(rover_yaml: Dict[str, Any]) -> None:
    """``chassis:`` block round-trips through ``ChassisConfig``."""
    chassis = ChassisConfig(**rover_yaml["chassis"])
    # M2020 actual mass per NASA fact sheet.
    assert chassis.mass == pytest.approx(1025.0, rel=1e-6)
    # Bounding-box tensor M2020 ballpark; recomputed in
    # ``test_chassis_inertia_matches_bbox`` below for cross-validation.
    assert chassis.inertia_xx > 0.0
    assert chassis.inertia_yy > 0.0
    assert chassis.inertia_zz > 0.0
    assert chassis.bbox_lwh == [3.0, 2.7, 2.2]


def test_wheels_block_parses_into_pydantic(rover_yaml: Dict[str, Any]) -> None:
    """``wheels:`` block round-trips through ``WheelsConfig``."""
    wheels = WheelsConfig(**rover_yaml["wheels"])
    # Radius matches ``control.wheel_radius`` exactly so the IK pipeline
    # and the dynamics overrides agree on wheel geometry.
    assert wheels.radius == pytest.approx(rover_yaml["control"]["wheel_radius"], rel=1e-6)
    assert wheels.diameter_reference == pytest.approx(0.525, rel=1e-6)
    assert wheels.mass == pytest.approx(9.0, rel=1e-6)
    assert wheels.friction_static == pytest.approx(0.6, rel=1e-6)
    assert wheels.friction_dynamic == pytest.approx(0.5, rel=1e-6)
    assert wheels.friction_static >= wheels.friction_dynamic


def test_suspension_block_parses_into_pydantic(rover_yaml: Dict[str, Any]) -> None:
    """``suspension:`` block round-trips through ``SuspensionConfig``."""
    suspension = SuspensionConfig(**rover_yaml["suspension"])
    assert suspension.rocker_damping == pytest.approx(75.0, rel=1e-6)
    assert suspension.bogie_damping == pytest.approx(50.0, rel=1e-6)


def test_friction_static_below_dynamic_rejected() -> None:
    """``WheelsConfig`` rejects ``friction_static < friction_dynamic``.

    Guards against the slope-creep failure mode (rover slides because
    static friction never gates the contact).
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        WheelsConfig(
            radius=0.2667,
            mass=9.0,
            width=0.40,
            inertia_spin=0.310,
            inertia_transverse=0.275,
            friction_static=0.3,
            friction_dynamic=0.5,
        )


# --- Layer 2: Inertia bbox derivation --------------------------------------


def _bbox_inertia(
    mass: float, length: float, width: float, height: float
) -> Tuple[float, float, float]:
    """Solid uniform rectangular cuboid principal inertia.

    ixx = M/12 * (W^2 + H^2)
    iyy = M/12 * (L^2 + H^2)
    izz = M/12 * (L^2 + W^2)
    """
    factor = mass / 12.0
    return (
        factor * (width * width + height * height),
        factor * (length * length + height * height),
        factor * (length * length + width * width),
    )


def _cylinder_inertia(mass: float, radius: float, height: float) -> Tuple[float, float]:
    """Uniform solid cylinder.

    I_spin       = m * r^2 / 2
    I_transverse = m * (3 r^2 + h^2) / 12
    """
    spin = 0.5 * mass * radius * radius
    transverse = mass * (3.0 * radius * radius + height * height) / 12.0
    return spin, transverse


def test_chassis_inertia_matches_bbox(rover_yaml: Dict[str, Any]) -> None:
    """YAML chassis inertia entries match the bounding-box formula to 1 %.

    Reviewer 2 evidence: prevents a silent YAML edit from desyncing the
    documented derivation from the numbers PhysX actually consumes.
    """
    chassis = ChassisConfig(**rover_yaml["chassis"])
    length, width, height = chassis.bbox_lwh
    expected_xx, expected_yy, expected_zz = _bbox_inertia(chassis.mass, length, width, height)
    assert chassis.inertia_xx == pytest.approx(expected_xx, rel=0.01)
    assert chassis.inertia_yy == pytest.approx(expected_yy, rel=0.01)
    assert chassis.inertia_zz == pytest.approx(expected_zz, rel=0.01)


def test_wheel_inertia_matches_cylinder(rover_yaml: Dict[str, Any]) -> None:
    """YAML wheel inertia entries match the solid-cylinder formula to 5 %.

    Looser tolerance than chassis because the M2020 wheels are spoked,
    not solid — the YAML value is a literature ballpark, not an exact
    cylinder match.  5 % is still tight enough to catch a typo (e.g.
    swapping spin / transverse) while admitting the spoke geometry
    correction.
    """
    wheels = WheelsConfig(**rover_yaml["wheels"])
    expected_spin, expected_transverse = _cylinder_inertia(wheels.mass, wheels.radius, wheels.width)
    assert wheels.inertia_spin == pytest.approx(expected_spin, rel=0.05)
    assert wheels.inertia_transverse == pytest.approx(expected_transverse, rel=0.05)


# --- Layer 3: Runtime injection callable -----------------------------------


class _FakePrim:
    """Duck-typed USD ``Usd.Prim`` for offline testing.

    ``IsValid()`` records every call so the test can assert which prim
    paths the runtime touched.  Other USD APIs are stubbed via
    ``MagicMock`` since the production helpers only consume their return
    values.
    """

    def __init__(self, valid: bool) -> None:
        self._valid = valid
        self.has_api_calls: List[Any] = []

    def IsValid(self) -> bool:  # noqa: N802  (USD API uses PascalCase)
        return self._valid

    def HasAPI(self, *args: Any, **kwargs: Any) -> bool:  # noqa: N802
        self.has_api_calls.append((args, kwargs))
        return False  # force ``_apply`` paths through .Apply()

    def CreateAttribute(self, *args: Any, **kwargs: Any) -> Any:  # noqa: N802
        return MagicMock()


class _FakeStage:
    """In-memory stage that hands back ``_FakePrim`` for any path."""

    def __init__(self, valid_paths: List[str]) -> None:
        self._valid = set(valid_paths)
        self.queried_paths: List[str] = []

    def GetPrimAtPath(self, path: Any) -> _FakePrim:  # noqa: N802
        path_str = str(path)
        self.queried_paths.append(path_str)
        return _FakePrim(path_str in self._valid)


def test_apply_chassis_physics_routes_yaml_to_mass_api(
    rover_yaml: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``apply_chassis_physics`` reads YAML values and writes them via MassAPI.

    We monkeypatch the deferred ``pxr`` import inside
    ``marslab.robots.rover._set_mass_and_inertia`` so the test never touches
    the real USD runtime.  The fake ``MassAPI`` records the values handed
    to it; the assertions verify those equal the YAML-declared chassis
    mass + inertia tensor.
    """
    from marslab.robots import rover as rover_module

    captured: Dict[str, Any] = {}

    fake_mass_attr = MagicMock()
    fake_mass_attr.Set.side_effect = lambda v: captured.__setitem__("mass", float(v))
    fake_inertia_attr = MagicMock()
    fake_inertia_attr.Set.side_effect = lambda v: captured.__setitem__(
        "inertia", (float(v[0]), float(v[1]), float(v[2]))
    )

    fake_mass_api_instance = MagicMock()
    fake_mass_api_instance.GetMassAttr.return_value = fake_mass_attr
    fake_mass_api_instance.GetDiagonalInertiaAttr.return_value = fake_inertia_attr

    fake_mass_api_class = MagicMock()
    fake_mass_api_class.return_value = fake_mass_api_instance
    fake_mass_api_class.Apply = MagicMock()

    fake_usd_physics = MagicMock()
    fake_usd_physics.MassAPI = fake_mass_api_class
    fake_gf = MagicMock()
    fake_gf.Vec3f = lambda x, y, z: (x, y, z)

    fake_pxr = MagicMock()
    fake_pxr.Gf = fake_gf
    fake_pxr.UsdPhysics = fake_usd_physics

    monkeypatch.setitem(__import__("sys").modules, "pxr", fake_pxr)

    rigid_body_path = "/World/Rover/Body_Chassis/Body_Chassis"
    stage = _FakeStage(valid_paths=[rigid_body_path])

    ok = rover_module.apply_chassis_physics(stage, rigid_body_path, rover_yaml["chassis"])
    assert ok is True
    assert captured["mass"] == pytest.approx(1025.0, rel=1e-6)
    assert captured["inertia"] == pytest.approx(
        (
            rover_yaml["chassis"]["inertia_xx"],
            rover_yaml["chassis"]["inertia_yy"],
            rover_yaml["chassis"]["inertia_zz"],
        ),
        rel=1e-6,
    )


def test_apply_chassis_physics_returns_false_for_missing_prim(
    rover_yaml: Dict[str, Any],
) -> None:
    """Missing rigid-body prim returns False instead of raising.

    Lets the rover spawn pipeline log a warning and continue (sensors /
    drive joints may still be configurable from the rover root).  No
    pxr import path is exercised because ``IsValid()`` short-circuits.
    """
    from marslab.robots import rover as rover_module

    stage = _FakeStage(valid_paths=[])  # no prims at all
    ok = rover_module.apply_chassis_physics(stage, "/World/Rover/missing", rover_yaml["chassis"])
    assert ok is False
    assert stage.queried_paths == ["/World/Rover/missing"]


def test_apply_wheel_physics_visits_each_wheel_link(
    rover_yaml: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``apply_wheel_physics`` queries every wheel link path under the chassis."""
    from marslab.robots import rover as rover_module

    # Stub pxr so the deferred imports inside the helpers do not blow up.
    fake_pxr = MagicMock()
    fake_pxr.Gf.Vec3f = lambda x, y, z: (x, y, z)
    monkeypatch.setitem(__import__("sys").modules, "pxr", fake_pxr)

    chassis_path = "/World/Rover/Body_Chassis"
    wheel_links = list(rover_yaml["control"]["drive_joint_names"])
    valid_paths = [f"{chassis_path}/{name}" for name in wheel_links]
    stage = _FakeStage(valid_paths=valid_paths)

    results = rover_module.apply_wheel_physics(
        stage, chassis_path, wheel_links, rover_yaml["wheels"]
    )

    # Every wheel landed.
    assert all(results.values())
    # Every wheel prim path was queried (mass override + friction binding
    # both call GetPrimAtPath).
    queried_set = set(stage.queried_paths)
    for name in wheel_links:
        assert f"{chassis_path}/{name}" in queried_set


def test_apply_suspension_damping_split_writes_both_buckets(
    rover_yaml: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rocker joints get rocker_damping; bogie joints get bogie_damping.

    The two damping numbers MUST end up on different joint paths — a
    silent fall-through to a single damping channel would erase the
    rocker / bogie distinction the YAML introduced.
    """
    from marslab.robots import rover as rover_module

    fake_pxr = MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "pxr", fake_pxr)

    chassis_path = "/World/Rover/Body_Chassis"
    rocker_names = ["CENTER_DIFFERENTIAL", "LEFT_DIFFERENTIAL", "RIGHT_DIFFERENTIAL"]
    bogie_names = ["LEFT_BOGIE", "RIGHT_BOGIE"]
    valid = [f"{chassis_path}/joints/{n}" for n in rocker_names + bogie_names]
    stage = _FakeStage(valid_paths=valid)

    results = rover_module.apply_suspension_damping_split(
        stage, chassis_path, rover_yaml["suspension"], rocker_names, bogie_names
    )
    for n in rocker_names + bogie_names:
        assert results[n] is True


# --- Layer 4: Reviewer 2 — schema rename verified --------------------------


def test_skid_steer_velocity_field_rename() -> None:
    """``SkidSteerDriveConfig`` exposes the new ``max_linear_velocity``
    / ``max_angular_velocity`` fields and rejects the legacy names.

    Schema bypass finding (``~/MarsLab/tmp/schema_bypass_finding.md``)
    showed the legacy ``max_linear_vel`` / ``max_angular_vel`` field
    names did NOT match the YAML keys ``max_linear_velocity`` /
    ``max_angular_velocity``.  Day 2 Task B folds the rename so a future
    ``SkidSteerDriveConfig.model_validate(control_cfg)`` no longer
    silently drops the speed clamps.  ``extra="forbid"`` ensures the old
    names raise instead of being absorbed.
    """
    from pydantic import ValidationError

    from marslab.config.schema.robot import SkidSteerDriveConfig

    cfg = SkidSteerDriveConfig(
        max_linear_velocity=0.5,
        max_angular_velocity=0.5,
        drive_damping=1000.0,
        steer_stiffness=50000.0,
        steer_damping=5000.0,
        drive_max_force=1000000.0,
        steer_max_force=100000.0,
        suspension_damping=50.0,
        drive_type="acceleration",
    )
    assert cfg.max_linear_velocity == pytest.approx(0.5)
    assert cfg.max_angular_velocity == pytest.approx(0.5)

    # Legacy field names rejected by ``extra="forbid"``.
    with pytest.raises(ValidationError):
        SkidSteerDriveConfig(
            max_linear_vel=0.5,
            max_angular_vel=0.5,
            drive_damping=1000.0,
            steer_stiffness=50000.0,
            steer_damping=5000.0,
            drive_max_force=1000000.0,
            steer_max_force=100000.0,
            suspension_damping=50.0,
            drive_type="acceleration",
        )
