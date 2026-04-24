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
