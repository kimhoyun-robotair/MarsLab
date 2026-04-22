"""Telemetry schema: runtime JSON sink output path.

Split from marslab.config.schema (R2, 2026-04-22). Leaf model — no
cross-domain references. Preserved verbatim (v2.0 telemetry pipeline
is expected to consume this block; see _risks.md §4.2).
"""

from pydantic import BaseModel, Field

__all__ = ["TelemetryConfig"]


class TelemetryConfig(BaseModel):
    """Runtime telemetry output paths (Phase B #23 / B4).

    Consumed by ``marslab.telemetry.json_sink.write_sink`` and the Phase
    B hooks inside ``scripts/run_scene.py``. Keeps workspace file
    locations out of Python source so a user can redirect the Wk1 IMU
    gate output without editing code.
    """

    json_sink_path: str = Field(
        default="_workspace/wk1_imu_gate.json",
        min_length=1,
        description=(
            "Destination path for the Wk1 IMU gate JSON payload. Parent "
            "directories are created on demand by the sink."
        ),
    )
