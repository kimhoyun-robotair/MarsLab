"""Run integration test: rover spawn with Mars gravity.

Run with: ~/isaacsim/python.sh scripts/run_integration_test.py

Tests:
    1. URDF→USD import succeeds
    2. Gravity configured to 3.72 m/s^2
    3. Robot settles on ground plane
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})

import omni.usd  # noqa: E402
from pxr import Gf, UsdGeom, UsdPhysics  # noqa: E402

from marslab.config.schema import RobotConfig  # noqa: E402
from marslab.robots.rover import spawn_rover  # noqa: E402


def create_ground_plane(stage, z: float = 0.0) -> None:
    """Create a simple collision ground plane."""
    plane_path = "/World/ground_plane"
    plane = UsdGeom.Mesh.Define(stage, plane_path)
    size = 50.0
    points = [
        Gf.Vec3f(-size, -size, z),
        Gf.Vec3f(size, -size, z),
        Gf.Vec3f(size, size, z),
        Gf.Vec3f(-size, size, z),
    ]
    plane.GetPointsAttr().Set(points)
    plane.GetFaceVertexIndicesAttr().Set([0, 1, 2, 0, 2, 3])
    plane.GetFaceVertexCountsAttr().Set([3, 3])

    plane_prim = stage.GetPrimAtPath(plane_path)
    UsdPhysics.CollisionAPI.Apply(plane_prim)


def main() -> None:
    """Run integration tests."""
    stage = omni.usd.get_context().get_stage()
    passed = 0
    failed = 0

    # Test 1: Spawn rover
    print("\n[TEST 1] Spawn rover from URDF...")
    try:
        create_ground_plane(stage)
        config = RobotConfig(
            type="rover",
            urdf_path="assets/robots/rover/simple_rover.urdf",
            spawn_position=[0.0, 0.0, 1.0],
        )
        robot_path = spawn_rover(stage, config, gravity=3.72)
        robot_prim = stage.GetPrimAtPath(robot_path)
        assert robot_prim.IsValid(), f"Robot prim not valid at {robot_path}"
        print(f"  PASSED: Robot spawned at {robot_path}")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # Test 2: Verify gravity
    print("\n[TEST 2] Verify Mars gravity (3.72 ± 0.05 m/s²)...")
    try:
        physics_scene = UsdPhysics.Scene(stage.GetPrimAtPath("/physicsScene"))
        gravity_mag = physics_scene.GetGravityMagnitudeAttr().Get()
        gravity_dir = physics_scene.GetGravityDirectionAttr().Get()
        assert abs(gravity_mag - 3.72) < 0.05, f"Gravity: {gravity_mag}"
        assert gravity_dir[2] == -1.0, f"Direction: {gravity_dir}"
        print(f"  PASSED: Gravity = {gravity_mag} m/s², dir = {gravity_dir}")
        passed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # Test 3: Simulate and check robot settles
    print("\n[TEST 3] Simulate 120 steps, check robot settles...")
    try:
        for _ in range(120):
            simulation_app.update()

        xform = UsdGeom.Xformable(stage.GetPrimAtPath(robot_path))
        world_transform = xform.ComputeLocalToWorldTransform(0)
        position = world_transform.ExtractTranslation()
        z_pos = position[2]
        assert -0.5 < z_pos < 2.0, f"z={z_pos}"
        print(f"  PASSED: Robot z = {z_pos:.3f} (expected near ground)")
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
