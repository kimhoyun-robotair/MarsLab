from pathlib import Path

import numpy as np
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]
from marslab_scene.terrain.hirise.config import (
    ExportConfig,
    InputConfig,
    PhysicsConfig,
    PipelineConfig,
    UsdConfig,
)
from marslab_scene.terrain.hirise.mesh.heightfield import build_heightfield_mesh
from marslab_scene.usd.terrain import write_terrain_stage
from pxr import Usd, UsdGeom, UsdPhysics


def _config(tmp_path: Path) -> PipelineConfig:
    input_path = tmp_path / "synthetic.tif"
    input_path.write_bytes(b"not used by USD tests")
    return PipelineConfig(
        input=InputConfig(path=input_path),
        usd=UsdConfig(output_dir=tmp_path, terrain_scene_name="terrain_scene.usda"),
        physics=PhysicsConfig(gravity_mps2=3.711),
        export=ExportConfig(),
    )


def _write_stage(tmp_path: Path) -> Usd.Stage:
    z = np.zeros((2, 2), dtype=np.float64)
    visual = build_heightfield_mesh(z, size_x_m=1.0, size_y_m=1.0)
    collision = build_heightfield_mesh(z, size_x_m=1.0, size_y_m=1.0)
    scene_path = write_terrain_stage(visual, collision, _config(tmp_path))
    stage = Usd.Stage.Open(str(scene_path))
    assert stage is not None
    return stage


def test_usd_stage_has_world_default_prim(tmp_path: Path) -> None:
    stage = _write_stage(tmp_path)

    default_prim = stage.GetDefaultPrim()

    assert default_prim.GetPath().pathString == "/World"


def test_usd_stage_is_z_up(tmp_path: Path) -> None:
    stage = _write_stage(tmp_path)

    assert UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.z


def test_usd_stage_meters_per_unit_is_one(tmp_path: Path) -> None:
    stage = _write_stage(tmp_path)

    assert UsdGeom.GetStageMetersPerUnit(stage) == 1.0


def test_visual_and_collision_mesh_prims_exist(tmp_path: Path) -> None:
    stage = _write_stage(tmp_path)

    visual = UsdGeom.Mesh.Get(stage, "/World/MarsTerrain/VisualMesh")
    collision = UsdGeom.Mesh.Get(stage, "/World/MarsTerrain/CollisionMesh")

    assert visual
    assert collision
    assert visual.GetPointsAttr().Get()
    assert collision.GetFaceVertexCountsAttr().Get() == [3, 3]
    assert collision.GetVisibilityAttr().Get() == UsdGeom.Tokens.invisible


def test_collision_mesh_has_collision_api(tmp_path: Path) -> None:
    stage = _write_stage(tmp_path)
    prim = stage.GetPrimAtPath("/World/MarsTerrain/CollisionMesh")

    assert "PhysicsCollisionAPI" in prim.GetAppliedSchemas()
    assert "PhysicsMeshCollisionAPI" in prim.GetAppliedSchemas()
    assert UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get() is True
    assert UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get() == "none"


def test_physics_scene_has_mars_gravity(tmp_path: Path) -> None:
    stage = _write_stage(tmp_path)
    scene = UsdPhysics.Scene.Get(stage, "/World/PhysicsScene")

    assert scene
    assert scene.GetGravityDirectionAttr().Get() == (0.0, 0.0, -1.0)
    assert scene.GetGravityMagnitudeAttr().Get() == pytest.approx(3.711)


def test_terrain_has_no_rigidbody_api(tmp_path: Path) -> None:
    stage = _write_stage(tmp_path)
    prim = stage.GetPrimAtPath("/World/MarsTerrain/CollisionMesh")

    assert "PhysicsRigidBodyAPI" not in prim.GetAppliedSchemas()


def test_collision_mesh_has_bound_physics_material(tmp_path: Path) -> None:
    stage = _write_stage(tmp_path)
    material_prim = stage.GetPrimAtPath("/World/MarsTerrain/PhysicsMaterial")

    assert "PhysicsMaterialAPI" in material_prim.GetAppliedSchemas()
    material_api = UsdPhysics.MaterialAPI(material_prim)
    assert material_api.GetStaticFrictionAttr().Get() == 1.0
    assert material_api.GetDynamicFrictionAttr().Get() == pytest.approx(0.8)
    assert material_api.GetRestitutionAttr().Get() == 0.0
