"""Unit tests for marslab.terrain.cave.geometry (R5)."""

from __future__ import annotations

import numpy as np
import pytest

from marslab.terrain.cave.geometry import (
    build_centerline,
    build_cross_sections,
    tangent_frames,
)

DOMAIN_M = (100.0, 100.0)
N_STATIONS = 30
RING_PTS = 20


@pytest.fixture()
def rng():
    """Fresh deterministic rng for each test."""
    return np.random.default_rng(42)


@pytest.fixture()
def centerline(rng):
    """Default centerline for a 100x100 m domain, 30 stations."""
    return build_centerline(DOMAIN_M, 0.0, 0.15, N_STATIONS, 0.0, rng)


def test_centerline_shape(centerline):
    """Centerline has the requested station count and trailing dim 3."""
    assert centerline.shape == (N_STATIONS, 3)


def test_centerline_floor_z(centerline):
    """Every centerline point sits exactly at floor_z."""
    assert np.all(centerline[:, 2] == 0.0)


def test_centerline_continuity(centerline):
    """Adjacent stations stay close (no jumps vs. path length)."""
    diffs = np.linalg.norm(np.diff(centerline, axis=0), axis=1)
    # Path length ~ max domain * 1.1 = 110 m spread across 29 segments.
    assert diffs.max() < 10.0
    assert diffs.min() > 0.0


def test_centerline_seed_determinism():
    """Same seed => identical centerline."""
    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)
    c1 = build_centerline(DOMAIN_M, 0.0, 0.15, N_STATIONS, 0.0, rng1)
    c2 = build_centerline(DOMAIN_M, 0.0, 0.15, N_STATIONS, 0.0, rng2)
    assert np.array_equal(c1, c2)


def test_cross_sections_shape(rng, centerline):
    """Cross sections have shape (n_stations, ring_pts, 2)."""
    profiles = build_cross_sections(centerline, 50.0, 0.5, 0.2, RING_PTS, rng)
    assert profiles.shape == (N_STATIONS, RING_PTS, 2)


def test_cross_sections_bounds(rng, centerline):
    """Local_x bounded by tube_width with slack for noise."""
    tube_width = 50.0
    noise_amp = 0.2
    profiles = build_cross_sections(centerline, tube_width, 0.5, noise_amp, RING_PTS, rng)
    a = tube_width / 2.0
    # With noise_amp = 0.2 the radial scale is 1.0 +/- ~0.2, so bound <= 1.5 a for safety.
    assert profiles[..., 0].max() <= a * 1.5
    assert profiles[..., 0].min() >= -a * 1.5


def test_tangent_frames_orthogonality(centerline):
    """tangent perpendicular vectors are unit length and orthogonal in XY."""
    tangent, perp = tangent_frames(centerline)
    # Unit length within 1e-6
    np.testing.assert_allclose(np.linalg.norm(tangent, axis=1), 1.0, atol=1e-6)
    np.testing.assert_allclose(np.linalg.norm(perp, axis=1), 1.0, atol=1e-6)
    # tangent . perp ~= 0 (XY-plane dot product)
    dot = tangent[:, 0] * perp[:, 0] + tangent[:, 1] * perp[:, 1]
    np.testing.assert_allclose(dot, 0.0, atol=1e-6)
    # perp z-component is exactly 0 (horizontal)
    assert np.all(perp[:, 2] == 0.0)
