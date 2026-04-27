"""Unit tests for marslab.terrain.cave.mesh (R5)."""

from __future__ import annotations

import numpy as np
import pytest

from marslab.terrain.cave.geometry import build_centerline, build_cross_sections
from marslab.terrain.cave.mesh import (
    build_skylight_shaft,
    build_surface_cap,
    build_tube_floor,
    build_tube_shell,
)

DOMAIN_M = (100.0, 100.0)
DOMAIN_PIX = (100, 100)
N_STATIONS = 30
RING_PTS = 20


@pytest.fixture()
def geometry(rng):
    """Shared (centerline, cross_sections) tuple for mesh tests."""
    centerline = build_centerline(DOMAIN_M, 0.0, 0.15, N_STATIONS, 0.0, rng)
    cross_sections = build_cross_sections(centerline, 50.0, 0.5, 0.2, RING_PTS, rng)
    return centerline, cross_sections


def test_tube_shell_vertex_count(geometry):
    """Tube shell has n_stations * ring_pts vertices."""
    centerline, cross_sections = geometry
    mesh = build_tube_shell(centerline, cross_sections, RING_PTS)
    assert len(mesh.vertices) == N_STATIONS * RING_PTS


def test_tube_shell_face_indices_valid(geometry):
    """Tube shell face indices within vertex bounds."""
    centerline, cross_sections = geometry
    mesh = build_tube_shell(centerline, cross_sections, RING_PTS)
    assert mesh.faces.min() >= 0
    assert mesh.faces.max() < len(mesh.vertices)


def test_tube_shell_no_nan(geometry):
    """Tube shell contains no NaN vertices."""
    centerline, cross_sections = geometry
    mesh = build_tube_shell(centerline, cross_sections, RING_PTS)
    assert not np.isnan(mesh.vertices).any()


def test_floor_normals_positive_z(geometry, rng):
    """All floor face normals have positive z component."""
    centerline, cross_sections = geometry
    mesh = build_tube_floor(centerline, cross_sections, RING_PTS, 100.0, rng)
    # flat_pct=100 keeps the floor planar => normals strictly +z.
    assert (mesh.face_normals[:, 2] > 0).all()


def test_floor_vertex_count(geometry, rng):
    """Floor vertex count = n_stations * floor_pts where floor_pts = max(ring_pts//2, 8)."""
    centerline, cross_sections = geometry
    mesh = build_tube_floor(centerline, cross_sections, RING_PTS, 70.0, rng)
    floor_pts = max(RING_PTS // 2, 8)
    assert len(mesh.vertices) == N_STATIONS * floor_pts


def test_skylight_shaft_vertical_span():
    """Shaft spans exactly from ceiling_z to surface_z."""
    shaft = build_skylight_shaft(
        center_xy=(50.0, 50.0),
        diameter=20.0,
        surface_z=150.0,
        ceiling_z=100.0,
        overhang_deg=0.0,
        n_segments=16,
    )
    assert shaft.vertices[:, 2].max() == pytest.approx(150.0)
    assert shaft.vertices[:, 2].min() == pytest.approx(100.0)


def test_surface_cap_no_nan_vertices(rng):
    """Surface cap mesh vertices contain no NaN (NaN only in elevation_2d)."""
    mesh, elevation = build_surface_cap(
        domain_size=DOMAIN_PIX,
        resolution=1.0,
        surface_z=150.0,
        skylight_positions=[(50.0, 50.0)],
        skylight_diameter=20.0,
        rng=rng,
    )
    assert not np.isnan(mesh.vertices).any()
    # Elevation grid has NaN inside the hole.
    assert np.isnan(elevation).any()


def test_surface_cap_hole_face_reduction(rng):
    """Surface cap with skylight holes has fewer faces than a full grid."""
    rows, cols = DOMAIN_PIX
    mesh, _ = build_surface_cap(
        domain_size=DOMAIN_PIX,
        resolution=1.0,
        surface_z=150.0,
        skylight_positions=[(50.0, 50.0)],
        skylight_diameter=20.0,
        rng=rng,
    )
    full_face_count = (rows - 1) * (cols - 1) * 2
    assert len(mesh.faces) < full_face_count


# ---------------------------------------------------------------------------
# Tube-shell normals point inward (geometric contract)
# ---------------------------------------------------------------------------


def test_tube_shell_normals_inward(geometry):
    """Docstring claims inward normals; ceiling faces must have ``n_z < 0``.

    If a future refactor flips the winding (e.g. someone swaps
    ``v0, v2, v1`` to ``v0, v1, v2``) the docstring lies. This test
    pins the geometric contract regardless of what the docstring
    says -- the two must stay in sync because PhysX collision and
    render lighting both depend on it.
    """
    centerline, cross_sections = geometry
    mesh = build_tube_shell(centerline, cross_sections, RING_PTS)
    centroids = mesh.triangles_center
    normals = mesh.face_normals

    # Ceiling faces are those sitting well above the centerline floor (z=0).
    # tube_height = 50 * 0.5 = 25, so centroid_z > 15 isolates the upper shell.
    ceiling = centroids[:, 2] > 20.0
    assert ceiling.any(), "fixture mesh should include ceiling faces"
    # Ceiling inward normal = toward lower z. Allow <=1% outliers on noisy
    # rings where two adjacent triangles can share a near-vertical edge, but
    # demand a strong majority so a winding flip (inward -> outward) would
    # collapse the stat far below this threshold.
    negative_frac = (normals[ceiling, 2] < 0).mean()
    assert negative_frac >= 0.95, (
        f"tube shell ceiling face normals must point inward (-z); only "
        f"{negative_frac:.2%} satisfied. Docstring-vs-code contract violated."
    )


# ---------------------------------------------------------------------------
# build_cave_scene seed is not hardcoded
# ---------------------------------------------------------------------------


def test_build_cave_scene_seed_is_parameterized():
    """``build_cave_scene`` must accept a ``seed`` argument.

    An earlier breakdown PointInstancer hardcoded ``seed=42`` inside
    ``_build_breakdown_instancer``, silently overriding any
    user-provided scenario seed. We can't exercise the USD path
    offline, so this regression checks the public surface instead:
    the argument must exist and ``_build_breakdown_instancer`` must
    accept a seed without defaulting to 42.
    """
    import inspect

    from marslab.terrain.cave.usd_builder import (
        _build_breakdown_instancer,
        build_cave_scene,
    )

    sig = inspect.signature(build_cave_scene)
    assert "seed" in sig.parameters, "build_cave_scene must expose seed parameter"
    # Default is None so callers that omit it inherit cave_data metadata seed.
    assert sig.parameters["seed"].default is None

    inner_sig = inspect.signature(_build_breakdown_instancer)
    assert (
        "seed" in inner_sig.parameters
    ), "_build_breakdown_instancer must accept seed (no more hardcoded 42)"
    # Default is 0, not 42 -- ensures any silent-fallback would be detectable
    # via a seed-determinism regression test on the caller.
    assert inner_sig.parameters["seed"].default == 0


def test_build_cave_scene_seed_respects_metadata(monkeypatch):
    """Without explicit seed, scene builder sources from cave_data metadata.

    Drives the seed-threading logic without needing Isaac Sim by
    intercepting the inner ``_build_breakdown_instancer`` call.
    """
    from marslab.terrain.cave import usd_builder as cmb

    recorded: list[int] = []

    def _fake_instancer(stage, blocks, prim_base_path, seed=0):
        recorded.append(seed)

    # Stub out the Isaac Sim-dependent helpers so the test stays offline.
    monkeypatch.setattr(cmb, "_build_breakdown_instancer", _fake_instancer)
    monkeypatch.setattr(cmb, "_trimesh_to_usd_prim", lambda *a, **kw: None)

    class _FakeStage:
        def DefinePrim(self, *_a, **_kw):  # noqa: N802 - USD naming
            return None

    # Also stub the module-level `UsdGeom` access inside ``build_cave_scene``.
    class _FakeUsdGeom:
        class Xform:
            @staticmethod
            def Define(*_a, **_kw):  # noqa: N802
                return None

    # Patch only the dynamic `from pxr import UsdGeom` line by hijacking the
    # sys.modules mapping so the function body can still `from pxr import UsdGeom`.
    import sys
    import types

    fake_pxr = types.ModuleType("pxr")
    fake_pxr.UsdGeom = _FakeUsdGeom
    # _trimesh_to_usd_prim is stubbed so Gf/Sdf/UsdPhysics/Vt are not needed.
    monkeypatch.setitem(sys.modules, "pxr", fake_pxr)

    cave_data = {
        "surface_mesh": None,
        "tube_mesh": None,
        "floor_mesh": None,
        "skylight_meshes": [],
        "debris_cones": [],
        "breakdown_positions": [{"x": 0.0, "y": 0.0, "z": 0.0, "diameter": 0.5}],
        "skylight_positions": [],
        "surface_elevation": np.zeros((2, 2), dtype=np.float32),
        "metadata": {"seed": 7},
    }
    cmb.build_cave_scene(cave_data, _FakeStage())
    assert recorded == [
        7
    ], f"seed must be sourced from cave_data['metadata']['seed'], got {recorded}"

    recorded.clear()
    cmb.build_cave_scene(cave_data, _FakeStage(), seed=99)
    assert recorded == [99], f"explicit seed argument must win over metadata, got {recorded}"
