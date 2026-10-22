"""Prepare the pinned Mars-gravity ArduPilot SITL build and vehicle defaults.

This is a dependency build, not a simulator or a test runner. ArduPilot source
and its GPL license stay in the separate, ignored .ardupilot directory.
"""

import argparse
import json
from pathlib import Path
import re
import subprocess

import yaml

UPSTREAM_TAG = "Copter-4.6.3"
UPSTREAM_COMMIT = "92b0cd788ec29406f26c6f9c31d5ceedbd1cc538"
MODEL_PATCH_REVISION = 2
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = PROJECT_ROOT / ".ardupilot" / "source"


def read_settings(config_path):
    with Path(config_path).expanduser().open(encoding="utf-8") as stream:
        settings = yaml.safe_load(stream)
    drone = settings["drone"]
    if drone.get("flight_backend", "ardupilot") != "ardupilot":
        raise ValueError("This command requires drone.flight_backend: ardupilot")
    return settings


def build_metadata(source):
    return Path(source) / "build" / "marslab-sitl.json"


def patch_gravity(source, gravity):
    header = Path(source) / "libraries" / "AP_Math" / "definitions.h"
    literal = f"{float(gravity):.9g}"
    if "." not in literal and "e" not in literal.lower():
        literal += ".0"
    replacement = f"#define GRAVITY_MSS     {literal}f"
    contents, count = re.subn(r"^#define\s+GRAVITY_MSS\s+[^\n]+", replacement,
                             header.read_text(encoding="utf-8"), flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError("Pinned ArduPilot gravity definition was not found exactly once")
    header.write_text(contents, encoding="utf-8")
    # This is the *Earth standard-atmosphere table*, used by SITL's virtual
    # barometer/geodetic bookkeeping. Its hard-coded layer pressures require
    # the standard's g0; changing that exponent alone breaks even ground altitude.
    # It does not supply gravity to the Isaac plant, INS, EKF or flight control.
    atmosphere = Path(source) / "libraries" / "AP_Baro" / "AP_Baro_atmosphere.cpp"
    contents = atmosphere.read_text(encoding="utf-8").replace("GRAVITY_MSS", "STANDARD_ATMOSPHERE_GRAVITY")
    marker = "static const float radius_earth = 6356.766E3;"
    definition = "static constexpr float STANDARD_ATMOSPHERE_GRAVITY = 9.80665f;\n"
    if definition not in contents:
        if marker not in contents:
            raise RuntimeError("Pinned ArduPilot standard-atmosphere definition was not found")
        contents = contents.replace(marker, definition+marker, 1)
    atmosphere.write_text(contents, encoding="utf-8")


def parameter_values(settings, source):
    values = {}
    # Preserve ArduPilot's published helicopter defaults, then describe our plant.
    for filename in ("copter-heli.parm", "copter-heli-dual.parm"):
        path = Path(source) / "Tools" / "autotest" / "default_params" / filename
        for row in path.read_text(encoding="utf-8").splitlines():
            fields = row.split("#", 1)[0].split()
            if len(fields) == 2:
                values[fields[0]] = float(fields[1])
    drone = settings["drone"]
    ap = drone.get("ardupilot", {})
    actuator = drone.get("actuators", {})
    physics_hz = int(drone.get("simulation", {}).get("physics_hz", 500))
    # Keep the native scheduler within its published 50..400 Hz range and
    # aligned with whole JSON physics samples (250 Hz for the 500 Hz plant).
    controller_hz = max(rate for rate in range(50, min(400, physics_hz)+1)
                        if physics_hz % rate == 0)
    minimum = float(actuator.get("collective_min_deg", -4.5))
    maximum = float(actuator.get("collective_max_deg", 17.5))
    hover = float(actuator.get("collective_hover_deg", 8.0))
    # Match AP's collective endpoint to the simulator's total thrust limit.
    # The decoder still represents the full physical blade range, including
    # differential collective for yaw. Avoid hidden heave saturation before AP's limit.
    flight_maximum = min(maximum, minimum+float(actuator.get("max_thrust_ratio", 1.6))*(hover-minimum))
    collective_pwm_max = round(1000+1000*(flight_maximum-minimum)/(maximum-minimum))
    values.update({
        "FRAME_CLASS": 11, "H_DUAL_MODE": 2, "H_YAW_SCALER": 0, "H_DCP_SCALER": 1,
        "H_SW_TYPE": 3, "H_SW2_TYPE": 3, "H_SW_COL_DIR": 0, "H_SW2_COL_DIR": 0,
        "H_SW_LIN_SVO": 0, "H_SW2_LIN_SVO": 0,
        "H_COL_MIN": 1000, "H_COL_MAX": collective_pwm_max,
        "H_COL2_MIN": 1000, "H_COL2_MAX": collective_pwm_max,
        "H_COL_ANG_MIN": minimum, "H_COL_ANG_MAX": flight_maximum,
        "H_COL_ZERO_THRST": minimum, "H_COL_LAND_MIN": minimum,
        "H_RSC_MODE": 2, "H_RSC_SETPOINT": 100*float(ap.get("rsc_setpoint", 0.7)),
        "H_RSC_RAMP_TIME": float(actuator.get("spool_up_seconds", 1.0)),
        "H_RSC_RUNUP_TIME": float(actuator.get("spool_up_seconds", 1.0))+1.0,
        "ATC_HOVR_ROL_TRM": 0, "MOT_THST_HOVER": (hover-minimum)/(flight_maximum-minimum),
        "MOT_HOVER_LEARN": 0, "RC8_OPTION": 32,
        "AHRS_EKF_TYPE": 10 if ap.get("navigation", "sim_truth") == "sim_truth" else 3,
        # The vehicle has one IMU. Match native scheduling to the lockstep
        # physics samples rather than quantizing a 400 Hz loop onto 500 Hz states.
        "INS_GYR_CAL": 0, "SIM_IMU_COUNT": 1,
        "SIM_RATE_HZ": physics_hz, "SCHED_LOOP_RATE": controller_hz,
        # This MVP has a ROS command source and simulated RC, not a physical receiver/GCS.
        "FS_THR_ENABLE": 0, "FS_GCS_ENABLE": 0, "FS_CRASH_CHECK": 0, "FENCE_ENABLE": 0,
        "BATT_MONITOR": 0, "ARMING_CHECK": 1, "BRD_SAFETY_DEFLT": 0,
        "SYSID_MYGCS": 255, "SERIAL0_PROTOCOL": 2,
    })
    # No RC mode switch is connected in this ROS-operated MVP.
    values.update({f"FLTMODE{channel}": 0 for channel in range(1, 7)})
    if ap.get("navigation", "sim_truth") == "sim_truth":
        # Navigation comes from native simulation AHRS, not a fictitious Mars
        # GNSS receiver. Leave native arming checks on for the configured sensors.
        values.update({"GPS1_TYPE": 0, "GPS2_TYPE": 0})
    # Stock two-IMU helicopter/JSON defaults contain a second calibration.
    # ArduPilot correctly rejects a calibration for an IMU that is absent.
    for instance in (2, 3):
        for axis in "XYZ":
            values[f"INS_ACC{instance}OFFS_{axis}"] = 0.0
            values[f"INS_ACC{instance}SCAL_{axis}"] = 1.0
    # ArduPilot's initial altitude-tuning guidance for Copter <=4.6 uses
    # ACCZ_P=hover, ACCZ_I=2*hover and halves POSZ/VELZ for vertical oscillation.
    # These remain native controller gains; runtime observations are in DRONE.md.
    hover_fraction = values["MOT_THST_HOVER"]
    values.update({"PSC_ACCZ_P": hover_fraction, "PSC_ACCZ_I": 2*hover_fraction,
                   "PSC_POSZ_P": 0.5, "PSC_VELZ_P": 2.5})
    for channel in range(1, 7):
        values.update({f"SERVO{channel}_FUNCTION": 32+channel,
                       f"SERVO{channel}_MIN": 1000, f"SERVO{channel}_MAX": 2000,
                       f"SERVO{channel}_TRIM": 1500, f"SERVO{channel}_REVERSED": 0})
    values.update({"SERVO8_FUNCTION": 31, "SERVO8_MIN": 1000, "SERVO8_MAX": 2000})
    # A direct moment plant needs no helicopter rate-to-cyclic feedforward.
    # For I*w_dot = effectiveness*u and u = Kp*(w_ref-w), choose
    # Kp = bandwidth*I/effectiveness. These are model-derived MVP gains, not NASA gains.
    inertia = drone.get("inertia_kgm2", [0.025, 0.025, 0.045])
    torque = actuator.get("max_torque_nm", [0.35, 0.35, 0.12])
    effectiveness = [torque[0], torque[1],
                     0.9*(maximum-minimum)*float(actuator.get("rotor_drag_per_collective_deg", 0.012))]
    bandwidth = ap.get("rate_bandwidth_radps", [10., 10., 8.])
    attitude = ap.get("attitude_p", [4., 4., 3.])
    for axis, name in enumerate(("RLL", "PIT", "YAW")):
        values[f"ATC_RAT_{name}_P"] = bandwidth[axis]*inertia[axis]/effectiveness[axis]
        values[f"ATC_RAT_{name}_FF"] = 0.0
        values[f"ATC_ANG_{name}_P"] = attitude[axis]
    flight = drone.get("flight", {})
    values["WPNAV_SPEED_UP"] = 100*float(flight.get("takeoff_speed_mps", 1.0))
    values["LAND_SPEED"] = 100*float(flight.get("landing_speed_mps", 0.3))
    values["LAND_SPEED_HIGH"] = values["LAND_SPEED"]
    values.update({name: float(value) for name, value in ap.get("parameter_overrides", {}).items()})
    return values


def write_parameters(settings, source, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    values = parameter_values(settings, source)
    destination.write_text(
        "# Generated MarsLab coaxial MVP; see docs/DRONE.md for every overridden policy.\n"
        + "".join(f"{name} {value:.9g}\n" for name, value in sorted(values.items())), encoding="utf-8")
    return destination


def require_mars_build(settings, source):
    metadata_path = build_metadata(source)
    if not metadata_path.is_file():
        raise RuntimeError("Build Mars-gravity SITL with scripts/build_ardupilot.sh first")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    gravity = float(settings["mars_env"]["gravity"])
    if (metadata.get("upstream_commit") != UPSTREAM_COMMIT
            or metadata.get("model_patch_revision") != MODEL_PATCH_REVISION
            or abs(metadata["gravity_mps2"]-gravity) > 1e-8):
        raise RuntimeError("SITL build does not match this config's gravity/version; rebuild with this YAML")
    binary = Path(source) / "build" / "sitl" / "bin" / "arducopter-heli"
    if not binary.is_file():
        raise RuntimeError(f"ArduPilot helicopter binary is missing: {binary}")
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "config.yaml"))
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    settings, source = read_settings(args.config), Path(args.source).expanduser().resolve()
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", "--branch", UPSTREAM_TAG,
                        "https://github.com/ArduPilot/ardupilot.git", str(source)], check=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if commit != UPSTREAM_COMMIT:
        raise RuntimeError(f"Use a separate {UPSTREAM_TAG} checkout; this checkout is {commit}")
    subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=source, check=True)
    gravity = float(settings["mars_env"]["gravity"])
    patch_gravity(source, gravity)
    subprocess.run(["./waf", "configure", "--board", "sitl", "--disable-tests"], cwd=source, check=True)
    subprocess.run(["./waf", "heli", "-j", str(args.jobs)], cwd=source, check=True)
    build_metadata(source).write_text(json.dumps({"upstream_commit": commit, "gravity_mps2": gravity,
                                                "model_patch_revision": MODEL_PATCH_REVISION},
                                               indent=2)+"\n", encoding="utf-8")
    parameters = write_parameters(settings, source, source.parent / "runtime" / "marslab.parm")
    print(f"Built ArduPilot helicopter SITL for gravity {gravity:g} m/s^2; defaults: {parameters}")


if __name__ == "__main__":
    main()
