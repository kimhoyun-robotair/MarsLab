"""Run one Ingenuity-like drone in the MarsLab scene and atmosphere."""

import logging
import time
from types import SimpleNamespace

import numpy as np

from marslab.config import MarsLabConfig
from marslab.runtime.atmosphere_boot import AtmosphereInit

_LOG = logging.getLogger(__name__)


def run_drone(config: MarsLabConfig, atmosphere_init: AtmosphereInit) -> int:
    from marslab.runtime.lifecycle import CleanupResources, cleanup_phase
    from marslab.sim.boot import boot_simulation_app

    drone_config = config.drone
    if drone_config is None:
        raise ValueError("A drone configuration is required")
    simulation_app = boot_simulation_app(config.runtime)
    resources = CleanupResources(simulation_app=simulation_app)
    world = None
    backend = None
    status = 1
    try:
        from pxr import Gf, PhysxSchema
        from marslab.robots.drone import spawn_drone
        from marslab.robots.drone_actuators import CoaxialActuators
        from marslab.flight.ardupilot import ArduPilotJsonBackend, ExternalWrenchBackend
        from marslab.flight.frames import rotation
        from marslab.flight.types import PhysicsState, ServoCommand
        from marslab.runtime.assembly import assemble_environment, resolve_spawn_position
        from marslab.runtime.main_loop import build_atmosphere_loop_state, _update_atmosphere
        from marslab.sensors.drone_sensors import spawn_drone_sensors
        from marslab.sim.spawn_clearance import resolve_spawn_clearance
        from marslab.sim.world_setup import create_world

        sim = drone_config.simulation
        dt = 1.0 / sim.physics_hz
        world, stage = create_world(physics_dt=dt, gravity=config.mars_env.gravity,
                                    rendering_dt=1.0/sim.render_hz)
        physics = world.get_physics_context()
        physics.set_enable_scene_query_support(True)
        physx = PhysxSchema.PhysxSceneAPI.Apply(physics.get_current_physics_scene_prim())
        physx.CreateEnableCCDAttr(True)
        physx.CreateEnableGPUDynamicsAttr(False)
        physx.CreateBroadphaseTypeAttr("MBP")
        assemble_environment(
            world=world, stage=stage, scene_path=str(config.scene.usdz_path),
            render_config=config.rendering, atmosphere_init=atmosphere_init,
            atmosphere_enabled=config.runtime.atmosphere_enabled,
        )
        position, rpy = resolve_spawn_position(
            stage=stage, terrain_prim_path="/World/Terrain", spawn=drone_config.spawn,
        )
        drone = spawn_drone(world, stage, drone_config, position, rpy)
        # Use the shared terrain collider sweep to keep all four feet above the DEM.
        position = resolve_spawn_clearance(stage, "/World/Terrain", drone.prim_path,
                                           position, 0.003)
        stage.GetPrimAtPath(drone.prim_path).GetAttribute("xformOp:translate").Set(Gf.Vec3d(*position))
        sensors = spawn_drone_sensors(world, drone_config)
        world.reset()
        sensors.initialize_cameras()
        simulation_app.update()
        actuators = CoaxialActuators(drone_config, config.mars_env.gravity)
        backend = (ArduPilotJsonBackend(drone_config.ardupilot)
                   if drone_config.flight_backend == "ardupilot" else ExternalWrenchBackend())
        # Local navigation origin at the spawn XY and nominal ground, in ENU.
        origin = np.asarray(position, dtype=float).copy()
        origin[2] -= -drone_config.foot_z_m+drone_config.foot_radius_m
        previous_velocity = drone.body.get_velocities()[0, :3].copy()
        last_range = None
        bridge = None
        rclpy = None
        if config.runtime.ros2_enabled:
            import rclpy
            from marslab.ros2_bridge.drone_bridge import create_drone_bridge

            bridge = create_drone_bridge(world, drone, sensors, drone_config, config.mars_env.gravity,
                                         backend, actuators)
            resources.bridge = SimpleNamespace(node=bridge)
            resources.rclpy_shutdown = lambda: rclpy.shutdown() if rclpy.ok() else None

        atmo = build_atmosphere_loop_state(atmosphere_init, atmosphere_init.tau)
        atmo_context = SimpleNamespace(
            stage=stage, atmosphere=atmo, physics_dt=dt, render_config=config.rendering,
            compute_sun_fn=None, compute_sol_sun_fn=None, compute_direct_fn=None,
            compute_diffuse_fn=None, compute_sky_dome_fn=None, update_sun_fn=None,
            update_sky_fn=None, configure_fog_fn=None, atmo_panel_update=None,
        )
        if config.runtime.atmosphere_enabled:
            from marslab.environment.diffuse_fraction import compute_diffuse_fraction_1d_approx
            from marslab.environment.light_intensity import compute_direct_intensity
            from marslab.environment.sky_dome import compute_sky_dome_params
            from marslab.environment.sun_position import compute_sol_sun_position, compute_sun_position
            from marslab.rendering.atmosphere_fog import configure_atmosphere_fog
            from marslab.rendering.sky_renderer import update_sky_dome
            from marslab.rendering.sun_renderer import update_sun_light

            atmo_context.compute_sun_fn = compute_sun_position
            atmo_context.compute_sol_sun_fn = compute_sol_sun_position
            atmo_context.compute_direct_fn = compute_direct_intensity
            atmo_context.compute_diffuse_fn = compute_diffuse_fraction_1d_approx
            atmo_context.compute_sky_dome_fn = compute_sky_dome_params
            atmo_context.update_sun_fn = update_sun_light
            atmo_context.update_sky_fn = update_sky_dome
            atmo_context.configure_fog_fn = configure_atmosphere_fog
            if not config.runtime.headless:
                from marslab.gui.atmosphere_panel import AtmospherePanel

                resources.atmosphere_panel = AtmospherePanel(atmo.atmosphere_dict)
                atmo_context.atmo_panel_update = resources.atmosphere_panel.update_display
        if not config.runtime.headless:
            from isaacsim.core.utils.viewports import set_camera_view

            set_camera_view(eye=np.asarray(position)+[3.0, 3.0, 2.0],
                            target=np.asarray(position)+[0.0, 0.0, 0.5])
        _LOG.info("Ingenuity drone spawned at %s using %s", position, drone.asset_url)
        _LOG.info("Flight backend: %s; gravity %.6g m/s^2", drone_config.flight_backend, config.mars_env.gravity)
        if drone_config.flight_backend == "ardupilot":
            _LOG.info("ArduPilot navigation: %s; physics waits for each PWM frame", drone_config.ardupilot.navigation)
        _LOG.info("Physics %d Hz; processed IMU %d Hz; Navcam %d Hz; range %d Hz",
                   sim.physics_hz, drone_config.sensors.imu_hz,
                   drone_config.sensors.nav_hz, drone_config.sensors.range_hz)
        if bridge is not None:
            _LOG.info("Start scripts/run_drone_stack.sh and scripts/run_drone_keyboard.sh in ROS terminals")
        world.play()
        next_render = float(world.current_time)
        wall_origin = time.monotonic()-world.current_time
        restart_pending = False
        rendered_frames = 0
        atmo_elapsed = 0.0
        while simulation_app.is_running() and (rclpy is None or rclpy.ok()):
            if bridge is not None:
                # Wrench and mode are independent DDS callbacks.
                rclpy.spin_once(bridge, timeout_sec=0.0)
                rclpy.spin_once(bridge, timeout_sec=0.0)
            if world.is_stopped():
                restart_pending = True
            if not world.is_playing():
                simulation_app.update()
                wall_origin = time.monotonic()-world.current_time
                continue
            if restart_pending:
                world.reset()
                sensors.initialize_cameras()
                drone.rotor_animation.reset()
                if bridge is not None:
                    bridge.reset_episode()
                backend.reset()
                actuators.reset()
                previous_velocity = drone.body.get_velocities()[0, :3].copy()
                last_range = None
                next_render = float(world.current_time)
                rendered_frames = 0
                atmo_elapsed = 0.0
                wall_origin = time.monotonic()-world.current_time
                world.play()
                restart_pending = False
            command = backend.poll()
            if backend.lockstep and command is None:
                # World.render processes the GUI without advancing physics. A
                # missing autopilot packet pauses simulated time, not the motors.
                world.render()
                time.sleep(0.001)
                continue
            if isinstance(command, ServoCommand):
                force, torque = actuators.step_servos(command.pwm, dt, drone_config.ardupilot.rsc_setpoint)
                powered = command.pwm[7] > 1000
            elif command is not None:
                force, torque = actuators.step(command.force, command.torque, dt, command.powered)
                powered = command.powered
            else:
                force, torque, powered = np.zeros(3), np.zeros(3), False
            drone.rotor_animation.update(float(world.current_time), powered, rpm=actuators.rpm)
            drone.body.apply_forces_and_torques_at_pos(forces=force.reshape(1, 3),
                torques=torque.reshape(1, 3), positions=np.zeros((1, 3)), is_global=False)
            world.step(render=False)
            if bridge is not None:
                bridge.publish_physics()
                if world.current_time_step_index % (sim.physics_hz//drone_config.sensors.range_hz) == 0:
                    last_range = bridge.publish_range()
                bridge.publish_applied_wrench(force, torque)
            pose, quaternion = drone.body.get_world_poses()
            velocity = drone.body.get_velocities()[0]
            body_rotation = rotation(quaternion[0])
            # Feed the autopilot physical SI specific force, with Mars gravity
            # removed from the velocity derivative. No Earth-unit rescaling.
            acceleration = (velocity[:3]-previous_velocity)/dt
            previous_velocity = velocity[:3].copy()
            backend.send_state(PhysicsState(float(world.current_time), pose[0]-origin,
                quaternion[0], velocity[:3], body_rotation.T@velocity[3:],
                body_rotation.T@(acceleration+np.array([0., 0., abs(config.mars_env.gravity)]))), last_range)
            now = float(world.current_time)
            atmo_elapsed += dt
            if now + 1e-9 >= next_render:
                drone.rotor_animation.apply()
                world.render()
                next_render += 1.0/sim.render_hz
                rendered_frames += 1
                if bridge is not None:
                    bridge.publish_images()
                if config.runtime.atmosphere_enabled and rendered_frames % atmo.update_interval == 0:
                    _update_atmosphere(atmo_context, advance_seconds=atmo_elapsed)
                    atmo_elapsed = 0.0
            if sim.duration_seconds and now >= sim.duration_seconds:
                break
            if sim.real_time:
                delay = now - (time.monotonic()-wall_origin)
                if delay > 0.0:
                    time.sleep(min(delay, dt))
        status = 0
    except KeyboardInterrupt:
        status = 0
    except Exception:
        _LOG.exception("Drone simulation failed")
    finally:
        if backend is not None:
            backend.close()
        if world is not None:
            try:
                world.stop()
            except Exception:
                _LOG.exception("Drone world shutdown failed")
                status = 1
        if cleanup_phase(resources, exit_status=status):
            status = 1
    return status
