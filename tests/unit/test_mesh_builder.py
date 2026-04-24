"""Unit tests for marslab/terrain/mesh_builder.py Layer 1 (offline)."""

import inspect

import numpy as np
import pytest

from marslab.terrain.mesh_builder import compute_mesh_arrays, terrain_z_at

# ---------------------------------------------------------------------------
# Winding / Normal tests — THE critical tests
# ---------------------------------------------------------------------------


def _compute_face_normal(points: np.ndarray, i0: int, i1: int, i2: int) -> np.ndarray:
    """Cross product of triangle edges to get face normal."""
    v0 = points[i0]
    v1 = points[i1]
    v2 = points[i2]
    edge1 = v1 - v0
    edge2 = v2 - v0
    return np.cross(edge1, edge2)


def test_all_face_normals_positive_z_flat():
    """On a flat surface, every triangle face normal must point +Z.

    This is THE critical test. If this fails, PhysX collision normals
    are inverted and objects fall through terrain.
    """
    elevation = np.zeros((4, 4), dtype=np.float32)
    result = compute_mesh_arrays(elevation, resolution=1.0)
    points = result["points"]
    indices = result["face_indices"]

    for i in range(0, len(indices), 3):
        normal = _compute_face_normal(points, indices[i], indices[i + 1], indices[i + 2])
        assert normal[2] > 0, (
            f"Face {i // 3} has non-positive Z normal: {normal}. "
            f"Winding is wrong — PhysX collision will fail."
        )


def test_all_face_normals_positive_z_slope():
    """On a tilted surface, face normals should still have positive Z."""
    rows, cols = 8, 8
    elevation = np.zeros((rows, cols), dtype=np.float32)
    # Create a ramp: z increases with column index
    for c in range(cols):
        elevation[:, c] = c * 2.0

    result = compute_mesh_arrays(elevation, resolution=1.0)
    points = result["points"]
    indices = result["face_indices"]

    for i in range(0, len(indices), 3):
        normal = _compute_face_normal(points, indices[i], indices[i + 1], indices[i + 2])
        assert normal[2] > 0, f"Face {i // 3} has non-positive Z normal on slope: {normal}"


def test_all_face_normals_positive_z_noisy():
    """Random noisy terrain: vast majority of face normals must be +Z."""
    rng = np.random.default_rng(42)
    elevation = rng.standard_normal((32, 32)).astype(np.float32) * 5.0
    result = compute_mesh_arrays(elevation, resolution=1.0)
    points = result["points"]
    indices = result["face_indices"]

    n_faces = len(indices) // 3
    positive_count = 0
    for i in range(0, len(indices), 3):
        normal = _compute_face_normal(points, indices[i], indices[i + 1], indices[i + 2])
        if normal[2] > 0:
            positive_count += 1

    ratio = positive_count / n_faces
    assert ratio > 0.99, f"Only {ratio:.2%} of faces have +Z normals on noisy terrain"


def test_source_text_winding_guard():
    """Guard against winding regression in source code.

    Checks that mesh_builder.py source contains the correct winding
    pattern and NOT the legacy buggy pattern.
    """
    source = inspect.getsource(compute_mesh_arrays)
    # Correct winding markers (CCW for +Z)
    assert "i00" in source
    assert "i01" in source
    assert "i10" in source
    # The face_indices assignment order must be i00, i01, i10 (not i00, i10, i01)
    # We check that the comment or assignment reflects this
    assert "Triangle 1: i00, i01, i10" in source or "face_indices[0::6] = i00" in source


# ---------------------------------------------------------------------------
# Elevation normalization
# ---------------------------------------------------------------------------


def test_elevation_normalized_to_zero_min():
    """After normalization, minimum elevation should be approximately 0."""
    elevation = np.array([[10.0, 20.0], [15.0, 25.0]], dtype=np.float32)
    result = compute_mesh_arrays(elevation, resolution=1.0)
    normed = result["normalized_elevation"]
    assert abs(np.min(normed)) < 1e-5


def test_elevation_absolute_mars_datum_normalized():
    """Absolute Mars datum (~-2518 m) must be normalized to near-zero."""
    elevation = np.full((4, 4), -2518.0, dtype=np.float32)
    elevation[0, 0] = -2520.0  # range = 2m
    result = compute_mesh_arrays(elevation, resolution=1.0)
    normed = result["normalized_elevation"]
    assert np.min(normed) == pytest.approx(0.0, abs=1e-5)
    assert np.max(normed) == pytest.approx(2.0, abs=1e-5)


def test_nan_replaced_with_zero():
    """NaN values in elevation should become 0 after normalization."""
    elevation = np.array([[1.0, np.nan], [2.0, 3.0]], dtype=np.float32)
    result = compute_mesh_arrays(elevation, resolution=1.0)
    normed = result["normalized_elevation"]
    assert not np.any(np.isnan(normed))


# ---------------------------------------------------------------------------
# Geometry shape checks
# ---------------------------------------------------------------------------


def test_vertex_count_matches_grid():
    """Number of vertices should equal rows * cols."""
    rows, cols = 5, 7
    elevation = np.zeros((rows, cols), dtype=np.float32)
    result = compute_mesh_arrays(elevation, resolution=1.0)
    assert result["points"].shape == (rows * cols, 3)


def test_face_count_matches_grid():
    """Number of triangles should be 2 * (rows-1) * (cols-1)."""
    rows, cols = 5, 7
    elevation = np.zeros((rows, cols), dtype=np.float32)
    result = compute_mesh_arrays(elevation, resolution=1.0)
    expected_faces = 2 * (rows - 1) * (cols - 1)
    assert len(result["face_indices"]) == expected_faces * 3
    assert len(result["face_counts"]) == expected_faces
    assert all(c == 3 for c in result["face_counts"])


def test_minimal_2x2_grid():
    """Smallest valid grid: 2x2 produces 2 triangles."""
    elevation = np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32)
    result = compute_mesh_arrays(elevation, resolution=1.0)
    assert result["points"].shape == (4, 3)
    assert len(result["face_indices"]) == 6  # 2 triangles * 3 indices
    assert len(result["face_counts"]) == 2


def test_resolution_scales_vertex_positions():
    """Vertex positions should scale with resolution."""
    elevation = np.zeros((3, 3), dtype=np.float32)
    result = compute_mesh_arrays(elevation, resolution=2.5)
    points = result["points"]
    # Bottom-right vertex should be at (2*2.5, 2*2.5, 0)
    max_x = np.max(points[:, 0])
    max_y = np.max(points[:, 1])
    assert max_x == pytest.approx(5.0)
    assert max_y == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Normals and UVs
# ---------------------------------------------------------------------------


def test_normals_unit_length():
    """All vertex normals should be approximately unit length."""
    elevation = np.random.default_rng(0).standard_normal((8, 8)).astype(np.float32)
    result = compute_mesh_arrays(elevation, resolution=1.0)
    normals = result["normals"]
    lengths = np.linalg.norm(normals, axis=1)
    assert np.allclose(lengths, 1.0, atol=1e-4)


def test_flat_terrain_normals_all_up():
    """On flat terrain, all vertex normals should be approximately (0, 0, 1)."""
    elevation = np.zeros((4, 4), dtype=np.float32)
    result = compute_mesh_arrays(elevation, resolution=1.0)
    normals = result["normals"]
    expected = np.array([0.0, 0.0, 1.0])
    for i, n in enumerate(normals):
        assert np.allclose(n, expected, atol=1e-4), f"Normal {i}: {n} != {expected}"


def test_uv_range_within_bounds():
    """UV coordinates should be in [0, uv_scale]."""
    elevation = np.zeros((4, 4), dtype=np.float32)
    uv_scale = 2.0
    result = compute_mesh_arrays(elevation, resolution=1.0, uv_scale=uv_scale)
    uvs = result["uvs"]
    assert np.min(uvs) >= 0.0
    assert np.max(uvs) <= uv_scale + 1e-6


# ---------------------------------------------------------------------------
# Dtypes
# ---------------------------------------------------------------------------


def test_output_dtypes_float32():
    """Points, normals, UVs should all be float32."""
    elevation = np.zeros((3, 3), dtype=np.float32)
    result = compute_mesh_arrays(elevation, resolution=1.0)
    assert result["points"].dtype == np.float32
    assert result["normals"].dtype == np.float32
    assert result["uvs"].dtype == np.float32
    assert result["normalized_elevation"].dtype == np.float32


# ---------------------------------------------------------------------------
# Return dict keys
# ---------------------------------------------------------------------------


def test_compute_mesh_arrays_returns_expected_keys():
    """compute_mesh_arrays() must return all required keys."""
    elevation = np.zeros((3, 3), dtype=np.float32)
    result = compute_mesh_arrays(elevation, resolution=1.0)
    expected_keys = {
        "points",
        "normals",
        "face_indices",
        "face_counts",
        "uvs",
        "normalized_elevation",
    }
    assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_1x1_grid_raises():
    """A 1x1 grid cannot form triangles."""
    elevation = np.array([[5.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="at least 2x2"):
        compute_mesh_arrays(elevation, resolution=1.0)


def test_1d_input_raises():
    """1D input must be rejected."""
    with pytest.raises(ValueError, match="2D"):
        compute_mesh_arrays(np.array([1.0, 2.0]), resolution=1.0)


def test_zero_resolution_raises():
    """Zero resolution must be rejected."""
    elevation = np.zeros((3, 3), dtype=np.float32)
    with pytest.raises(ValueError, match="resolution"):
        compute_mesh_arrays(elevation, resolution=0.0)


def test_negative_resolution_raises():
    """Negative resolution must be rejected."""
    elevation = np.zeros((3, 3), dtype=np.float32)
    with pytest.raises(ValueError, match="resolution"):
        compute_mesh_arrays(elevation, resolution=-1.0)


# ---------------------------------------------------------------------------
# terrain_z_at() tests
# ---------------------------------------------------------------------------


def test_terrain_z_at_flat():
    """On flat terrain, z should be the flat value everywhere."""
    elevation = np.full((4, 4), 5.0, dtype=np.float32)
    z = terrain_z_at(elevation, resolution=1.0, x=1.5, y=1.5)
    assert z == pytest.approx(5.0, abs=1e-4)


def test_terrain_z_at_grid_point_exact():
    """At exact grid points, bilinear interpolation should match."""
    elevation = np.array([[0.0, 10.0], [20.0, 30.0]], dtype=np.float32)
    assert terrain_z_at(elevation, 1.0, 0.0, 0.0) == pytest.approx(0.0)
    assert terrain_z_at(elevation, 1.0, 1.0, 0.0) == pytest.approx(10.0)
    assert terrain_z_at(elevation, 1.0, 0.0, 1.0) == pytest.approx(20.0)
    assert terrain_z_at(elevation, 1.0, 1.0, 1.0) == pytest.approx(30.0)


def test_terrain_z_at_midpoint():
    """Midpoint of a 2x2 grid should be the average of all 4 corners."""
    elevation = np.array([[0.0, 10.0], [20.0, 30.0]], dtype=np.float32)
    z = terrain_z_at(elevation, 1.0, 0.5, 0.5)
    expected = (0.0 + 10.0 + 20.0 + 30.0) / 4.0
    assert z == pytest.approx(expected, abs=1e-4)


def test_terrain_z_at_clamp_outside():
    """Coordinates outside terrain bounds should be clamped to edge."""
    elevation = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    # x=-10 should clamp to x=0
    z_neg = terrain_z_at(elevation, 1.0, -10.0, 0.0)
    z_zero = terrain_z_at(elevation, 1.0, 0.0, 0.0)
    assert z_neg == pytest.approx(z_zero)

    # x=100 should clamp to x=1.0 (cols-1)
    z_big = terrain_z_at(elevation, 1.0, 100.0, 0.0)
    z_edge = terrain_z_at(elevation, 1.0, 1.0, 0.0)
    assert z_big == pytest.approx(z_edge)


def test_terrain_z_at_with_resolution():
    """Resolution should scale grid coordinates correctly."""
    elevation = np.array([[0.0, 10.0], [20.0, 30.0]], dtype=np.float32)
    # With resolution=2.0, column 1 is at x=2.0
    z = terrain_z_at(elevation, 2.0, 2.0, 0.0)
    assert z == pytest.approx(10.0, abs=1e-4)
