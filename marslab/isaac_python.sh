#!/bin/bash
# Thin wrapper that strips the user's system ROS 2 Jazzy environment
# BEFORE invoking Isaac Sim's python.sh. Do NOT edit ~/.bashrc -- this
# wrapper is process-local and leaves the user's shell untouched.
#
# Why this exists:
# The user's ~/.bashrc sources /opt/ros/jazzy/setup.bash, which sets
#   LD_LIBRARY_PATH=/opt/ros/jazzy/opt/*/lib:/opt/ros/jazzy/lib/...
#   PYTHONPATH=/opt/ros/jazzy/lib/python3.12/site-packages
#   AMENT_PREFIX_PATH=/opt/ros/jazzy
#   CMAKE_PREFIX_PATH=/opt/ros/jazzy/...
#   ROS_DISTRO=jazzy, ROS_VERSION=2, ROS_PYTHON_VERSION=3
# Isaac Sim 5.1 embeds CPython 3.11. The system ROS 2 Jazzy packages
# are built for Python 3.12 ABI and link against Python 3.12 symbols.
# Letting them leak into the Isaac Sim process produces two failure
# modes we have actually observed:
#
# Historical (Python side, fixed):
#   `import rclpy` resolves /opt/ros/jazzy/.../python3.12/.../rclpy,
#   which imports `_rclpy_pybind11.cpython-311-*.so`, which does not
#   exist -> ModuleNotFoundError -> Kit atexit SIGSEGV.
#
# Background (C side, fixed by this wrapper):
#   After sys.path was purged inside the Python entry script, the
#   import resolved to the Isaac Sim bundled rclpy under
#   $ISAAC_SIM_PATH/exts/isaacsim.ros2.bridge/jazzy, BUT the C dynamic
#   linker still saw LD_LIBRARY_PATH=/opt/ros/jazzy/... and loaded
#   /opt/ros/jazzy/lib/librcl_interfaces__rosidl_generator_py.so
#   (Python 3.12 ABI) into the Python 3.11 process. That .so tried
#   to convert a ParameterEvent PyObject* built from its 3.12 struct
#   layout against the 3.11 runtime type and abort()ed on the
#   assertion
#     strncmp("rcl_interfaces.msg._parameter_event.ParameterEvent",
#             full_classname_dest, 50) == 0
#   fired from rosidl_generator_py/rcl_interfaces/msg/_parameter_event_s.c:69.
#
# Because Python sys.path manipulation does not reach the dynamic
# linker, we must purge the environment BEFORE the Python process boots.
# ld.so consults LD_LIBRARY_PATH at exec-time (and dlopen-time) so this
# wrapper does the purge in the parent shell immediately before exec.
#
# Usage:
#   marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
#
# The wrapper invokes $ISAAC_SIM_PATH/python.sh.

set -euo pipefail

_WRAPPER_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
_REPOSITORY_ROOT="$(cd -- "$_WRAPPER_DIR/.." && pwd -P)"

# -----------------------------------------------------------------------------
# Strip a colon-separated PATH-like variable of entries starting with a prefix.
# Idempotent: safe to call on an unset or empty variable.
# -----------------------------------------------------------------------------
_purge_colon_path() {
    local varname="$1"
    local bad_prefix="$2"
    local old_val="${!varname:-}"
    if [[ -z "$old_val" ]]; then
        return 0
    fi
    local new_val=""
    local OLD_IFS="$IFS"
    IFS=':'
    for entry in $old_val; do
        if [[ "$entry" != "$bad_prefix"* ]]; then
            if [[ -z "$new_val" ]]; then
                new_val="$entry"
            else
                new_val="$new_val:$entry"
            fi
        fi
    done
    IFS="$OLD_IFS"
    export "$varname=$new_val"
}

_SYSTEM_ROS_PREFIX="/opt/ros"
_purge_colon_path LD_LIBRARY_PATH   "$_SYSTEM_ROS_PREFIX"
_purge_colon_path PYTHONPATH        "$_SYSTEM_ROS_PREFIX"
_purge_colon_path CMAKE_PREFIX_PATH "$_SYSTEM_ROS_PREFIX"
_purge_colon_path PKG_CONFIG_PATH   "$_SYSTEM_ROS_PREFIX"
_purge_colon_path PATH              "$_SYSTEM_ROS_PREFIX"

# Ament / ROS 2 scalar variables -- unset entirely.
unset AMENT_PREFIX_PATH
unset AMENT_CURRENT_PREFIX
unset COLCON_PREFIX_PATH
unset COLCON_CURRENT_PREFIX
unset ROS_DISTRO
unset ROS_VERSION
unset ROS_PYTHON_VERSION
unset ROS_AUTOMATIC_DISCOVERY_RANGE
unset RMW_IMPLEMENTATION
unset ROS_LOCALHOST_ONLY

export PYTHONPATH="$_REPOSITORY_ROOT"

# Resolve Isaac Sim python.sh. Let the user override the location via
# ISAAC_SIM_PATH when installing outside ~/isaacsim.
ISAAC_SIM_PATH="${ISAAC_SIM_PATH:-${HOME:-}/isaacsim}"
ISAAC_PY="$ISAAC_SIM_PATH/python.sh"
if [[ ! -x "$ISAAC_PY" ]]; then
    echo "[isaac_python] ERROR: Isaac Sim python.sh not found at $ISAAC_PY" >&2
    echo "[isaac_python] Set ISAAC_SIM_PATH or install Isaac Sim 5.x." >&2
    exit 1
fi

# Re-export ISAAC_SIM_PATH so marslab/main.py can pick up the same location
# when building its bundled rclpy path.
export ISAAC_SIM_PATH

# Background:
# After purging /opt/ros/jazzy from LD_LIBRARY_PATH we ALSO need to
# prepend the Isaac Sim-bundled ROS 2 lib directory. Without this, the
# dynamic linker can no longer find the bundle's own dependency chain
# (librmw_implementation.so -> libament_index_cpp.so, librcl_action.so,
# etc.) because those libs are NOT in /etc/ld.so.cache -- they live only
# inside the Isaac Sim extension tree. Symptom: the purge removed
# /opt/ros/jazzy pollution (good) but left LD_LIBRARY_PATH empty, which
# broke the bundle's self-dependency resolution. We target the jazzy
# distribution the bundle ships.
_BUNDLED_ROS2_LIB="$ISAAC_SIM_PATH/exts/isaacsim.ros2.bridge/jazzy/lib"
if [[ ! -d "$_BUNDLED_ROS2_LIB" ]]; then
    echo "[isaac_python] ERROR: bundled ROS 2 lib dir not found: $_BUNDLED_ROS2_LIB" >&2
    echo "[isaac_python] Install Isaac Sim 5.x (ships jazzy by default)." >&2
    exit 1
fi
export LD_LIBRARY_PATH="${_BUNDLED_ROS2_LIB}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

exec "$ISAAC_PY" "$@"
