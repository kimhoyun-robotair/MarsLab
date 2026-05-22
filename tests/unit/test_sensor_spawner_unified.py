"""Regression tests locking in the Path A -> Path B unification.

These tests guarantee that the legacy Path A surface
(``attach_camera`` / ``attach_imu`` / ``attach_lidar`` /
``load_and_attach_sensor``) is no longer exported from
:mod:`marslab.sensors` and that no in-tree MarsLab module imports
from the deprecated ``camera.py`` / ``imu.py`` / ``lidar.py`` files.
They also smoke-test the read-side helpers that moved onto
:class:`marslab.sensors.sensor_spawner.SensorHandles` so a future
refactor cannot silently drop them.
"""

from __future__ import annotations

import ast
import pathlib
import sys
from typing import List, Tuple

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MARSLAB_DIR = REPO_ROOT / "marslab"
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Legacy Path A modules (kept on disk behind a deprecation notice until
# the user runs ``git rm``).  In-tree callers must not import these.
_PATH_A_MODULES = {
    "marslab.sensors.camera",
    "marslab.sensors.imu",
    "marslab.sensors.lidar",
}
_PATH_A_NAMES = {
    "attach_camera",
    "attach_imu",
    "attach_lidar",
    "load_and_attach_sensor",
}


def test_sensor_handles_has_read_imu() -> None:
    """``SensorHandles.read_imu`` must exist as an instance method.

    Ported from Path A's free ``read_imu`` function during the
    Path A -> Path B unification.
    """
    from marslab.sensors.sensor_spawner import SensorHandles

    assert hasattr(SensorHandles, "read_imu")
    assert callable(SensorHandles.read_imu)
    # Also guard the other read-side helpers that migrated across.
    for name in (
        "read_camera_rgb",
        "read_camera_depth",
        "read_lidar_3d_point_cloud",
    ):
        assert hasattr(SensorHandles, name), f"SensorHandles lost helper {name!r}"
        assert callable(getattr(SensorHandles, name))


def test_sensor_handles_read_imu_asserts_mars_gravity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mars-gravity invariant is preserved on Path B.

    Calls ``SensorHandles.read_imu`` with a stubbed IMU interface
    that returns Earth gravity (9.81 m/s^2). The soft warning
    referencing Mars gravity (3.72 m/s^2) must still fire -- this is
    the runtime-side guard that complements the attach-time hard
    assertion.
    """
    import logging
    import types

    # Stub the ``isaacsim.sensors.physics._sensor`` module so ``read_imu``
    # returns 9.81 on the z-axis without needing Isaac Sim.
    class _Reading:
        lin_acc_x = 0.0
        lin_acc_y = 0.0
        lin_acc_z = 9.81
        ang_vel_x = 0.0
        ang_vel_y = 0.0
        ang_vel_z = 0.0

    class _Interface:
        def get_sensor_reading(self, *_a: object, **_k: object) -> _Reading:
            return _Reading()

    sensor_mod = types.ModuleType("isaacsim.sensors.physics._sensor")
    sensor_mod.acquire_imu_sensor_interface = lambda: _Interface()  # type: ignore[attr-defined]
    phys_mod = sys.modules.get("isaacsim.sensors.physics") or types.ModuleType(
        "isaacsim.sensors.physics"
    )
    phys_mod._sensor = sensor_mod  # type: ignore[attr-defined]
    isaacsim_pkg = sys.modules.get("isaacsim") or types.ModuleType("isaacsim")
    sensors_pkg = sys.modules.get("isaacsim.sensors") or types.ModuleType("isaacsim.sensors")

    monkeypatch.setitem(sys.modules, "isaacsim", isaacsim_pkg)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors", sensors_pkg)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors.physics", phys_mod)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors.physics._sensor", sensor_mod)

    # Force re-import so ``read_imu`` binds to our stub via the
    # function-local ``from isaacsim.sensors.physics import _sensor``.
    sys.modules.pop("marslab.sensors.sensor_spawner", None)
    sys.modules.pop("marslab.sensors", None)

    from marslab.sensors.sensor_spawner import SensorHandles

    handles = SensorHandles(
        camera=None,
        lidar_3d=None,
        lidar_2d=None,
        imu=object(),
        camera_prim_path="/World/Rover/camera",
        lidar_3d_prim_path="/World/Rover/lidar_3d",
        lidar_2d_prim_path=None,
        imu_prim_path="/World/Rover/imu",
    )

    caplog_logger = logging.getLogger("marslab.sensors.sensor_spawner")
    caplog_logger.propagate = True

    # Attach an explicit handler so we can read records deterministically
    # without relying on the pytest ``caplog`` fixture (kept simple so the
    # regression target is obvious).
    records: List[logging.LogRecord] = []

    class _CollectHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _CollectHandler(level=logging.WARNING)
    caplog_logger.addHandler(handler)
    try:
        data = handles.read_imu()
    finally:
        caplog_logger.removeHandler(handler)

    assert data["lin_acc"][2] == pytest.approx(9.81)
    msgs = [r.getMessage() for r in records]
    assert any(
        "deviates from Mars gravity" in m and "3.72" in m for m in msgs
    ), f"expected Mars-gravity deviation warning, got {msgs!r}"


def test_path_a_not_exported_from_init() -> None:
    """``from marslab.sensors import attach_camera`` must raise ``ImportError``.

    Locks in the Path A removal from :mod:`marslab.sensors.__init__`.
    """
    import importlib

    # Fresh import to avoid stale cached attributes from other tests in
    # this session.
    sys.modules.pop("marslab.sensors", None)
    marslab_sensors = importlib.import_module("marslab.sensors")

    for name in _PATH_A_NAMES:
        assert not hasattr(
            marslab_sensors, name
        ), f"marslab.sensors must not export deprecated Path A name {name!r}."

    # The canonical Path B surface must still be present.
    assert hasattr(marslab_sensors, "SensorHandles")
    assert hasattr(marslab_sensors, "spawn_sensors")


def _iter_python_source_files() -> List[pathlib.Path]:
    """Return every in-tree MarsLab Python source file outside of tests."""
    files: List[pathlib.Path] = []
    for root in (MARSLAB_DIR, SCRIPTS_DIR):
        if not root.exists():
            continue
        files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return files


def _collect_imports(path: pathlib.Path) -> List[Tuple[str, str]]:
    """Parse ``path`` and yield ``(module, imported_name)`` pairs.

    ``imported_name`` is ``""`` for bare ``import x`` statements.  For
    ``from a.b import c`` we return ``("a.b", "c")``.
    """
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:  # pragma: no cover - guard against malformed files
        pytest.fail(f"Could not parse {path}: {exc}")
    pairs: List[Tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                pairs.append((node.module, alias.name))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                pairs.append((alias.name, ""))
    return pairs


def test_no_marslab_module_imports_path_a() -> None:
    """No in-tree MarsLab source file may import the deprecated Path A modules.

    Skips ``marslab/sensors/__init__.py`` and the Path A modules themselves
    (``camera.py`` / ``imu.py`` / ``lidar.py``) which are allowed to
    self-reference in their deprecation notices.  Also skips the
    ``tests/`` tree — the legacy test file is being migrated in the same
    batch and is covered by ``test_path_a_not_exported_from_init``.
    """
    allowed_self = {
        MARSLAB_DIR / "sensors" / "__init__.py",
        MARSLAB_DIR / "sensors" / "camera.py",
        MARSLAB_DIR / "sensors" / "imu.py",
        MARSLAB_DIR / "sensors" / "lidar.py",
    }

    offenders: List[str] = []
    for src_file in _iter_python_source_files():
        if src_file in allowed_self:
            continue
        for module, name in _collect_imports(src_file):
            # ``from marslab.sensors.camera import attach_camera`` or bare
            # ``import marslab.sensors.camera``.
            if module in _PATH_A_MODULES:
                offenders.append(f"{src_file}: from {module} import {name or '*'}")
                continue
            # ``from marslab.sensors import attach_camera`` (re-export path).
            if module == "marslab.sensors" and name in _PATH_A_NAMES:
                offenders.append(f"{src_file}: from marslab.sensors import {name}")

    assert not offenders, "in-tree Path A imports must be zero:\n  " + "\n  ".join(offenders)
