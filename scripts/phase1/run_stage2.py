"""Phase 1 Stage 2 runtime: Mars terrain + atmosphere viewer (thin CLI).

Renders a DEM-based (or procedural) terrain mesh with Mars PBR materials
and atmosphere (sun, sky dome, fog). No rover, no ROS2, no rocks beyond
the Golombek SFD scatter. The GUI runs indefinitely so the user can
freely navigate the scene. Press Ctrl+C to exit.

Data flow (P2 unidirectional):
    Config YAML -> run_stage2_boot (offline) -> SimulationApp
    -> setup_stage2_scene (USD + atmosphere) -> run_stage2_loop.

R7-2 (2026-04-23): the original 421-LOC script was split into three
focused modules under ``marslab.runtime``. Rollback path is ``git log``
before 2026-04-23.

Usage:
    scripts/isaac_python.sh scripts/phase1/run_stage2.py \\
        --config configs/mars_env.yaml
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from marslab.cli.stage2_args import parse_stage2_args  # noqa: E402
from marslab.runtime.stage2_boot import run_stage2_boot  # noqa: E402


def main() -> int:
    """Entry point for the Stage 2 viewer."""
    args = parse_stage2_args()

    boot = run_stage2_boot(args.config, repo_root=REPO_ROOT)

    # Isaac Sim must be alive before any ``omni.*`` / ``isaacsim.*``
    # import resolves -- so the SimulationApp launch stays in this CLI
    # shim and the scene/loop modules import their Kit-dependent
    # functions lazily.
    from isaacsim import SimulationApp  # noqa: E402

    simulation_app = SimulationApp(
        {"headless": bool(args.headless), "renderer": "RaytracedLighting"}
    )

    from marslab.runtime.stage2_loop import run_stage2_loop  # noqa: E402
    from marslab.runtime.stage2_scene import setup_stage2_scene  # noqa: E402

    scene = setup_stage2_scene(boot)
    run_stage2_loop(simulation_app, boot, scene, headless=bool(args.headless))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
