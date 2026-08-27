"""Precomputed rock placement CSV boundary."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


class RockCsvError(ValueError):
    """Raised when a precomputed placement CSV is invalid."""


@dataclass(frozen=True, slots=True)
class RockCsv:
    projected_xy_m: NDArray[np.float64]
    diameters_m: NDArray[np.float64]
    source_path: Path


def load_rock_csv(csv_path: Path) -> RockCsv:
    """Load the schema-v1 precomputed rock population while preserving row order."""
    path = Path(csv_path).expanduser().resolve()
    if not path.is_file():
        detail = f"Rock CSV not found: {path}"
        raise RockCsvError(detail)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        columns = {name.strip().lower(): name for name in header}
        x_column = _required_column(columns, header, "x")
        y_column = _required_column(columns, header, "y")
        diameter_column = columns.get("diameter") or columns.get("diameter_m")
        if diameter_column is None:
            detail = f"Rock CSV missing required diameter column: {header}"
            raise RockCsvError(detail)
        rows = [
            (
                _required_float(row.get(x_column), x_column, number),
                _required_float(row.get(y_column), y_column, number),
                _required_float(row.get(diameter_column), diameter_column, number),
            )
            for number, row in enumerate(reader, start=2)
        ]
    if not rows:
        detail = f"Rock CSV is empty: {path}"
        raise RockCsvError(detail)
    values = np.asarray(rows, dtype=np.float64)
    if not np.isfinite(values).all():
        raise RockCsvError("Rock CSV required values must be finite")
    if np.any(values[:, 2] <= 0.0):
        raise RockCsvError("Rock CSV diameters must be positive")
    return RockCsv(
        projected_xy_m=values[:, :2],
        diameters_m=values[:, 2],
        source_path=path,
    )


def _required_column(columns: dict[str, str], header: list[str], name: str) -> str:
    try:
        return columns[name]
    except KeyError:
        detail = f"Rock CSV missing required column {name!r}: {header}"
        raise RockCsvError(detail) from None


def _required_float(value: str | None, column: str, row: int) -> float:
    if value is None or value == "":
        detail = f"Rock CSV {column!r} is missing at row {row}"
        raise RockCsvError(detail)
    try:
        return float(value)
    except ValueError as error:
        detail = f"Rock CSV {column!r} is not a float at row {row}"
        raise RockCsvError(detail) from error
