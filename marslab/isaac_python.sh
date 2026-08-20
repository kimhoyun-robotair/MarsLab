#!/bin/bash
# Launch Isaac Sim's bundled Python with a process-local ROS environment.
# Keep the ROS 2 Jazzy companion in its own terminal and use this wrapper for
# the single runtime command:
#   marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
# The wrapper leaves the caller's shell unchanged.

set -euo pipefail

_WRAPPER_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
_REPOSITORY_ROOT="$(cd -- "$_WRAPPER_DIR/.." && pwd -P)"

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

ISAAC_SIM_PATH="${ISAAC_SIM_PATH:-${HOME:-}/isaacsim}"
ISAAC_PY="$ISAAC_SIM_PATH/python.sh"
if [[ ! -x "$ISAAC_PY" ]]; then
    echo "[isaac_python] ERROR: Isaac Sim python.sh not found at $ISAAC_PY" >&2
    echo "[isaac_python] Set ISAAC_SIM_PATH or install Isaac Sim 5.x." >&2
    exit 1
fi

export ISAAC_SIM_PATH

_BUNDLED_ROS2_LIB="$ISAAC_SIM_PATH/exts/isaacsim.ros2.bridge/jazzy/lib"
if [[ ! -d "$_BUNDLED_ROS2_LIB" ]]; then
    echo "[isaac_python] ERROR: bundled ROS 2 lib dir not found: $_BUNDLED_ROS2_LIB" >&2
    echo "[isaac_python] Install Isaac Sim 5.x (ships jazzy by default)." >&2
    exit 1
fi
export LD_LIBRARY_PATH="${_BUNDLED_ROS2_LIB}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

exec "$ISAAC_PY" "$@"
