#!/usr/bin/env python3
"""Run MarsLab from one validated configuration document.
The entry point sequences startup, loop execution, and cleanup.
Isaac and ROS boundaries open only after preflight."""

from __future__ import annotations

import argparse
import logging
from importlib import import_module

from marslab.runtime.assembly import assemble_pre_reset
from marslab.runtime.atmosphere_boot import prepare_atmosphere
from marslab.runtime.lifecycle import CleanupResources, cleanup_phase, run_with_cleanup
from marslab.runtime.loop_context import build_loop_context
from marslab.runtime.post_reset import assemble_post_reset
from marslab.runtime.prepare import prepare_config
from marslab.sim.boot import boot_simulation_app
from marslab.sim.world_setup import create_world


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MarsLab: Isaac Sim Mars rover simulation.",
        allow_abbrev=False,
    )
    parser.add_argument("--config", required=True, help="Path to the MarsLab config YAML.")
    config_path = parser.parse_args().config
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(levelname)s: %(message)s")

    config = prepare_config(config_path)
    mars = config.mars_env
    atmosphere = prepare_atmosphere(config)
    simulation_app = boot_simulation_app(config.runtime)
    resources = CleanupResources(simulation_app=simulation_app)
    run_completed = False
    try:
        try:
            world, stage = create_world(physics_dt=atmosphere.physics_dt, gravity=mars.gravity)
            pre_reset = assemble_pre_reset(
                world=world,
                stage=stage,
                scene_path=str(config.scene.usdz_path),
                rover=config.rover,
                render_config=config.rendering,
                atmosphere_init=atmosphere,
                atmosphere_enabled=config.runtime.atmosphere_enabled,
                ros2_enabled=config.runtime.ros2_enabled,
            )
            post_reset = assemble_post_reset(
                world=world,
                simulation_app=simulation_app,
                pre_reset=pre_reset,
                rover=config.rover,
                atmosphere_init=atmosphere,
                headless=config.runtime.headless,
                atmosphere_enabled=config.runtime.atmosphere_enabled,
                ros2_enabled=config.runtime.ros2_enabled,
                wheel_odom_publish_tf=config.wheel_odom.publish_tf,
            )
            bridge = post_reset.bridge
            resources = CleanupResources(
                bridge=bridge,
                rclpy_shutdown=(import_module("rclpy").shutdown if bridge is not None else None),
                simulation_app=simulation_app,
            )
            context = build_loop_context(
                simulation_app=simulation_app,
                world=world,
                stage=stage,
                config=config,
                atmosphere_init=atmosphere,
                pre_reset=pre_reset,
                post_reset=post_reset,
            )
        except Exception:
            logging.getLogger("marslab.main").exception("Simulation setup failed.")
            raise
        result = run_with_cleanup(context, resources)
        run_completed = True
        return result.status
    finally:
        if not run_completed:
            cleanup_phase(resources)


if __name__ == "__main__":
    raise SystemExit(main())
