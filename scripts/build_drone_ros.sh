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
unsetopt NO_UNSET
source /opt/ros/jazzy/setup.zsh
setopt NO_UNSET
command -v colcon >/dev/null || { print -u2 -- "Install python3-colcon-common-extensions."; exit 1; }
cd "$package_root/ros2_ws"
colcon build --symlink-install --packages-select ingenuity_ros
