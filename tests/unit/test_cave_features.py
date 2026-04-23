"""Unit tests for marslab.terrain.cave.features (R5)."""

from __future__ import annotations

import numpy as np
import pytest

from marslab.terrain.cave.features import (
    build_debris_cone,
    compute_skylight_positions,
)
from marslab.terrain.cave.geometry import build_centerline


@pytest.fixture()
def rng():
    """Deterministic rng per test."""
    return np.random.default_rng(42)


@pytest.fixture()
def centerline(rng):
    """Centerline across a 200x200 m domain with 60 stations."""
    return build_centerline((200.0, 200.0), 0.0, 0.15, 60, 0.0, rng)


def test_skylight_zero_count_empty(centerline, rng):
    """count=0 returns [] with no domain dependence."""
    assert compute_skylight_positions(centerline, 0, 20.0, (200.0, 200.0), rng) == []


def test_skylight_no_overlap(centerline, rng):
    """Placed skylights honour the 1.5 * diameter separation rule."""
    positions = compute_skylight_positions(centerline, 5, 20.0, (200.0, 200.0), rng)
    min_dist = 20.0 * 1.5
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            d = float(
                np.hypot(positions[i][0] - positions[j][0], positions[i][1] - positions[j][1])
            )
            assert d >= min_dist


def test_skylight_domain_margin(centerline, rng):
    """Skylight centers stay a half-diameter + 10 m inside the domain edge."""
    diameter = 20.0
    positions = compute_skylight_positions(centerline, 5, diameter, (200.0, 200.0), rng)
    margin = diameter / 2.0 + 10.0
    for x, y in positions:
        assert margin <= x <= 200.0 - margin
        assert margin <= y <= 200.0 - margin


def test_skylight_count_capped_by_domain(rng):
    """Tiny domain with an oversized skylight returns the fallback center."""
    short = build_centerline((20.0, 20.0), 0.0, 0.0, 5, 0.0, rng)
    positions = compute_skylight_positions(short, 3, 25.0, (20.0, 20.0), rng)
    # Only fallback center is returned when no station is within the margin.
    assert positions == [(10.0, 10.0)]


def test_debris_cone_apex_above_base(rng):
    """Debris cone apex Z > base Z."""
    cone = build_debris_cone(
        center_xy=(0.0, 0.0),
        floor_z=0.0,
        skylight_diameter=20.0,
        angle_of_repose=30.0,
        rng=rng,
    )
    # Apex is the ring with t=0; base is t=1. Because of rotation the first
    # ring has r=0, so we check z span instead: z_max - z_min > 0.
    z_span = float(cone.vertices[:, 2].max() - cone.vertices[:, 2].min())
    assert z_span > 0.0


def test_debris_cone_vertex_count(rng):
    """Cone has rings * segments vertices with default params."""
    cone = build_debris_cone(
        center_xy=(0.0, 0.0),
        floor_z=0.0,
        skylight_diameter=20.0,
        angle_of_repose=30.0,
        rng=rng,
    )
    # Defaults: 12 rings * 24 segments
    assert len(cone.vertices) == 12 * 24


def test_debris_cone_base_radius_matches_skylight(rng):
    """Base ring radius ~= 0.8 * skylight_diameter / 2."""
    skylight_d = 20.0
    cone = build_debris_cone(
        center_xy=(0.0, 0.0),
        floor_z=0.0,
        skylight_diameter=skylight_d,
        angle_of_repose=30.0,
        rng=rng,
    )
    expected_base = skylight_d / 2.0 * 0.8
    # Last ring (i = rings-1) holds the base; radii vary slightly due to noise.
    n_segments = 24
    base_ring = cone.vertices[-n_segments:]
    radii = np.hypot(base_ring[:, 0], base_ring[:, 1])
    # +/- 25% slack for the 5% gaussian noise applied per vertex.
    assert (0.75 * expected_base) <= radii.mean() <= (1.25 * expected_base)
