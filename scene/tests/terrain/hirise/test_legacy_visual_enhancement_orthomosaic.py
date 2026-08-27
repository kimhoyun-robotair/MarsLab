from pathlib import Path

import numpy as np
import pytest
import rasterio
from marslab_scene.terrain.hirise.appearance.orthomosaic import read_orthomosaic_luminance
from marslab_scene.terrain.hirise.config import OrthomosaicConfig
from marslab_scene.terrain.hirise.ingest.geotiff import read_dem_window
from rasterio.transform import from_origin

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]


def _write_quadrant_ortho(path: Path, *, count: int = 1) -> Path:
    base = np.zeros((8, 8), dtype=np.uint8)
    base[:4, :4] = 10
    base[:4, 4:] = 80
    base[4:, :4] = 160
    base[4:, 4:] = 240
    if count == 1:
        data = base[np.newaxis, :, :]
    else:
        data = np.stack([base, base // 2, np.full_like(base, 30)], axis=0)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=8,
        height=8,
        count=count,
        dtype="uint8",
        crs="EPSG:32611",
        transform=from_origin(100.0, 200.0, 2.0, 3.0),
    ) as dataset:
        dataset.write(data)
    return path


def test_orthomosaic_luminance_preserves_quadrant_orientation(
    synthetic_geotiff_factory,
    tmp_path: Path,
) -> None:
    dem = synthetic_geotiff_factory(width=8, height=8)
    ortho = _write_quadrant_ortho(tmp_path / "ortho.tif")
    crop = read_dem_window(dem, window=rasterio.windows.Window(0, 0, 8, 8))

    result = read_orthomosaic_luminance(
        OrthomosaicConfig(path=ortho, resampling="nearest", band_mode="grayscale"),
        crop,
        output_width=4,
        output_height=4,
    )

    assert result.array.shape == (4, 4)
    assert result.array[0, 0] < result.array[0, -1] < result.array[-1, 0]
    assert result.array[-1, 0] < result.array[-1, -1]
    assert result.band_mode == "grayscale"


def test_orthomosaic_rgb_luminance_has_expected_shape(
    synthetic_geotiff_factory,
    tmp_path: Path,
) -> None:
    dem = synthetic_geotiff_factory(width=8, height=8)
    ortho = _write_quadrant_ortho(tmp_path / "ortho_rgb.tif", count=3)
    crop = read_dem_window(dem, window=rasterio.windows.Window(0, 0, 8, 8))

    result = read_orthomosaic_luminance(
        OrthomosaicConfig(path=ortho, resampling="bilinear", band_mode="auto"),
        crop,
        output_width=6,
        output_height=5,
    )

    assert result.array.shape == (5, 6)
    assert np.isfinite(result.array).all()
    assert np.min(result.array) >= 0.0
    assert np.max(result.array) <= 1.0
    assert result.band_mode == "rgb"
