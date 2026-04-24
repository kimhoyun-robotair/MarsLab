"""Integration test: IMU z-axis gravity on spawned rover (THE critical test).

This is the Wk1 acceptance gate from ``CLAUDE.md`` Testing Requirements::

    Robot spawn: IMU z-axis = 3.72 +/- 0.05 m/s^2 (THE critical test)

Execution (Isaac Sim required, GPU required)::

    scripts/isaac_python.sh scripts/run_integration_test.py \
        tests/integration/test_imu_gravity_actual.py

The test is marked ``integration`` so ``pytest tests/unit/`` skips it.
It also uses ``pytest.importorskip("isaacsim")`` so that even a manual
``pytest tests/integration/`` on a non-Isaac host reports SKIPPED
rather than ERROR — matching Reviewer 2 #15's "external reproducibility"
requirement.

References:
  * PLAN.md §5.3 Wk1 acceptance criteria
  * tests/visual_inspection/checklist.md V9 (IMU probe procedure)
  * marslab/sensors/sensor_spawner.py (IMU spawn path)
"""

from __future__ import annotations

import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Skip guard.  ``isaacsim`` only resolves inside Isaac Sim's bundled Python
# (launched via ``scripts/isaac_python.sh``).  On system Python the import
# fails fast and the test is reported SKIPPED with a readable reason.
# ---------------------------------------------------------------------------
isaacsim = pytest.importorskip(
    "isaacsim",
    reason="Isaac Sim not available; run via scripts/isaac_python.sh",
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.mark.integration
def test_imu_z_gravity_within_mars_band() -> None:
    """Assert IMU linear-acceleration z is within 3.72 +/- 0.05 m/s^2.

    Procedure (matches visual_inspection/checklist.md V9):
      1. Boot ``SimulationApp`` via ``marslab.sim.boot.boot_simulation_app``
         in headless mode.
      2. Run ``run_stage2_boot`` + ``setup_stage2_scene`` to install the
         Jezero Flat terrain + Mars PhysicsScene (gravity = 3.72).
      3. Spawn the NASA JPL m2020 rover USD via
         ``marslab.robots.rover.spawn_rover``.
      4. After physics warmup (1000 steps @ 1/200 = 5 s), read
         ``isaacsim.sensors.physics.IMUSensor.get_current_frame()``.
      5. Assert ``abs(imu.lin_acc[2] - 3.72) <= 0.05``.

    The test purposefully uses the same spawn helper as ``run_stage4.py``
    so that a regression in the production runtime surfaces here.
    """
    # Deferred imports: available only inside the Isaac Sim Python runtime.
    from marslab.robots.rover import spawn_rover  # noqa: PLC0415
    from marslab.runtime.stage2_boot import run_stage2_boot  # noqa: PLC0415
    from marslab.runtime.stage2_scene import setup_stage2_scene  # noqa: PLC0415
    from marslab.sim.boot import boot_simulation_app  # noqa: PLC0415

    simulation_app = boot_simulation_app(headless=True)
    try:
        config_path = os.path.join(REPO_ROOT, "configs/scenarios/jezero_flat.yaml")
        boot = run_stage2_boot(config_path, repo_root=REPO_ROOT)
        scene = setup_stage2_scene(boot)
        world = scene.world
        stage = scene.stage

        rover_cfg = boot.config["rover"]
        usd_rel = rover_cfg["usd_path"]
        usd_abs = (
            usd_rel if os.path.isabs(usd_rel) else os.path.abspath(os.path.join(REPO_ROOT, usd_rel))
        )
        from marslab.config.scenario_loader import resolve_spawn_pose  # noqa: PLC0415

        spawn_xyz = resolve_spawn_pose(rover_cfg, boot.elevation, boot.metadata, boot.resolution)
        spawned = spawn_rover(stage, rover_cfg, usd_abs, spawn_xyz)

        from isaacsim.sensors.physics import IMUSensor  # noqa: PLC0415

        imu_path = f"{spawned.prim_path}/base_link/integration_imu_probe"
        imu = IMUSensor(prim_path=imu_path)

        world.reset()
        # 5 seconds of physics at 1/200 dt — matches checklist.md V9 procedure.
        for _ in range(1000):
            world.step(render=False)

        frame = imu.get_current_frame()
        lin_acc = frame["lin_acc"]
        imu_z = float(lin_acc[2])
        assert 3.67 <= imu_z <= 3.77, (
            f"IMU z = {imu_z:.4f} m/s^2 outside Mars band [3.67, 3.77]. "
            "Check PhysicsScene gravity or rover spawn settle gating."
        )
    finally:
        simulation_app.close()
