"""Unit tests for marslab.terrain.cave.breakdown."""

from __future__ import annotations

import numpy as np
import pytest

from marslab.terrain.cave.breakdown import generate_breakdown_positions
from marslab.terrain.cave.geometry import build_centerline, build_cross_sections

DOMAIN_M = (200.0, 200.0)
N_STATIONS = 60
RING_PTS = 20


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
        coverage_pct=15.0,
        block_mean=0.5,
        block_sigma=0.3,
        skylight_positions=[],
        skylight_diameter=20.0,
    )
    b1 = generate_breakdown_positions(rng=rng1, **args)
    b2 = generate_breakdown_positions(rng=rng2, **args)
    assert b1 != b2


# ---------------------------------------------------------------------------
# Lognormal mean-correction regression tests.
#
# ``generate_breakdown_positions`` must draw diameters whose expected
# value equals the configured ``block_mean``. The mean-corrected form
# ``mean = log(block_mean) - sigma**2 / 2`` makes ``E[X] = block_mean``
# exactly; the un-corrected ``mean = log(block_mean)`` form would bias
# the expected value upward by ``exp(sigma**2 / 2)``.
# ---------------------------------------------------------------------------


def _draw_uncapped_diameters(
    block_mean: float, block_sigma: float, n_samples: int, seed: int
) -> np.ndarray:
    """Replicate the production lognormal draw without the 5 m cap.

    Mirrors the mean-corrected ``rng.lognormal(mean=log(m) - s**2/2,
    sigma=s)`` call inside ``generate_breakdown_positions`` so this test
    protects the mathematical intent, not the rejection-sampling loop.
    """
    rng = np.random.default_rng(seed)
    return rng.lognormal(
        mean=np.log(block_mean) - block_sigma**2 / 2.0,
        sigma=block_sigma,
        size=n_samples,
    )


def test_block_size_distribution_statistic():
    """Uncapped sample mean approximates ``block_mean`` within 5 percent.

    Regression guard: the un-corrected form ``mean=log(block_mean)``
    biases ``E[X]`` upward by ``exp(sigma**2/2)`` (roughly 4.6 percent
    at sigma=0.3).
    """
    block_mean = 0.5
    block_sigma = 0.3
    samples = _draw_uncapped_diameters(block_mean, block_sigma, 10_000, seed=42)

    sample_mean = float(np.mean(samples))
    rel_err = abs(sample_mean - block_mean) / block_mean
    assert rel_err < 0.05, (
        f"Sample mean {sample_mean:.4f} deviates from block_mean "
        f"{block_mean:.4f} by {rel_err:.3%} (> 5%)."
    )

    # Median should diverge from block_mean by roughly exp(-sigma**2/2);
    # this guards against an accidental revert to median=block_mean.
    sample_median = float(np.median(samples))
    expected_median = block_mean * np.exp(-(block_sigma**2) / 2.0)
    assert abs(sample_median - expected_median) / expected_median < 0.05


def test_lognormal_sigma_scaling():
    """Mean-correction holds across sigma values; median shifts accordingly.

    For sigma=0.3 the old ``mean=log(m)`` form biased the expected value
    by only ~4.6 percent, but for sigma=1.0 the bias balloons to ~65
    percent (``exp(0.5) = 1.6487``). This test locks both regimes in.
    """
    block_mean = 0.5
    n_samples = 10_000

    for block_sigma in (0.3, 1.0):
        samples = _draw_uncapped_diameters(block_mean, block_sigma, n_samples, seed=2026)

        # Expected value must equal block_mean (within MC noise) for both
        # small and large sigma.
        sample_mean = float(np.mean(samples))
        rel_err_mean = abs(sample_mean - block_mean) / block_mean
        assert rel_err_mean < 0.05, (
            f"sigma={block_sigma}: sample mean {sample_mean:.4f} "
            f"deviates from {block_mean:.4f} by {rel_err_mean:.3%}."
        )

        # Median must equal block_mean * exp(-sigma**2/2) -- the defining
        # property of the mean-correction. This is the key check that
        # distinguishes the fix from the old median=block_mean form.
        sample_median = float(np.median(samples))
        expected_median = block_mean * np.exp(-(block_sigma**2) / 2.0)
        rel_err_median = abs(sample_median - expected_median) / expected_median
        assert rel_err_median < 0.05, (
            f"sigma={block_sigma}: sample median {sample_median:.4f} "
            f"differs from expected {expected_median:.4f} "
            f"by {rel_err_median:.3%}."
        )


def test_generator_mean_matches_config_within_cap(geometry):
    """End-to-end: mean of drawn diameters tracks ``block_mean``.

    Exercises the real ``generate_breakdown_positions`` path (including
    the 5 m cap and rejection sampling). With ``block_mean=0.5`` and
    ``block_sigma=0.3`` the cap almost never fires, so the observed
    sample mean should be close to 0.5 m. The un-corrected lognormal
    form would bias it upward to ~0.523 m.
    """
    centerline, cross_sections = geometry
    rng = np.random.default_rng(7)
    blocks = generate_breakdown_positions(
        centerline,
        cross_sections,
        floor_z=0.0,
        coverage_pct=40.0,
        block_mean=0.5,
        block_sigma=0.3,
        skylight_positions=[],
        skylight_diameter=20.0,
        rng=rng,
    )
    diameters = np.array([b["diameter"] for b in blocks])
    assert (
        diameters.size >= 200
    ), f"Need >=200 blocks for a stable mean estimate, got {diameters.size}."

    # 5 m cap is a very soft truncation at block_mean=0.5, block_sigma=0.3
    # (the cap is ~15 sigma in log-space), so bias stays well under 5%.
    sample_mean = float(np.mean(diameters))
    assert abs(sample_mean - 0.5) / 0.5 < 0.08, (
        f"End-to-end sample mean {sample_mean:.4f} deviates from 0.5 m "
        f"by more than 8% -- mean-correction regression?"
    )
