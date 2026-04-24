"""Module-focused tests for marslab.config.schema.terrain (offline, P3, R8-5)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from marslab.config.schema import (
    CaveConfig,
    CaveGeometryConfig,
    DemCropConfig,
    TerrainConfig,
)


class TestDemPath:
    """HiRISE source needs at least one of ``dem_path`` / ``converted_dem_dir``."""

    def test_hirise_requires_some_path(self) -> None:
        with pytest.raises(ValidationError):
            TerrainConfig(source="hirise", dem_path=None, converted_dem_dir=None)

    def test_hirise_with_dem_path_only(self) -> None:
        t = TerrainConfig(source="hirise", dem_path="a.tif")
        assert t.dem_path == "a.tif"

    def test_hirise_with_converted_dir_only(self) -> None:
        t = TerrainConfig(source="hirise", converted_dem_dir="cached/")
        assert t.converted_dem_dir == "cached/"

    def test_procedural_needs_preset(self) -> None:
        with pytest.raises(ValidationError):
            TerrainConfig(source="procedural", procedural_preset=None)

    def test_procedural_with_flat_preset(self) -> None:
        t = TerrainConfig(source="procedural", procedural_preset="flat")
        assert t.procedural_preset == "flat"


class TestRockPlacementSpec:
    """Golombek SFD and rock-diameter guards."""

    def test_rock_sfd_k_default_5_percent(self) -> None:
        """Default CFA=0.05 matches moderate rock abundance (Viking-1 class)."""
        assert TerrainConfig(source="procedural", procedural_preset="flat").rock_sfd_k == 0.05

    def test_rock_sfd_k_upper_bound(self) -> None:
        """``le=0.15`` — 15% CFA ceiling matches VL2 plus sigma."""
        with pytest.raises(ValidationError):
            TerrainConfig(source="procedural", procedural_preset="flat", rock_sfd_k=0.2)

    def test_rock_sfd_k_zero_allowed(self) -> None:
        """Zero rock abundance is valid (pure soil scenarios)."""
        t = TerrainConfig(source="procedural", procedural_preset="flat", rock_sfd_k=0.0)
        assert t.rock_sfd_k == 0.0

    def test_rock_diameter_range_must_be_ordered(self) -> None:
        with pytest.raises(ValidationError):
            TerrainConfig(
                source="procedural",
                procedural_preset="flat",
                rock_diameter_range=(3.0, 0.2),
            )

    def test_rock_diameter_range_default_matches_physical_minimum(self) -> None:
        """< 20 cm rocks are rendered as texture, not mesh."""
        t = TerrainConfig(source="procedural", procedural_preset="flat")
        assert t.rock_diameter_range == (0.20, 3.0)


class TestElevationBounds:
    """``DemCropConfig`` pixel-index window invariants."""

    def test_dem_crop_accepts_zero_origin(self) -> None:
        c = DemCropConfig(row=0, col=0, height=100, width=100)
        assert c.row == 0 and c.col == 0

    def test_dem_crop_rejects_negative_origin(self) -> None:
        with pytest.raises(ValidationError):
            DemCropConfig(row=-1, col=0, height=100, width=100)
        with pytest.raises(ValidationError):
            DemCropConfig(row=0, col=-1, height=100, width=100)

    def test_dem_crop_rejects_zero_dimensions(self) -> None:
        with pytest.raises(ValidationError):
            DemCropConfig(row=0, col=0, height=0, width=100)
        with pytest.raises(ValidationError):
            DemCropConfig(row=0, col=0, height=100, width=0)


class TestCaveGeometryDefaultFactory:
    """``CaveConfig.geometry`` uses ``default_factory`` to stay backward-compat."""

    def test_cave_config_default_is_valid(self) -> None:
        """Reviewer 2 #5 (2026-04-24): ``CaveConfig()`` with zero arguments
        must construct without raising.

        Pre-fix: ``skylight_depth_m=90.0`` < ``tube_width_m*tube_height_ratio``
        (200*0.5 = 100m) with default ``skylight_count=10`` tripped
        ``check_cave_ranges``. Raising the default to 110m (still in
        Cushing 2007 68-178m range) restores the ergonomic default.
        """
        c = CaveConfig()
        assert c.tube_width_m * c.tube_height_ratio == 100.0
        assert c.skylight_depth_m >= c.tube_width_m * c.tube_height_ratio
        assert c.skylight_count > 0

    def test_cave_geometry_default_factory(self) -> None:
        """YAMLs that omit ``geometry`` still yield a valid nested config."""
        c = CaveConfig()
        assert isinstance(c.geometry, CaveGeometryConfig)

    def test_cave_geometry_default_values(self) -> None:
        g = CaveGeometryConfig()
        assert g.centerline_path_length_factor == 1.1
        assert g.centerline_freq_ratio_secondary == 2.3
        assert g.surface_noise_sigma == 10.0

    def test_cave_geometry_smooth_sigma_positive(self) -> None:
        with pytest.raises(ValidationError):
            CaveGeometryConfig(cross_section_smooth_sigma=(0.0, 2.0))
        with pytest.raises(ValidationError):
            CaveGeometryConfig(cross_section_smooth_sigma=(3.0, -1.0))

    def test_cave_skylight_depth_reaches_ceiling(self) -> None:
        """With default 200 m width * 0.5 ratio = 100 m tube height — a
        50 m skylight depth cannot reach the tube and must raise."""
        with pytest.raises(ValidationError):
            CaveConfig(skylight_count=5, skylight_depth_m=50.0)

    def test_cave_config_skylight_depth_validation(self) -> None:
        """Reviewer 2 #5 (2026-04-24): raising the default must NOT disable
        the cross-field rule. Invalid user overrides still raise, and the
        boundary (depth == tube_height) is accepted by ``>=``.
        """
        # Explicit underflow with non-zero skylights still raises.
        with pytest.raises(ValidationError):
            CaveConfig(skylight_count=3, skylight_depth_m=80.0)
        # Boundary case: depth == tube_height is permitted by the ``<`` guard.
        c = CaveConfig(skylight_count=3, skylight_depth_m=100.0)
        assert c.skylight_depth_m == 100.0
        # ``skylight_count == 0`` skips the check entirely.
        c0 = CaveConfig(skylight_count=0, skylight_depth_m=20.0)
        assert c0.skylight_count == 0

    def test_cave_geometry_accepts_nested_override(self) -> None:
        """Explicit nested override wins over default factory."""
        c = CaveConfig(geometry=CaveGeometryConfig(surface_noise_sigma=25.0))
        assert c.geometry.surface_noise_sigma == 25.0

    def test_cave_wall_albedo_ordered(self) -> None:
        with pytest.raises(ValidationError):
            CaveConfig(wall_albedo_range=(0.2, 0.05))
