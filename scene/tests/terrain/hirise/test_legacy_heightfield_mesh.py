from pathlib import Path

import numpy as np
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]

from marslab_scene.terrain.hirise.mesh.heightfield import build_faces, build_heightfield_mesh
from marslab_scene.terrain.hirise.mesh.obj_export import write_obj
from marslab_scene.terrain.hirise.mesh.validate import MeshValidationError, validate_normals_up


def test_vertex_and_face_count() -> None:
    z = np.zeros((3, 4), dtype=np.float64)

    mesh = build_heightfield_mesh(z, size_x_m=30.0, size_y_m=20.0)

    assert mesh.vertices.shape == (12, 3)
    assert mesh.faces.shape == (12, 3)


def test_flat_heightfield_normals_are_up() -> None:
    z = np.zeros((3, 3), dtype=np.float64)

    mesh = build_heightfield_mesh(z, size_x_m=2.0, size_y_m=2.0)

    validate_normals_up(mesh)


def test_faces_use_documented_winding() -> None:
    faces = build_faces(height=2, width=2)

    np.testing.assert_array_equal(faces, np.array([[0, 2, 1], [1, 2, 3]]))


def test_no_nan_or_inf_vertices() -> None:
    z = np.array([[0.0, np.nan], [1.0, 2.0]])

    with pytest.raises(MeshValidationError, match="finite"):
        build_heightfield_mesh(z, size_x_m=1.0, size_y_m=1.0)


def test_mesh_bounds_match_crop_and_elevation() -> None:
    z = np.array([[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]])

    mesh = build_heightfield_mesh(z, size_x_m=20.0, size_y_m=10.0)

    assert mesh.bounds == (-10.0, 10.0, -5.0, 5.0, 0.0, 5.0)


def test_vertices_follow_rep103_local_enu() -> None:
    z = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])

    mesh = build_heightfield_mesh(z, size_x_m=20.0, size_y_m=10.0)

    np.testing.assert_allclose(mesh.vertices[0], np.array([-10.0, 5.0, 1.0]))
    np.testing.assert_allclose(mesh.vertices[2], np.array([10.0, 5.0, 3.0]))
    np.testing.assert_allclose(mesh.vertices[3], np.array([-10.0, -5.0, 4.0]))


def test_validate_normals_up_rejects_downward_winding() -> None:
    z = np.zeros((2, 2), dtype=np.float64)
    mesh = build_heightfield_mesh(z, size_x_m=1.0, size_y_m=1.0)
    flipped = type(mesh)(
        vertices=mesh.vertices,
        faces=mesh.faces[:, ::-1],
        bounds=mesh.bounds,
    )

    with pytest.raises(MeshValidationError, match="positive Z"):
        validate_normals_up(flipped)


def test_write_obj(tmp_path: Path) -> None:
    z = np.zeros((2, 2), dtype=np.float64)
    mesh = build_heightfield_mesh(z, size_x_m=1.0, size_y_m=1.0)
    path = tmp_path / "terrain.obj"

    write_obj(mesh, path)

    text = path.read_text(encoding="utf-8")
    assert "v -0.5 0.5 0.0\n" in text
    assert "f 1 3 2\n" in text
