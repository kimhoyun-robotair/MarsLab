"""Offline unit tests for marslab.terrain._pbr_helpers.

These tests stub out ``pxr`` so the module can be exercised without
Isaac Sim. The helper is a thin wrapper over OmniPBR setters and
``UsdShade.Shader.CreateInput`` calls; we verify the call counts and
filenames rather than actual USD state.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _stub_pxr(monkeypatch: pytest.MonkeyPatch):
    """Inject a minimal ``pxr.Sdf`` stub so the helper imports cleanly.

    The helper's only ``pxr`` use is:
        Sdf.ValueTypeNames.Asset / .Float
        Sdf.AssetPath(path)
    The stub returns sentinel objects that the mocked shader records
    via its ``CreateInput`` mock.
    """
    pxr_module = types.ModuleType("pxr")
    sdf_module = types.ModuleType("pxr.Sdf")

    class _ValueTypeNames:
        Asset = "Asset"
        Float = "Float"

    def _asset_path(path):
        return ("AssetPath", path)

    sdf_module.ValueTypeNames = _ValueTypeNames
    sdf_module.AssetPath = _asset_path
    pxr_module.Sdf = sdf_module

    monkeypatch.setitem(sys.modules, "pxr", pxr_module)
    monkeypatch.setitem(sys.modules, "pxr.Sdf", sdf_module)
    yield


def _make_material() -> MagicMock:
    """Build a duck-typed OmniPBR mock with shaders_list[0].CreateInput."""
    material = MagicMock()
    shader = MagicMock()
    # CreateInput(...) -> input mock with .Set(...)
    shader.CreateInput.return_value = MagicMock()
    material.shaders_list = [shader]
    return material


def _write_pngs(directory: Path, names: list[str]) -> None:
    for name in names:
        (directory / name).write_bytes(b"fake png bytes")


def test_empty_directory_no_calls(tmp_path: Path) -> None:
    """Empty texture dir => no shader_input or set_texture calls."""
    from marslab.terrain._pbr_helpers import apply_pbr_textures

    material = _make_material()
    apply_pbr_textures(material, str(tmp_path), project_uvw=True)

    assert material.set_texture.call_count == 0
    assert material.set_project_uvw.call_count == 0
    assert material.shaders_list[0].CreateInput.call_count == 0


def test_all_three_textures_present(tmp_path: Path) -> None:
    """All three PNGs => 3 shader inputs + 1 project_uvw call."""
    from marslab.terrain._pbr_helpers import apply_pbr_textures

    _write_pngs(tmp_path, ["albedo.png", "normal.png", "roughness.png"])
    material = _make_material()

    apply_pbr_textures(material, str(tmp_path), project_uvw=True)

    # albedo via wrapper
    assert material.set_texture.call_count == 1
    assert material.set_project_uvw.call_count == 1
    material.set_project_uvw.assert_called_once_with(True)

    # normal + roughness + roughness_influence => 3 CreateInput calls
    shader = material.shaders_list[0]
    assert shader.CreateInput.call_count == 3
    input_names = [call.args[0] for call in shader.CreateInput.call_args_list]
    assert "normalmap_texture" in input_names
    assert "reflectionroughness_texture" in input_names
    assert "reflection_roughness_texture_influence" in input_names


def test_missing_one_texture(tmp_path: Path) -> None:
    """Only 2 of 3 PNGs => only the present ones are wired."""
    from marslab.terrain._pbr_helpers import apply_pbr_textures

    # Skip the normal map.
    _write_pngs(tmp_path, ["albedo.png", "roughness.png"])
    material = _make_material()

    apply_pbr_textures(material, str(tmp_path), project_uvw=True)

    # Albedo wrapper still fires once.
    assert material.set_texture.call_count == 1
    assert material.set_project_uvw.call_count == 1

    # Roughness fires roughness_texture + roughness_influence; normal
    # is skipped. Total CreateInput = 2.
    shader = material.shaders_list[0]
    assert shader.CreateInput.call_count == 2
    input_names = [call.args[0] for call in shader.CreateInput.call_args_list]
    assert "normalmap_texture" not in input_names
    assert "reflectionroughness_texture" in input_names
    assert "reflection_roughness_texture_influence" in input_names


def test_project_uvw_false(tmp_path: Path) -> None:
    """project_uvw=False => set_project_uvw(False), shader inputs unchanged."""
    from marslab.terrain._pbr_helpers import apply_pbr_textures

    _write_pngs(tmp_path, ["albedo.png", "normal.png", "roughness.png"])
    material = _make_material()

    apply_pbr_textures(material, str(tmp_path), project_uvw=False)

    # Albedo path still wires set_texture and set_project_uvw, but with False.
    assert material.set_texture.call_count == 1
    assert material.set_project_uvw.call_count == 1
    material.set_project_uvw.assert_called_once_with(False)

    # Shader inputs still fire 3 times (normal + roughness + roughness_influence).
    shader = material.shaders_list[0]
    assert shader.CreateInput.call_count == 3


def test_only_normal_present(tmp_path: Path) -> None:
    """Only normal.png => 1 shader input, no albedo wrapper, no project_uvw."""
    from marslab.terrain._pbr_helpers import apply_pbr_textures

    _write_pngs(tmp_path, ["normal.png"])
    material = _make_material()

    apply_pbr_textures(material, str(tmp_path), project_uvw=True)

    assert material.set_texture.call_count == 0
    assert material.set_project_uvw.call_count == 0

    shader = material.shaders_list[0]
    assert shader.CreateInput.call_count == 1
    assert shader.CreateInput.call_args_list[0].args[0] == "normalmap_texture"
