from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]
from marslab_scene.terrain.hirise.config import CropConfig
from marslab_scene.terrain.hirise.dem.crop import (
    CropOutOfBoundsError,
    compute_crop_origin_projected,
    compute_crop_window,
)
from marslab_scene.terrain.hirise.ingest.dem_info import inspect_dem
from marslab_scene.terrain.hirise.ingest.geotiff import read_dem_window
from rasterio.transform import Affine, from_origin
from rasterio.windows import Window


def test_compute_center_crop_window_by_meter_size(
    synthetic_geotiff_factory: Callable[..., Path],
) -> None:
    path = synthetic_geotiff_factory(
        width=100,
        height=100,
        transform=from_origin(0.0, 100.0, 1.0, 1.0),
    )
    info = inspect_dem(path)

    window = compute_crop_window(
        info,
        CropConfig(width_m=20.0, height_m=10.0, center_mode="dataset_center"),
    )

    assert window == Window(col_off=40, row_off=45, width=20, height=10)


def test_compute_projected_center_crop_window(
    synthetic_geotiff_factory: Callable[..., Path],
) -> None:
    path = synthetic_geotiff_factory(
        width=100,
        height=100,
        transform=from_origin(0.0, 100.0, 1.0, 1.0),
    )
    info = inspect_dem(path)

    window = compute_crop_window(
        info,
        CropConfig(
            width_m=10.0,
            height_m=10.0,
            center_mode="projected",
            center_x=30.0,
            center_y=70.0,
        ),
    )

    assert window == Window(col_off=25, row_off=25, width=10, height=10)


def test_crop_out_of_bounds_raises_when_partial_false(
    synthetic_geotiff_factory: Callable[..., Path],
) -> None:
    path = synthetic_geotiff_factory(
        width=100,
        height=100,
        transform=from_origin(0.0, 100.0, 1.0, 1.0),
    )
    info = inspect_dem(path)

    with pytest.raises(CropOutOfBoundsError):
        compute_crop_window(
            info,
            CropConfig(
                width_m=20.0,
                height_m=20.0,
                center_mode="projected",
                center_x=5.0,
                center_y=95.0,
                allow_partial=False,
            ),
        )


def test_crop_rejects_rotated_transform(
    synthetic_geotiff_factory: Callable[..., Path],
) -> None:
    path = synthetic_geotiff_factory(
        width=100,
        height=100,
        transform=Affine(1.0, 0.1, 0.0, 0.0, -1.0, 100.0),
    )
    info = inspect_dem(path)

    with pytest.raises(ValueError, match="Rotated or sheared"):
        compute_crop_window(info, CropConfig(width_m=10.0, height_m=10.0))


def test_read_dem_window_reads_expected_crop(
    synthetic_geotiff_factory: Callable[..., Path],
) -> None:
    path = synthetic_geotiff_factory(
        width=10,
        height=10,
        transform=from_origin(0.0, 10.0, 1.0, 1.0),
    )
    window = Window(col_off=2, row_off=3, width=4, height=2)

    crop = read_dem_window(path, window)

    assert crop.array.shape == (2, 4)
    np.testing.assert_array_equal(crop.array, np.array([[32, 33, 34, 35], [42, 43, 44, 45]]))
    assert crop.mask.shape == (2, 4)
    assert not crop.mask.any()
    assert crop.transform == from_origin(2.0, 7.0, 1.0, 1.0)
    assert crop.bounds == (2.0, 5.0, 6.0, 7.0)


def test_crop_window_does_not_read_full_file(
    synthetic_geotiff_factory: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = synthetic_geotiff_factory()
    captured: dict[str, Window | None] = {}

    from marslab_scene.terrain.hirise.ingest import geotiff

    real_open = geotiff.rasterio.open

    class DatasetProxy:
        def __init__(self, dataset: object) -> None:
            self._dataset = dataset

        def __enter__(self) -> "DatasetProxy":
            self._dataset.__enter__()
            return self

        def __exit__(self, *args: object) -> object:
            return self._dataset.__exit__(*args)

        def __getattr__(self, name: str) -> object:
            return getattr(self._dataset, name)

        def read(self, band: int, *, window: Window | None = None, masked: bool = False) -> object:
            captured["window"] = window
            return self._dataset.read(band, window=window, masked=masked)

    def open_proxy(*args: object, **kwargs: object) -> DatasetProxy:
        return DatasetProxy(real_open(*args, **kwargs))

    monkeypatch.setattr(geotiff.rasterio, "open", open_proxy)

    window = Window(col_off=1, row_off=2, width=3, height=4)
    read_dem_window(path, window)

    assert captured["window"] == window


def test_compute_crop_origin_projected() -> None:
    origin = compute_crop_origin_projected(from_origin(2.0, 7.0, 1.0, 1.0), width=4, height=2)

    assert origin == (4.0, 6.0)
