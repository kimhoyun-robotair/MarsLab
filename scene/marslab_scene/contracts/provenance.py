"""Artifact provenance value object."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Provenance:
    producer: str
    marslab_revision: str | None
    marslab_utils_revision: str | None
    source_files: tuple[Path, ...]
