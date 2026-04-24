"""Unit tests for marslab.terrain.rock_placer."""

import math

import pytest

from marslab.terrain.rock_placer import (
    RockPlacement,
    compute_cfa,
    compute_q,
    sample_rocks_golombek,
)

# --- compute_q ---


def test_compute_q_known_value():
    """q(0.08) = 1.79 + 0.152 / 0.08 = 3.69."""
    assert compute_q(0.08) == pytest.approx(3.69, abs=1e-6)


def test_compute_q_vl2():
    """q(0.04) = 1.79 + 0.152 / 0.04 = 5.59."""
    assert compute_q(0.04) == pytest.approx(5.59, abs=1e-6)


def test_compute_q_zero_raises():
    with pytest.raises(ValueError):
        compute_q(0)


def test_compute_q_negative_raises():
    with pytest.raises(ValueError):
        compute_q(-0.01)


# --- compute_cfa ---


def test_cfa_at_zero_equals_k():
    """CFA at D=0 equals k."""
    assert compute_cfa(0.05, 0.0) == pytest.approx(0.05, abs=1e-6)


def test_cfa_monotonic_decrease():
    """CFA decreases with increasing diameter."""
    k = 0.05
    cfa_05 = compute_cfa(k, 0.5)
    cfa_10 = compute_cfa(k, 1.0)
    cfa_20 = compute_cfa(k, 2.0)
    assert cfa_05 > cfa_10 > cfa_20 > 0


def test_cfa_negative_diameter_raises():
    with pytest.raises(ValueError):
        compute_cfa(0.05, -1.0)


# --- sample_rocks_golombek ---


def test_sample_seed_determinism():
    """Same seed produces identical results."""
    r1 = sample_rocks_golombek(1000, 0.05, (0.05, 3.0), seed=42)
    r2 = sample_rocks_golombek(1000, 0.05, (0.05, 3.0), seed=42)
    assert len(r1) == len(r2)
    for a, b in zip(r1, r2, strict=False):
        assert a.x == b.x
        assert a.y == b.y
        assert a.diameter == b.diameter


def test_sample_different_seeds():
    """Different seeds produce different results."""
    r1 = sample_rocks_golombek(1000, 0.05, (0.05, 3.0), seed=42)
    r2 = sample_rocks_golombek(1000, 0.05, (0.05, 3.0), seed=99)
    positions_1 = [(r.x, r.y) for r in r1[:10]]
    positions_2 = [(r.x, r.y) for r in r2[:10]]
    assert positions_1 != positions_2


def test_sample_diameter_range_respected():
    """All rock diameters are within the specified range."""
    rocks = sample_rocks_golombek(10000, 0.05, (0.1, 2.0), seed=42)
    assert len(rocks) > 0
    for r in rocks:
        assert 0.1 <= r.diameter <= 2.0


def test_sample_positions_within_area():
    """All rock positions are within the square area."""
    area = 10000.0
    side = math.sqrt(area)
    rocks = sample_rocks_golombek(area, 0.05, (0.05, 3.0), seed=42)
    for r in rocks:
        assert 0 <= r.x <= side
        assert 0 <= r.y <= side


def test_sample_height_ratio():
    """Rock height equals height_ratio * diameter."""
    rocks = sample_rocks_golombek(1000, 0.05, (0.05, 3.0), seed=42, height_ratio=0.5)
    for r in rocks[:20]:
        assert r.height == pytest.approx(0.5 * r.diameter, abs=1e-10)


def test_sample_sorted_descending():
    """Rocks are sorted by diameter descending."""
    rocks = sample_rocks_golombek(10000, 0.05, (0.05, 3.0), seed=42)
    for i in range(len(rocks) - 1):
        assert rocks[i].diameter >= rocks[i + 1].diameter


def test_sample_returns_rock_placement():
    """Return type is list of RockPlacement."""
    rocks = sample_rocks_golombek(1000, 0.05, (0.05, 3.0), seed=42)
    assert isinstance(rocks, list)
    assert all(isinstance(r, RockPlacement) for r in rocks)


def test_sample_k_zero_raises():
    with pytest.raises(ValueError):
        sample_rocks_golombek(1000, 0, (0.05, 3.0), seed=42)


def test_sample_invalid_diameter_range():
    with pytest.raises(ValueError):
        sample_rocks_golombek(1000, 0.05, (3.0, 0.05), seed=42)


def test_sample_negative_area_raises():
    with pytest.raises(ValueError):
        sample_rocks_golombek(-100, 0.05, (0.05, 3.0), seed=42)


# --- CFA statistical validation (the key scientific test) ---


def test_cfa_total_area_statistical():
    """Total CFA of sampled rocks matches the k parameter within 10%.

    This validates the statistical model: sampled rocks should cover
    approximately k * area of the total area.
    """
    k = 0.05
    area = 10000.0  # 100m x 100m
    rocks = sample_rocks_golombek(area, k, (0.01, 5.0), seed=42)
    total_rock_area = sum(math.pi / 4 * r.diameter**2 for r in rocks)
    measured_cfa = total_rock_area / area
    assert abs(measured_cfa - k) / k < 0.10, (
        f"Measured CFA {measured_cfa:.4f} differs from k={k} by "
        f"{abs(measured_cfa - k) / k * 100:.1f}%"
    )


@pytest.mark.parametrize(
    "k_val",
    [0.02, 0.04, 0.06, 0.08],
    ids=["InSight", "VL2", "MPF", "VL1"],
)
def test_cfa_landing_sites(k_val):
    """CFA validation against published Mars landing site data."""
    area = 10000.0
    rocks = sample_rocks_golombek(area, k_val, (0.01, 5.0), seed=42)
    total_rock_area = sum(math.pi / 4 * r.diameter**2 for r in rocks)
    measured_cfa = total_rock_area / area
    assert abs(measured_cfa - k_val) / k_val < 0.10, (
        f"k={k_val}: measured CFA {measured_cfa:.4f}, "
        f"error {abs(measured_cfa - k_val) / k_val * 100:.1f}%"
    )
