from __future__ import annotations

import numpy as np
import pytest
from marslab_scene.terrain.hirise.appearance.finalize import EnhancedTexture
from marslab_scene.terrain.hirise.appearance.material import prepared_texture_from_enhanced
from marslab_scene.terrain.hirise.config import InputConfig, PipelineConfig, UsdConfig
from marslab_scene.terrain.hirise.mesh.heightfield import build_heightfield_mesh
from marslab_scene.usd.terrain import write_terrain_stage
from pxr import Usd, UsdShade

pytestmark = [pytest.mark.standalone_usd, pytest.mark.legacy_parity]


def test_enhanced_texture_uses_relative_usda_asset_path(tmp_path) -> None:
    input_path = tmp_path / "synthetic.tif"
    input_path.write_bytes(b"unused")
    config = PipelineConfig(
        input=InputConfig(path=input_path),
        usd=UsdConfig(output_dir=tmp_path, terrain_scene_name="terrain_scene.usda"),
    )
    texture_path = tmp_path / "textures" / "terrain_albedo_mars_enhanced.png"
    texture_path.parent.mkdir()
    texture_path.write_bytes(b"synthetic png placeholder")
    enhanced = EnhancedTexture(
        image=np.zeros((2, 2, 3), dtype=np.uint8),
        output_path=texture_path,
        width=2,
        height=2,
        sha256="0" * 64,
        parameters={},
    )
    prepared = prepared_texture_from_enhanced(enhanced, config.texture)
    mesh = build_heightfield_mesh(np.zeros((2, 2), dtype=np.float64), 1.0, 1.0)

    scene_path = write_terrain_stage(mesh, mesh, config, texture=prepared)

    usda = scene_path.read_text(encoding="utf-8")
    assert "textures/terrain_albedo_mars_enhanced.png" in usda
    assert str(tmp_path) not in usda


def test_enhanced_texture_material_binds_visual_mesh_only(tmp_path) -> None:
    input_path = tmp_path / "synthetic.tif"
    input_path.write_bytes(b"unused")
    config = PipelineConfig(
        input=InputConfig(path=input_path),
        usd=UsdConfig(output_dir=tmp_path, terrain_scene_name="terrain_scene.usda"),
    )
    texture_path = tmp_path / "textures" / "terrain_albedo_mars_enhanced.png"
    texture_path.parent.mkdir()
    texture_path.write_bytes(b"synthetic png placeholder")
    prepared = prepared_texture_from_enhanced(
        EnhancedTexture(
            image=np.zeros((2, 2, 3), dtype=np.uint8),
            output_path=texture_path,
            width=2,
            height=2,
            sha256="0" * 64,
            parameters={},
        ),
        config.texture,
    )
    mesh = build_heightfield_mesh(np.zeros((2, 2), dtype=np.float64), 1.0, 1.0)

    scene_path = write_terrain_stage(mesh, mesh, config, texture=prepared)
    stage = Usd.Stage.Open(str(scene_path))
    assert stage is not None
    visual = stage.GetPrimAtPath("/World/MarsTerrain/VisualMesh")
    collision = stage.GetPrimAtPath("/World/MarsTerrain/CollisionMesh")

    assert visual.HasAPI(UsdShade.MaterialBindingAPI)
    collision_binding = UsdShade.MaterialBindingAPI(collision).GetDirectBinding().GetMaterialPath()
    assert collision_binding.pathString != "/World/Looks/MarsTerrain_Material"
