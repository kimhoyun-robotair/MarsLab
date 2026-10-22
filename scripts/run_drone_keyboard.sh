#!/usr/bin/env -S zsh -f
if [[ ${ZSH_EVAL_CONTEXT} == *:file ]]; then
  print -u2 -- "Run this script as a command. Do not source it."
  return 1
fi
emulate -LR zsh
setopt ERR_EXIT NO_UNSET PIPE_FAIL
package_root=${0:A:h:h}
if [[ ! -f /opt/ros/jazzy/setup.zsh ]]; then
  print -u2 -- "Install ROS 2 Jazzy on Ubuntu 24.04 first."
  exit 1
fi
if [[ ! -f "$package_root/ros2_ws/install/setup.zsh" ]]; then
  print -u2 -- "Run scripts/build_drone_ros.sh first."
  exit 1
fi
unsetopt NO_UNSET
source /opt/ros/jazzy/setup.zsh
source "$package_root/ros2_ws/install/setup.zsh"
setopt NO_UNSET
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
exec ros2 run ingenuity_ros keyboard --ros-args -p use_sim_time:=true "$@"
