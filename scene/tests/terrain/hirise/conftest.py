from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine, from_origin


@pytest.fixture
def synthetic_geotiff_factory(tmp_path: Path) -> Callable[..., Path]:
    def _create(
        *,
        name: str = "synthetic.tif",
        width: int = 10,
        height: int = 10,
        count: int = 1,
        dtype: str = "float32",
        crs: str | None = "EPSG:32611",
        transform: Affine | None = None,
        nodata: float | None = -9999.0,
    ) -> Path:
        path = tmp_path / name
        data = np.arange(width * height, dtype=dtype).reshape(height, width)
        transform = transform or from_origin(100.0, 200.0, 2.0, 3.0)

        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            width=width,
            height=height,
            count=count,
            dtype=dtype,
            crs=crs,
            transform=transform,
            nodata=nodata,
        ) as dataset:
            for band in range(1, count + 1):
                dataset.write(data, band)

        return path

    return _create
