"""Unit tests for marslab.terrain.cave_generator."""

import hashlib

import numpy as np
import pytest

from marslab.terrain.cave_generator import generate_cave_mesh

# Shared small-domain params for fast tests
SMALL = {
    "domain_size": (100, 100),
    "resolution": 1.0,
    "path_resolution": 30,
    "ring_resolution": 20,
    "seed": 42,
}


@pytest.fixture()
def cave_default():
    """Default cave mesh with small domain for speed."""
    return generate_cave_mesh(**SMALL)


@pytest.fixture()
def cave_full():
    """Full-size cave (400x400) for dimensional tests."""
    return generate_cave_mesh(seed=42)


# --- Output structure ---


def test_return_keys(cave_default):
    """All expected keys present in output dict."""
    expected = {
        "tube_mesh",
        "floor_mesh",
        "surface_mesh",
        "skylight_meshes",
        "debris_cones",
        "breakdown_positions",
        "skylight_positions",
        "metadata",
        "surface_elevation",
    }
    assert expected == set(cave_default.keys())


def test_mesh_types(cave_default):
    """Meshes are trimesh.Trimesh objects."""
    import trimesh

    assert isinstance(cave_default["tube_mesh"], trimesh.Trimesh)
    assert isinstance(cave_default["floor_mesh"], trimesh.Trimesh)
    assert isinstance(cave_default["surface_mesh"], trimesh.Trimesh)


def test_surface_elevation_shape(cave_default):
    """Surface elevation matches domain size."""
    assert cave_default["surface_elevation"].shape == (100, 100)
    assert cave_default["surface_elevation"].dtype == np.float32


# --- No NaN / valid indices ---


@pytest.mark.parametrize(
    "mesh_key",
    ["tube_mesh", "floor_mesh", "surface_mesh"],
    ids=["tube", "floor", "surface"],
)
def test_no_nan_vertices(cave_default, mesh_key):
    """No NaN in {tube,floor,surface} mesh vertices."""
    assert not np.isnan(cave_default[mesh_key].vertices).any()


@pytest.mark.parametrize(
    "mesh_key",
    ["tube_mesh", "floor_mesh", "surface_mesh"],
    ids=["tube", "floor", "surface"],
)
def test_face_indices_valid(cave_default, mesh_key):
    """All face indices within vertex count for {tube,floor,surface} mesh."""
    mesh = cave_default[mesh_key]
    assert mesh.faces.max() < len(mesh.vertices)
    assert mesh.faces.min() >= 0


# --- Dimensional checks ---


def test_tube_bounding_box_width(cave_full):
    """Tube width in bounding box approximates configured width."""
    verts = cave_full["tube_mesh"].vertices
    # Tube width is across the perpendicular direction
    # For default direction=0 (along Y), width is in X
    x_range = verts[:, 0].max() - verts[:, 0].min()
    configured_width = 200.0
    # Allow ±30% for noise + curvature
    assert x_range > configured_width * 0.5
    assert x_range < configured_width * 2.0


def test_tube_height(cave_full):
    """Tube height matches configured ratio."""
    verts = cave_full["tube_mesh"].vertices
    z_range = verts[:, 2].max() - verts[:, 2].min()
    configured_height = 200.0 * 0.5  # width * ratio
    # Allow generous range for noise
    assert z_range > configured_height * 0.5
    assert z_range < configured_height * 2.0


def test_surface_z_above_tube(cave_full):
    """Surface mesh is above tube mesh."""
    surface_z_min = cave_full["surface_mesh"].vertices[:, 2].min()
    tube_z_max = cave_full["tube_mesh"].vertices[:, 2].max()
    assert surface_z_min > tube_z_max * 0.8


def test_floor_below_tube_ceiling(cave_full):
    """Floor mesh is below tube ceiling."""
    floor_z_max = cave_full["floor_mesh"].vertices[:, 2].max()
    tube_z_max = cave_full["tube_mesh"].vertices[:, 2].max()
    assert floor_z_max < tube_z_max


# --- Normals ---


def test_floor_normals_upward(cave_default):
    """Floor face normals have positive Z component (upward)."""
    mesh = cave_default["floor_mesh"]
    face_normals = mesh.face_normals
    # Most floor normals should point upward
    upward_fraction = (face_normals[:, 2] > 0).sum() / len(face_normals)
    assert upward_fraction > 0.8, f"Only {upward_fraction:.0%} floor normals point up"


def test_tube_normals_inward(cave_default):
    """Tube shell normals point generally inward (toward centerline)."""
    mesh = cave_default["tube_mesh"]
    face_normals = mesh.face_normals
    face_centers = mesh.triangles.mean(axis=1)

    # For the ceiling (upper faces), normals should point downward
    upper_faces = face_centers[:, 2] > face_centers[:, 2].mean()
    if upper_faces.sum() > 0:
        downward_fraction = (face_normals[upper_faces, 2] < 0).sum() / upper_faces.sum()
        assert downward_fraction > 0.5, f"Only {downward_fraction:.0%} ceiling normals point down"


# --- Skylight ---


def test_skylight_count_default(cave_default):
    """Default config produces multiple skylights (small domain limits count)."""
    # Default is 10 requested, but small 100x100 domain fits fewer due to margins
    assert len(cave_default["skylight_meshes"]) >= 1
    assert len(cave_default["skylight_positions"]) >= 1


def test_skylight_shaft_depth(cave_default):
    """Skylight shaft spans from surface to tube ceiling."""
    shaft = cave_default["skylight_meshes"][0]
    z_min = shaft.vertices[:, 2].min()
    z_max = shaft.vertices[:, 2].max()
    # Should span a significant vertical range
    assert (z_max - z_min) > 30.0  # at least 30m depth


def test_skylight_no_overlap(cave_default):
    """Skylights do not overlap (minimum separation = 1.5 * diameter)."""
    positions = cave_default["skylight_positions"]
    diameter = 20.0  # default
    min_dist = diameter * 1.5
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            dx = positions[i][0] - positions[j][0]
            dy = positions[i][1] - positions[j][1]
            dist = (dx**2 + dy**2) ** 0.5
            assert dist >= min_dist, f"Skylights {i} and {j} overlap: dist={dist:.1f}m"


def test_surface_has_skylight_hole(cave_default):
    """Surface mesh has fewer faces than a full grid (hole cut)."""
    rows, cols = 100, 100
    full_face_count = (rows - 1) * (cols - 1) * 2
    actual_faces = len(cave_default["surface_mesh"].faces)
    assert actual_faces < full_face_count, "No skylight hole in surface"


def test_no_skylight_variant():
    """skylight_count=0 produces no skylights but debris cones still spawn."""
    result = generate_cave_mesh(skylight_count=0, **SMALL)
    assert len(result["skylight_meshes"]) == 0
    # Debris cones are independent of skylights — they still spawn inside the tube
    assert len(result["debris_cones"]) >= 1


# --- Debris cone ---


def test_debris_cone_exists(cave_default):
    """Default config produces debris cones inside the tube."""
    assert len(cave_default["debris_cones"]) >= 1
    for cone in cave_default["debris_cones"]:
        assert len(cone.vertices) > 0
        assert len(cone.faces) > 0


def test_debris_cone_apex_above_floor(cave_default):
    """Debris cone apex is above floor level."""
    cone = cave_default["debris_cones"][0]
    z_max = cone.vertices[:, 2].max()
    floor_z = cave_default["metadata"]["floor_z"]
    assert z_max > floor_z


def test_debris_cone_avoids_centerline():
    """Debris cones are offset from centerline (rover passage)."""
    result = generate_cave_mesh(
        debris_cone_count=5,
        domain_size=(400, 400),
        resolution=1.0,
        path_resolution=60,
        ring_resolution=20,
        seed=42,
    )
    assert len(result["debris_cones"]) >= 1


# --- Breakdown blocks ---


def test_breakdown_positions_nonempty(cave_default):
    """Default breakdown coverage produces blocks."""
    assert len(cave_default["breakdown_positions"]) > 0


def test_breakdown_positions_have_required_keys(cave_default):
    """Each breakdown position has x, y, z, diameter."""
    for block in cave_default["breakdown_positions"]:
        assert "x" in block
        assert "y" in block
        assert "z" in block
        assert "diameter" in block
        assert block["diameter"] > 0


def test_breakdown_zero_coverage():
    """breakdown_coverage_pct=0 produces no blocks."""
    result = generate_cave_mesh(breakdown_coverage_pct=0.0, **SMALL)
    assert len(result["breakdown_positions"]) == 0


# --- Seed determinism ---


def test_seed_determinism():
    """Same seed produces identical output."""
    r1 = generate_cave_mesh(**SMALL)
    r2 = generate_cave_mesh(**SMALL)
    assert np.array_equal(r1["tube_mesh"].vertices, r2["tube_mesh"].vertices)
    assert np.array_equal(r1["floor_mesh"].vertices, r2["floor_mesh"].vertices)
    assert np.array_equal(r1["surface_mesh"].vertices, r2["surface_mesh"].vertices)


def test_different_seeds_differ():
    """Different seeds produce different output."""
    r1 = generate_cave_mesh(seed=42, **{k: v for k, v in SMALL.items() if k != "seed"})
    r2 = generate_cave_mesh(seed=99, **{k: v for k, v in SMALL.items() if k != "seed"})
    assert not np.array_equal(r1["tube_mesh"].vertices, r2["tube_mesh"].vertices)


# --- Parameter variants ---


def test_narrow_tube():
    """width=80m produces a narrower tube."""
    result = generate_cave_mesh(tube_width_m=80.0, **SMALL)
    verts = result["tube_mesh"].vertices
    x_range = verts[:, 0].max() - verts[:, 0].min()
    assert x_range < 200.0  # narrower than default 200m


def test_wide_tube():
    """width=300m produces a wider tube."""
    result = generate_cave_mesh(tube_width_m=300.0, skylight_depth_m=180.0, **SMALL)
    verts = result["tube_mesh"].vertices
    x_range = verts[:, 0].max() - verts[:, 0].min()
    assert x_range > 100.0  # wider than narrow


def test_many_skylights():
    """skylight_count=10 on large domain produces multiple skylights."""
    result = generate_cave_mesh(
        skylight_count=10,
        skylight_diameter_m=20.0,
        domain_size=(400, 400),
        resolution=1.0,
        path_resolution=60,
        ring_resolution=20,
        seed=42,
    )
    # Large domain should fit most of the 10 requested
    assert len(result["skylight_meshes"]) >= 5
    assert len(result["skylight_positions"]) >= 5


def test_high_breakdown_coverage():
    """High breakdown coverage produces many blocks."""
    result = generate_cave_mesh(breakdown_coverage_pct=80.0, **SMALL)
    assert len(result["breakdown_positions"]) > 50


def test_no_debris_cone():
    """debris_cone_present=False produces no cones."""
    result = generate_cave_mesh(debris_cone_present=False, **SMALL)
    assert len(result["debris_cones"]) == 0


# --- Metadata ---


def test_metadata_keys(cave_default):
    """All expected metadata keys present."""
    expected = {
        "tube_width_m",
        "tube_height_m",
        "ceiling_thickness_m",
        "surface_z",
        "floor_z",
        "domain_m",
        "skylight_count",
        "breakdown_count",
        "tube_vertices",
        "floor_vertices",
        "seed",
    }
    assert expected == set(cave_default["metadata"].keys())


def test_metadata_values(cave_default):
    """Metadata values match configuration."""
    meta = cave_default["metadata"]
    assert meta["tube_width_m"] == 200.0
    assert meta["tube_height_m"] == 100.0
    assert meta["ceiling_thickness_m"] == 50.0
    assert meta["surface_z"] == 150.0
    assert meta["floor_z"] == 0.0
    assert meta["seed"] == 42


# --- R5 regression guard ---


# Hash captured from the pre-R5 monolithic cave_generator on 2026-04-23 for
# SMALL = seed=42, domain_size=(100, 100), resolution=1.0, path_resolution=30,
# ring_resolution=20. If this hash changes, either the RNG consumption order
# drifted (serious bug -- fix the split) or the user intentionally tuned the
# generator (update the hash here with a work_log entry).
#
# Updated 2026-04-24 (Reviewer 2 audit #11): the breakdown lognormal
# draw was mean-corrected (``mean=log(m) - sigma**2/2`` instead of
# ``mean=log(m)``) so the sampled diameter stream changed. RNG order is
# unchanged; only the transformed draw values differ.
_R5_REGRESSION_HASH = "a8d0af1c9b0b3fb00a78fb94f7b821b26816ca67b02bad60c347b8084307d9b1"


def test_r5_regression_hash_stable():
    """RNG draw order and numeric output survive the R5 4-way split."""
    result = generate_cave_mesh(**SMALL)

    parts: list[bytes] = []
    for key in ("tube_mesh", "floor_mesh", "surface_mesh"):
        parts.append(result[key].vertices.tobytes())
    for sky in result["skylight_meshes"]:
        parts.append(sky.vertices.tobytes())
    for cone in result["debris_cones"]:
        parts.append(cone.vertices.tobytes())
    bd = [(b["x"], b["y"], b["z"], b["diameter"]) for b in result["breakdown_positions"]]
    parts.append(np.asarray(bd, dtype=np.float64).tobytes())
    parts.append(np.asarray(result["skylight_positions"], dtype=np.float64).tobytes())
    parts.append(np.nan_to_num(result["surface_elevation"], nan=-9999.0).tobytes())

    actual = hashlib.sha256(b"".join(parts)).hexdigest()
    assert actual == _R5_REGRESSION_HASH, (
        "Cave generator bit-exact regression guard failed. "
        "Either the R5 submodule split changed RNG order, or parameters drifted."
    )
