# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = []
# ///
# ─── How to run ───
# marslab/isaac_python.sh scripts/scene/validate_scene.py --scene assets/scene/example.usdz

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from dataclasses import asdict
from pathlib import Path

from marslab_scene.isaac_environment import ensure_pxr_runtime


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a final scene package with pxr.")
    parser.add_argument("--scene", type=Path, required=True)
    arguments = parser.parse_args()
    pxr_runtime = ensure_pxr_runtime()
    try:
        from marslab_scene.usd.validation import validate_runtime_package  # noqa: PLC0415

        report = validate_runtime_package(arguments.scene)
        output = asdict(report)
        output["status"] = "PASS"
        output["terrain_mesh_count"] = len(report.terrain_mesh_paths)
        print(json.dumps(output, sort_keys=True), flush=True)
    except Exception:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK
        traceback.print_exc()
        sys.stderr.flush()
        if pxr_runtime is not None:
            os._exit(1)
        raise
    if pxr_runtime is not None:
        pxr_runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
