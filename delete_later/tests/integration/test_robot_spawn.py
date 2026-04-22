"""Integration test: rover spawn with Mars gravity.

Run with: ~/isaacsim/python.sh -m pytest tests/integration/test_robot_spawn.py -v

THE critical test: IMU z-axis must read 3.72 ± 0.05 m/s^2.
"""

# NOTE (2026-04-22): THE critical IMU z=3.72±0.05 check runs via
#                    ~/isaacsim/python.sh scripts/run_integration_test.py
# Reason for skip: SimulationApp + ROS2 bridge incompatible with pytest in-process.
# Reactivation: v2.0 harness (headless SimApp + pytest).
import pytest

pytestmark = pytest.mark.skip(
    reason="Requires ~/isaacsim/python.sh; use scripts/run_integration_test.py"
)

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": True})

import omni.usd  # noqa: E402
from pxr import Gf, UsdGeom, UsdPhysics  # noqa: E402

from marslab.config.schema import RobotConfig  # noqa: E402
from marslab.robots.rover import spawn_rover  # noqa: E402


def _create_ground_plane(stage, z: float = 0.0) -> None:
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


def test_rover_spawn_and_gravity():
    """Spawn rover on ground plane and verify Mars gravity.

    After settling, the robot should experience ~3.72 m/s^2 downward.
    We verify by checking the physics scene gravity setting and that
    the robot remains on the ground plane (not falling through or flying).
    """
    stage = omni.usd.get_context().get_stage()

    # Create ground and spawn rover
    _create_ground_plane(stage, z=0.0)

    config = RobotConfig(
        type="rover",
        urdf_path="assets/robots/rover/simple_rover.urdf",
        spawn_position=[0.0, 0.0, 1.0],
    )
    robot_path = spawn_rover(stage, config, gravity=3.72)

    # Verify gravity configuration
    physics_scene = UsdPhysics.Scene(stage.GetPrimAtPath("/physicsScene"))
    gravity_mag = physics_scene.GetGravityMagnitudeAttr().Get()
    gravity_dir = physics_scene.GetGravityDirectionAttr().Get()

    assert abs(gravity_mag - 3.72) < 0.05, f"Gravity magnitude: {gravity_mag}"
    assert gravity_dir[2] == -1.0, f"Gravity direction: {gravity_dir}"

    # Verify robot was spawned
    robot_prim = stage.GetPrimAtPath(robot_path)
    assert robot_prim.IsValid(), f"Robot prim not found at {robot_path}"

    # Step simulation to let robot settle
    for _ in range(120):
        simulation_app.update()

    # Verify robot position: should be near ground, not fallen through
    xform = UsdGeom.Xformable(robot_prim)
    world_transform = xform.ComputeLocalToWorldTransform(0)
    position = world_transform.ExtractTranslation()
    z_pos = position[2]

    # Robot should be above ground (z > -0.5) and below spawn height (z < 2.0)
    assert -0.5 < z_pos < 2.0, f"Robot z={z_pos}, expected near ground"

    print(f"[test] Gravity: {gravity_mag} m/s^2, direction: {gravity_dir}")
    print(f"[test] Robot position after settling: z={z_pos:.3f}")


def test_rover_prim_valid():
    """Verify the spawned rover has expected structure."""
    stage = omni.usd.get_context().get_stage()

    config = RobotConfig(
        type="rover",
        urdf_path="assets/robots/rover/simple_rover.urdf",
        spawn_position=[5.0, 5.0, 1.0],
    )
    robot_path = spawn_rover(stage, config, gravity=3.72)
    robot_prim = stage.GetPrimAtPath(robot_path)

    assert robot_prim.IsValid()
    # Should have child prims (links and joints)
    children = robot_prim.GetChildren()
    assert len(children) > 0, "Robot has no child prims"


def teardown_module():
    """Clean shutdown."""
    simulation_app.close()
