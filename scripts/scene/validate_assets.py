# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = []
# ///
# ─── How to run ───
# marslab/isaac_python.sh scripts/scene/validate_assets.py --fixture scene/tests/fixtures

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

from marslab_scene.isaac_environment import ensure_pxr_runtime


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate rock and habitat asset contracts.")
    parser.add_argument("--fixture", type=Path)
    arguments = parser.parse_args()
    if arguments.fixture is None:
        asset_root = Path("assets")
        input_tier = "canonical"
    else:
        asset_root = arguments.fixture / "assets"
        input_tier = "synthetic"
    pxr_runtime = ensure_pxr_runtime()
    try:
        from marslab_scene.assets.habitats import load_habitat_asset  # noqa: PLC0415
        from marslab_scene.assets.rocks import load_rock_asset  # noqa: PLC0415

        rocks = load_rock_asset(asset_root / "rocks/manifest.yaml")
        habitat = load_habitat_asset(asset_root / "habitats/manifest.yaml")
        print(
            json.dumps(
                {
                    "habitat_bundle_digest": habitat.bundle_digest,
                    "input_tier": input_tier,
                    "rock_bundle_digest": rocks.bundle_digest,
                    "status": "PASS",
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
