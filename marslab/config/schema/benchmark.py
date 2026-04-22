"""Benchmark schema: dataset generation + evaluation parameters.

Split from marslab.config.schema (R2, 2026-04-22). Leaf model — no
cross-domain references.
"""

from pydantic import BaseModel, Field

__all__ = ["BenchmarkConfig"]


class BenchmarkConfig(BaseModel):
    """Benchmark data generation and evaluation parameters."""

    annotation_format: str = Field(default="ai4mars")
    dr_axes: list[str] = Field(default_factory=list, description="Domain randomization axes")
    num_samples: int = Field(default=10000, ge=1)
    seed: int = Field(default=42, ge=0)
