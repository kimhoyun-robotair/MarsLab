"""Offline-testable cover for ``marslab.ros2_bridge.tf_nameoverrides``.

S3 release-blocker fix (2026-04-27).  The functions touch ``pxr.*``
inside the body, so the unit tests inject a duck-typed stage / prim
mock and assert that the ``isaac:nameOverride`` attribute creation
flows through unchanged.  ``pxr`` itself is not importable in CI, so
:func:`apply_nameoverride` and :func:`create_odom_anchor` must be
exercised through the deferred-import path with ``pxr`` faked in
``sys.modules``.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fake_pxr(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    """Inject a duck-typed ``pxr`` package so the deferred imports succeed."""
    pxr = types.ModuleType("pxr")
    sdf = types.ModuleType("pxr.Sdf")
    gf = types.ModuleType("pxr.Gf")
    usd_geom = types.ModuleType("pxr.UsdGeom")

    sdf.ValueTypeNames = types.SimpleNamespace(String="String")
    gf.Vec3d = lambda x, y, z: ("Vec3d", float(x), float(y), float(z))

    xform_define_calls: list[tuple] = []
    xform_handle = MagicMock(name="UsdGeom.Xform")
    xform_handle.GetPrim.return_value = MagicMock(name="anchor_prim")
    xform_handle.GetPrim.return_value.IsValid.return_value = True
    xform_handle.AddTranslateOp.return_value = MagicMock(name="translate_op")

    def _define(stage: object, path: str) -> MagicMock:
        xform_define_calls.append((stage, path))
        return xform_handle

    usd_geom.Xform = types.SimpleNamespace(Define=_define)

    pxr.Sdf = sdf
    pxr.Gf = gf
    pxr.UsdGeom = usd_geom

    monkeypatch.setitem(sys.modules, "pxr", pxr)
    monkeypatch.setitem(sys.modules, "pxr.Sdf", sdf)
    monkeypatch.setitem(sys.modules, "pxr.Gf", gf)
    monkeypatch.setitem(sys.modules, "pxr.UsdGeom", usd_geom)

    return types.SimpleNamespace(
        pxr=pxr,
        xform_handle=xform_handle,
        xform_define_calls=xform_define_calls,
    )


class TestApplyNameOverride:
    def test_writes_attribute_on_valid_prim(self, fake_pxr: types.SimpleNamespace) -> None:
        from marslab.ros2_bridge.tf_nameoverrides import apply_nameoverride

        prim = MagicMock()
        prim.IsValid.return_value = True
        attr = MagicMock()
        prim.CreateAttribute.return_value = attr

        stage = MagicMock()
        stage.GetPrimAtPath.return_value = prim

        ok = apply_nameoverride(stage, "/World/Rover/Body_Chassis/Body_Chassis", "base_link")

        assert ok is True
        prim.CreateAttribute.assert_called_once_with("isaac:nameOverride", "String", True)
        attr.Set.assert_called_once_with("base_link")

    def test_skips_missing_prim_with_warning(
        self, fake_pxr: types.SimpleNamespace, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from marslab.ros2_bridge.tf_nameoverrides import apply_nameoverride

        prim = MagicMock()
        prim.IsValid.return_value = False
        stage = MagicMock()
        stage.GetPrimAtPath.return_value = prim

        ok = apply_nameoverride(stage, "/World/Bogus", "base_link")

        assert ok is False
        prim.CreateAttribute.assert_not_called()
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "/World/Bogus" in captured.err


class TestCreateOdomAnchor:
    def test_defines_xform_and_sets_translation(self, fake_pxr: types.SimpleNamespace) -> None:
        from marslab.ros2_bridge.tf_nameoverrides import (
            DEFAULT_ODOM_ANCHOR_PATH,
            create_odom_anchor,
        )

        stage = MagicMock(name="stage")
        ok = create_odom_anchor(stage, DEFAULT_ODOM_ANCHOR_PATH, (1.0, 2.0, 3.0))

        assert ok is True
        # UsdGeom.Xform.Define was called with the requested path.
        assert fake_pxr.xform_define_calls == [(stage, DEFAULT_ODOM_ANCHOR_PATH)]
        # The translation op was invoked on a new Vec3d.
        translate_op = fake_pxr.xform_handle.AddTranslateOp.return_value
        translate_op.Set.assert_called_once_with(("Vec3d", 1.0, 2.0, 3.0))

    def test_default_anchor_path_is_world_odom_anchor(self) -> None:
        from marslab.ros2_bridge.tf_nameoverrides import DEFAULT_ODOM_ANCHOR_PATH

        # The anchor path is referenced from both ``rover.py`` and
        # ``run_stage4.py``; pin it so a rename in one place breaks the
        # test instead of silently creating two anchors at different
        # paths.
        assert DEFAULT_ODOM_ANCHOR_PATH == "/World/odom_anchor"

    def test_writes_nameoverride_attribute_on_anchor(self, fake_pxr: types.SimpleNamespace) -> None:
        from marslab.ros2_bridge.tf_nameoverrides import create_odom_anchor

        stage = MagicMock(name="stage")
        create_odom_anchor(stage, "/World/odom_anchor", (0.0, 0.0, 0.0))

        anchor_prim = fake_pxr.xform_handle.GetPrim.return_value
        anchor_prim.CreateAttribute.assert_called_once_with("isaac:nameOverride", "String", True)
        anchor_prim.CreateAttribute.return_value.Set.assert_called_once_with("odom")
