"""Bit-exact seed replay tests for every randomized callable in MarsLab.

The project's testing rules ("unit tests for everything") and the
Module Dependency Rule ("every randomized function accepts a seed
parameter") imply that *the same seed must produce the same output,
every byte*.

This test runs each randomized public callable twice with the same
seed and asserts ``np.testing.assert_array_equal`` (bit-exact, not
``assert_allclose``). Float lists are compared with raw ``==`` so a
single ULP drift would fail the test.

Modules covered (call-surface discovered with
``rg "seed:|np\\.random|rng\\." marslab/``):

* :mod:`marslab.terrain.rock_placer` -- :func:`sample_rocks_golombek`
  (Golombek SFD; ``np.random.default_rng(seed)``).
* :mod:`marslab.terrain.procedural_generator` -- :func:`generate_terrain`
  for all five presets (``flat``, ``crater``, ``hills``, ``rocky_plain``,
  ``canyon``).
* :mod:`marslab.terrain.cave.geometry` -- :func:`build_centerline`
  and :func:`build_cross_sections` (shared ``rng``, draw order matters).
* :mod:`marslab.terrain.cave.features` -- :func:`build_debris_cone`.
* :mod:`marslab.environment.tau_profile` -- :func:`compute_tau` for all
  three profile types (also no seed; deterministic given config).

The Isaac Sim-dependent modules (``cave.usd_builder``, ``material_applicator``)
are intentionally skipped here because they import Isaac Sim and the
guideline P3 says offline tests must not require it. Their RNG draws
are exercised indirectly through ``cave.geometry`` / ``cave.features``
which they wrap.
"""

from __future__ import annotations

import numpy as np
import pytest

from marslab.environment.tau_profile import compute_tau
from marslab.terrain.cave.features import build_debris_cone
from marslab.terrain.cave.geometry import (
    build_centerline,
    build_cross_sections,
)
from marslab.terrain.procedural_generator import generate_terrain
from marslab.terrain.rock_placer import sample_rocks_golombek

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_rng(seed: int) -> np.random.Generator:
    """Return a fresh ``np.random.Generator`` with the given seed.

    Wrapping the call so a future numpy default-rng change still
    produces the same Generator type for both replays.
    """
    return np.random.default_rng(seed)


# ---------------------------------------------------------------------------
# 1. rock_placer (Golombek SFD)
# ---------------------------------------------------------------------------


class TestRockPlacerReplay:
    """Two replays of ``sample_rocks_golombek`` with the same seed match."""

    @pytest.mark.parametrize("seed", [0, 1, 42, 12345])
    def test_same_seed_bit_exact(self, seed: int) -> None:
        """Same seed -> identical RockPlacement list (bit-exact)."""
        rocks_a = sample_rocks_golombek(
            area_m2=400.0, k=0.05, diameter_range=(0.05, 1.5), seed=seed
        )
        rocks_b = sample_rocks_golombek(
            area_m2=400.0, k=0.05, diameter_range=(0.05, 1.5), seed=seed
        )
        assert len(rocks_a) == len(rocks_b)
        for ra, rb in zip(rocks_a, rocks_b, strict=True):
            assert ra.x == rb.x  # bit-exact float compare
            assert ra.y == rb.y
            assert ra.diameter == rb.diameter
            assert ra.height == rb.height

    def test_different_seeds_diverge(self) -> None:
        """Sanity check: different seeds produce different output.

        Without this, a constant-output bug would falsely pass the
        replay test.
        """
        rocks_a = sample_rocks_golombek(area_m2=400.0, k=0.05, diameter_range=(0.05, 1.5), seed=0)
        rocks_b = sample_rocks_golombek(area_m2=400.0, k=0.05, diameter_range=(0.05, 1.5), seed=1)
        # At minimum the first rock x coordinate should differ.
        assert rocks_a[0].x != rocks_b[0].x


# ---------------------------------------------------------------------------
# 2. procedural_generator (all 5 presets)
# ---------------------------------------------------------------------------


class TestProceduralGeneratorReplay:
    """Two replays of each terrain preset are byte-identical."""

    PRESETS_AND_KWARGS = [
        ("flat", {}),
        ("crater", {}),
        ("hills", {}),
        ("rocky_plain", {}),
        ("canyon", {}),
    ]

    @pytest.mark.parametrize("preset,kwargs", PRESETS_AND_KWARGS)
    def test_preset_replay(self, preset: str, kwargs: dict) -> None:
        """Same (preset, size, resolution, seed) -> bit-exact elevation."""
        seed = 7
        size = (32, 32)
        resolution = 1.0
        elev_a, meta_a = generate_terrain(preset, size, resolution, seed, kwargs)
        elev_b, meta_b = generate_terrain(preset, size, resolution, seed, kwargs)
        np.testing.assert_array_equal(elev_a, elev_b)
        # Metadata is derived from the elevation and itself fully
        # deterministic, so equality is the right contract.
        assert meta_a == meta_b


# ---------------------------------------------------------------------------
# 3. cave.geometry (build_centerline + build_cross_sections)
# ---------------------------------------------------------------------------


class TestCaveGeometryReplay:
    """Replay of the shared-rng cave geometry pipeline.

    Important: ``build_centerline`` consumes 2 uniform draws *before*
    ``build_cross_sections`` consumes one ``standard_normal`` block,
    so the test exercises the documented draw order.
    """

    def _run(self, seed: int) -> tuple[np.ndarray, np.ndarray]:
        rng = _fresh_rng(seed)
        centerline = build_centerline(
            domain_m=(60.0, 60.0),
            direction_deg=30.0,
            curvature=0.5,
            n_points=20,
            floor_z=0.0,
            rng=rng,
        )
        cross_sections = build_cross_sections(
            centerline=centerline,
            tube_width=4.0,
            height_ratio=0.6,
            noise_amp=0.1,
            ring_pts=12,
            rng=rng,
        )
        return centerline, cross_sections

    @pytest.mark.parametrize("seed", [0, 7, 99])
    def test_replay_bit_exact(self, seed: int) -> None:
        """Same seed -> identical centerline AND cross_sections."""
        cl_a, cs_a = self._run(seed)
        cl_b, cs_b = self._run(seed)
        np.testing.assert_array_equal(cl_a, cl_b)
        np.testing.assert_array_equal(cs_a, cs_b)


# ---------------------------------------------------------------------------
# 4. cave.features.build_debris_cone
# ---------------------------------------------------------------------------


class TestDebrisConeReplay:
    """``build_debris_cone`` mesh vertices are bit-exact for the same seed."""

    @pytest.mark.parametrize("seed", [0, 1, 42])
    def test_replay_bit_exact(self, seed: int) -> None:
        """Two replays produce identical vertex arrays."""
        rng_a = _fresh_rng(seed)
        rng_b = _fresh_rng(seed)
        mesh_a = build_debris_cone(
            center_xy=(0.0, 0.0),
            floor_z=0.0,
            skylight_diameter=4.0,
            angle_of_repose=30.0,
            rng=rng_a,
        )
        mesh_b = build_debris_cone(
            center_xy=(0.0, 0.0),
            floor_z=0.0,
            skylight_diameter=4.0,
            angle_of_repose=30.0,
            rng=rng_b,
        )
        np.testing.assert_array_equal(np.asarray(mesh_a.vertices), np.asarray(mesh_b.vertices))
        np.testing.assert_array_equal(np.asarray(mesh_a.faces), np.asarray(mesh_b.faces))


# ---------------------------------------------------------------------------
# 5. tau_profile (deterministic, no seed)
# ---------------------------------------------------------------------------


class TestTauProfileReplay:
    """All three tau profiles are deterministic given config."""

    CASES = [
        ("constant", {"base_tau": 0.5}),
        ("ramp", {"start_tau": 0.3, "end_tau": 2.0}),
        ("sine", {"base_tau": 0.5, "amplitude": 0.3, "period_fraction": 1.0}),
    ]

    @pytest.mark.parametrize("profile,kwargs", CASES)
    def test_replay_bit_exact(self, profile: str, kwargs: dict) -> None:
        """Same (profile, t, kwargs) -> bit-exact tau values across t in [0, 1]."""
        ts = np.linspace(0.0, 1.0, 101)
        out_a = [compute_tau(profile, float(t), **kwargs) for t in ts]
        out_b = [compute_tau(profile, float(t), **kwargs) for t in ts]
        # Python list equality is a bit-exact float compare for
        # plain ``float`` elements.
        assert out_a == out_b


# ---------------------------------------------------------------------------
# 7. Cross-call independence
# ---------------------------------------------------------------------------


class TestCrossCallIndependence:
    """Calling another seeded function in between must not perturb replay.

    A class of bugs is to leak module-level RNG state. We assert that
    interleaving two seeded calls with a third (different-seed) call
    in between still produces identical output for the first two.
    """

    def test_rock_placer_isolated_from_terrain_call(self) -> None:
        """Rock placement output unchanged by an intervening terrain call."""
        rocks_a = sample_rocks_golombek(area_m2=200.0, k=0.05, diameter_range=(0.05, 1.0), seed=11)
        # Intervening call with a different seed.
        _ = generate_terrain("hills", (16, 16), 1.0, seed=99)
        rocks_b = sample_rocks_golombek(area_m2=200.0, k=0.05, diameter_range=(0.05, 1.0), seed=11)
        assert len(rocks_a) == len(rocks_b)
        for ra, rb in zip(rocks_a, rocks_b, strict=True):
            assert (ra.x, ra.y, ra.diameter, ra.height) == (
                rb.x,
                rb.y,
                rb.diameter,
                rb.height,
            )
