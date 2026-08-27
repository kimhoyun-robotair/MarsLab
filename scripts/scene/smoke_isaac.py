# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = []
# ///
# ─── How to run ───
# marslab/isaac_python.sh scripts/scene/smoke_isaac.py --scene scene.usdz \
#   --base-runtime-config configs/config.yaml

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from marslab_scene.runtime_validation import run_isaac_runtime_smoke


def main() -> int:
    parser = argparse.ArgumentParser(description="Run actual Isaac and MarsLab scene smoke.")
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--base-runtime-config", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--input-tier",
        choices=("synthetic", "canonical", "paper"),
        default="synthetic",
    )
    arguments = parser.parse_args()
    input_tier: Literal["synthetic", "canonical", "paper"] = arguments.input_tier
    report = run_isaac_runtime_smoke(
        arguments.scene,
        arguments.base_runtime_config,
        input_tier=input_tier,
        report_path=arguments.report,
        emit_console=True,
    )
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
