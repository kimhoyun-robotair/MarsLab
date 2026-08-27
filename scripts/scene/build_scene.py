# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = []
# ///
# ─── How to run ───
# marslab/isaac_python.sh scripts/scene/build_scene.py --config configs/scene/smoke.yaml

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

from marslab_scene.isaac_environment import ensure_pxr_runtime


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one MarsLab scene recipe.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    pxr_runtime = ensure_pxr_runtime()
    try:
        from marslab_scene import build_scene  # noqa: PLC0415

        artifact = build_scene(
            arguments.config,
            output_dir=arguments.output_dir,
            force=arguments.force,
        )
        print(
            json.dumps(
                {
                    "published_path": str(artifact.root_dir),
                    "previous_output_backup": (
                        None
                        if artifact.previous_output_backup is None
                        else str(artifact.previous_output_backup)
                    ),
                    "runtime_package": str(artifact.runtime_package_path),
                },
                sort_keys=True,
            ),
            flush=True,
        )
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
