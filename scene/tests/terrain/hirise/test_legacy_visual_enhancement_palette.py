from pathlib import Path

import numpy as np
import pytest
import rasterio
from marslab_scene.terrain.hirise.appearance.palette import extract_mastcam_palette
from marslab_scene.terrain.hirise.config import MastcamReferenceConfig

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]


def _write_reference(path: Path, data: np.ndarray) -> Path:
    bands = np.moveaxis(data.astype("uint8"), -1, 0)
    with rasterio.open(
        path,
        "w",
        driver="PNG",
        width=data.shape[1],
        height=data.shape[0],
        count=3,
        dtype="uint8",
    ) as dataset:
        dataset.write(bands)
    return path


def test_extract_mastcam_palette_from_synthetic_reference(tmp_path: Path) -> None:
    image = np.zeros((9, 4, 3), dtype=np.uint8)
    image[:3, :] = np.array([70, 35, 22], dtype=np.uint8)
    image[3:6, :] = np.array([150, 82, 42], dtype=np.uint8)
    image[6:, :] = np.array([220, 178, 118], dtype=np.uint8)
    path = _write_reference(tmp_path / "mastcam.png", image)

    palette = extract_mastcam_palette(
        MastcamReferenceConfig(path=path, robust_percentiles=(0.0, 50.0, 100.0))
    )

    assert palette.shadow_rgb == (70, 35, 22)
    assert palette.midtone_rgb == (150, 82, 42)
    assert palette.highlight_rgb == (220, 178, 118)


def test_extract_mastcam_palette_roi_changes_palette(tmp_path: Path) -> None:
    image = np.zeros((4, 8, 3), dtype=np.uint8)
    image[:, :4] = np.array([60, 30, 20], dtype=np.uint8)
    image[:, 4:] = np.array([210, 160, 100], dtype=np.uint8)
    path = _write_reference(tmp_path / "mastcam.png", image)

    palette = extract_mastcam_palette(
        MastcamReferenceConfig(
            path=path,
            roi=(4, 0, 8, 4),
            robust_percentiles=(0.0, 50.0, 100.0),
        )
    )

    assert palette.shadow_rgb == (210, 160, 100)
    assert palette.midtone_rgb == (210, 160, 100)
    assert palette.highlight_rgb == (210, 160, 100)


def test_extract_mastcam_palette_rejects_likely_sky(tmp_path: Path) -> None:
    image = np.zeros((4, 8, 3), dtype=np.uint8)
    image[:, :4] = np.array([90, 140, 220], dtype=np.uint8)
    image[:, 4:] = np.array([150, 80, 45], dtype=np.uint8)
    path = _write_reference(tmp_path / "mastcam.png", image)

    palette = extract_mastcam_palette(
        MastcamReferenceConfig(path=path, robust_percentiles=(0.0, 50.0, 100.0))
    )

    assert palette.sky_rejection_applied is True
    assert palette.used_pixel_count == 16
    assert palette.midtone_rgb == (150, 80, 45)
