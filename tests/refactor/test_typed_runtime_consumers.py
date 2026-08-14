from pathlib import Path

from marslab.config.schema.rover_sensors import DisabledSensorConfig, SensorsConfig
from marslab.runtime.loop_context import build_loop_context
from marslab.runtime.main_loop import AtmosphereLoopState
from marslab.runtime.run_plan import RunMode, RunPlanRequest, build_run_plan
from marslab.runtime.sensor_frames import build_sensor_frames, sensor_frames_to_tuples

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_plan():
    return build_run_plan(
        RunPlanRequest(
            scene_path="assets/scene/jezero_plain/jezero_plain.usdz",
            rover_usd_path="assets/robots/rover/m2020.usd",
            scenario_path="configs/default.yaml",
            rover_yaml_path="configs/rover_m2020.yaml",
        ),
        RunMode.RUN,
        cwd=REPO_ROOT,
    )


def test_sensor_frames_consume_typed_plan_sensors_and_skip_disabled_variant() -> None:
    # Given: the canonical typed settings with the 2-D lidar explicitly disabled.
    plan = _run_plan()
    sensors = SensorsConfig(
        seed=plan.sensors.seed,
        camera=plan.sensors.camera,
        lidar_3d=plan.sensors.lidar_3d,
        lidar_2d=DisabledSensorConfig(enabled=False),
        imu=plan.sensors.imu,
    )

    # When: the offline TF seam consumes the frozen model directly.
    frames = sensor_frames_to_tuples(build_sensor_frames(sensors))

    # Then: enabled sensor transforms survive and the disabled variant contributes no frame.
    assert [frame[0] for frame in frames] == ["camera_link", "lidar_link", "imu_link"]
    assert frames[0][1] == [1.2, 0.0, 2.1]


def test_loop_context_consumes_typed_plan_control() -> None:
    # Given: a canonical typed control model and inert offline runtime handles.
    plan = _run_plan()
    atmosphere = AtmosphereLoopState(
        atmosphere_dict={},
        sol_duration=88775.244,
        solar_constant=589.2,
    )

    # When: the loop assembly seam consumes the model directly.
    context = build_loop_context(
        simulation_app=None,
        world=None,
        stage=None,
        articulation=None,
        imu=None,
        drive_indices=[0, 1],
        steer_indices=[2, 3],
        control_cfg=plan.control,
        physics_dt=1.0 / 60.0,
        atmosphere=atmosphere,
        render_config=None,
        ackermann_fn=lambda *args: args,
        bridge=None,
    )

    # Then: the observable loop geometry and limits equal the validated plan fields.
    assert context.geometry.wheelbase == plan.control.wheelbase
    assert context.geometry.wheel_radius == plan.control.wheel_radius
    assert context.control_limits.max_steer_angle == plan.control.max_steer_angle
