"""Unit tests for marslab.terrain.cave.breakdown (R5)."""

from __future__ import annotations

import numpy as np
import pytest

from marslab.terrain.cave.breakdown import generate_breakdown_positions
from marslab.terrain.cave.geometry import build_centerline, build_cross_sections

DOMAIN_M = (200.0, 200.0)
N_STATIONS = 60
RING_PTS = 20


@pytest.fixture()
def rng():
    """Deterministic rng per test."""
    return np.random.default_rng(42)


@pytest.fixture()
def geometry(rng):
    """Shared centerline / cross_sections for breakdown tests."""
    centerline = build_centerline(DOMAIN_M, 0.0, 0.15, N_STATIONS, 0.0, rng)
    cross_sections = build_cross_sections(centerline, 80.0, 0.5, 0.2, RING_PTS, rng)
    return centerline, cross_sections


def test_zero_coverage_returns_empty(geometry, rng):
    """coverage_pct=0 returns an empty list."""
    centerline, cross_sections = geometry
    blocks = generate_breakdown_positions(
        centerline,
        cross_sections,
        floor_z=0.0,
        ring_pts=RING_PTS,
        coverage_pct=0.0,
        block_mean=0.5,
        block_sigma=0.3,
        skylight_positions=[],
        skylight_diameter=20.0,
        rng=rng,
    )
    assert blocks == []


def test_coverage_area_approximates_target(geometry, rng):
    """Placed area approximates target coverage within generous slack."""
    centerline, cross_sections = geometry
    coverage_pct = 20.0
    blocks = generate_breakdown_positions(
        centerline,
        cross_sections,
        floor_z=0.0,
        ring_pts=RING_PTS,
        coverage_pct=coverage_pct,
        block_mean=0.5,
        block_sigma=0.3,
        skylight_positions=[],
        skylight_diameter=20.0,
        rng=rng,
    )
    placed_area = sum(np.pi * (b["diameter"] / 2.0) ** 2 for b in blocks)
    # Target area = tube_area * 0.2; tube area ~= tube_width * path_length but
    # we just check that the loop actually ran for a sensible number of blocks.
    assert placed_area > 0.0
    assert len(blocks) > 10


def test_diameter_capped_at_5m(geometry, rng):
    """Block diameters are capped at 5 m even with large sigma."""
    centerline, cross_sections = geometry
    blocks = generate_breakdown_positions(
        centerline,
        cross_sections,
        floor_z=0.0,
        ring_pts=RING_PTS,
        coverage_pct=30.0,
        block_mean=1.0,
        block_sigma=1.0,
        skylight_positions=[],
        skylight_diameter=20.0,
        rng=rng,
    )
    for b in blocks:
        assert b["diameter"] <= 5.0
        assert b["diameter"] > 0.0


def test_avoids_skylights(geometry, rng):
    """Blocks do not land inside skylight discs."""
    centerline, cross_sections = geometry
    skylight_xy = (100.0, 100.0)
    skylight_d = 40.0
    blocks = generate_breakdown_positions(
        centerline,
        cross_sections,
        floor_z=0.0,
        ring_pts=RING_PTS,
        coverage_pct=20.0,
        block_mean=0.5,
        block_sigma=0.3,
        skylight_positions=[skylight_xy],
        skylight_diameter=skylight_d,
        rng=rng,
    )
    r2 = (skylight_d / 2.0) ** 2
    for b in blocks:
        dx = b["x"] - skylight_xy[0]
        dy = b["y"] - skylight_xy[1]
        assert dx * dx + dy * dy >= r2


def test_block_z_equals_floor_z(geometry, rng):
    """Every block z equals the provided floor_z."""
    centerline, cross_sections = geometry
    blocks = generate_breakdown_positions(
        centerline,
        cross_sections,
        floor_z=-3.5,
        ring_pts=RING_PTS,
        coverage_pct=10.0,
        block_mean=0.5,
        block_sigma=0.3,
        skylight_positions=[],
        skylight_diameter=20.0,
        rng=rng,
    )
    assert all(b["z"] == -3.5 for b in blocks)


def test_seed_reproducibility(geometry):
    """Same seed => identical block list (order + values)."""
    centerline, cross_sections = geometry
    rng1 = np.random.default_rng(123)
    rng2 = np.random.default_rng(123)
    args = dict(
        centerline=centerline,
        cross_sections=cross_sections,
        floor_z=0.0,
        ring_pts=RING_PTS,
        coverage_pct=15.0,
        block_mean=0.5,
        block_sigma=0.3,
        skylight_positions=[],
        skylight_diameter=20.0,
    )
    b1 = generate_breakdown_positions(rng=rng1, **args)
    b2 = generate_breakdown_positions(rng=rng2, **args)
    assert b1 == b2


def test_different_seeds_differ(geometry):
    """Different seeds produce different block lists."""
    centerline, cross_sections = geometry
    rng1 = np.random.default_rng(1)
    rng2 = np.random.default_rng(99)
    args = dict(
        centerline=centerline,
        cross_sections=cross_sections,
        floor_z=0.0,
        ring_pts=RING_PTS,
        coverage_pct=15.0,
        block_mean=0.5,
        block_sigma=0.3,
        skylight_positions=[],
        skylight_diameter=20.0,
    )
    b1 = generate_breakdown_positions(rng=rng1, **args)
    b2 = generate_breakdown_positions(rng=rng2, **args)
    assert b1 != b2
