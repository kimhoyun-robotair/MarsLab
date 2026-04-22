"""Integration test: multi-robot spawning in Mars scene.

Run with: ~/isaacsim/python.sh scripts/run_multi_robot_test.py

Tests:
    1. Rover spawn
    2. Rotorcraft spawn
    3. Quadruped (Go2) spawn
    4. All 3 robots coexist
    5. Gravity = 3.72
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})

import omni.usd  # noqa: E402
from pxr import UsdPhysics  # noqa: E402

from marslab.config.schema import RobotConfig  # noqa: E402
from marslab.robots.quadruped import spawn_quadruped  # noqa: E402
from marslab.robots.rotorcraft import spawn_rotorcraft  # noqa: E402
from marslab.robots.rover import spawn_rover  # noqa: E402


def main() -> None:
    """Run multi-robot integration tests."""
    stage = omni.usd.get_context().get_stage()
    passed = 0
    failed = 0
    robot_paths = {}

    # TEST 1: Rover
    print("\n[TEST 1] Spawn rover...")
    try:
        config = RobotConfig(
            type="rover",
            urdf_path="assets/robots/rover/simple_rover.urdf",
            spawn_position=[0.0, 0.0, 1.0],
        )
        path = spawn_rover(stage, config, gravity=3.72)
        assert stage.GetPrimAtPath(path).IsValid()
        robot_paths["rover"] = path
        print(f"  PASSED: {path}")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # TEST 2: Rotorcraft
    print("\n[TEST 2] Spawn rotorcraft...")
    try:
        config = RobotConfig(
            type="rotorcraft",
            urdf_path="assets/robots/rotorcraft/simple_rotorcraft.urdf",
            spawn_position=[5.0, 0.0, 3.0],
        )
        path = spawn_rotorcraft(stage, config, gravity=3.72, atmo_density=0.020)
        assert stage.GetPrimAtPath(path).IsValid()
        robot_paths["rotorcraft"] = path
        print(f"  PASSED: {path}")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # TEST 3: Quadruped (Go2)
    print("\n[TEST 3] Spawn quadruped (Go2)...")
    try:
        config = RobotConfig(
            type="quadruped",
            usd_asset_path="Isaac/Robots/Unitree/Go2/go2.usd",
            spawn_position=[-3.0, 0.0, 1.0],
        )
        path = spawn_quadruped(stage, config, gravity=3.72)
        assert stage.GetPrimAtPath(path).IsValid()
        robot_paths["quadruped"] = path
        print(f"  PASSED: {path}")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # TEST 4: All 3 coexist
    print("\n[TEST 4] All 3 robots coexist...")
    try:
        for name, path in robot_paths.items():
            assert stage.GetPrimAtPath(path).IsValid(), f"{name} prim invalid"
        assert len(robot_paths) == 3, f"Expected 3 robots, got {len(robot_paths)}"
        print(f"  PASSED: {list(robot_paths.keys())}")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # TEST 5: Gravity
    print("\n[TEST 5] Verify Mars gravity...")
    try:
        physics_scene = UsdPhysics.Scene(stage.GetPrimAtPath("/physicsScene"))
        gravity_mag = physics_scene.GetGravityMagnitudeAttr().Get()
        assert abs(gravity_mag - 3.72) < 0.05, f"Gravity: {gravity_mag}"
        print(f"  PASSED: Gravity = {gravity_mag} m/s²")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # Summary
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*40}")

    simulation_app.close()
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
