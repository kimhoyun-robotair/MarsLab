#!/usr/bin/env -S zsh -f
if [[ ${ZSH_EVAL_CONTEXT} == *:file ]]; then
  print -u2 -- "Run this script as a command. Do not source it."
  return 1
fi
emulate -LR zsh
setopt ERR_EXIT NO_UNSET PIPE_FAIL
package_root=${0:A:h:h}
build_python="$package_root/.ardupilot/venv/bin/python"
if [[ ! -x "$build_python" ]]; then
  python3 -m venv "$package_root/.ardupilot/venv"
fi
"$build_python" -m pip install -r "$package_root/scripts/ardupilot_requirements.txt"
export PYTHONPATH="$package_root${PYTHONPATH:+:$PYTHONPATH}"
exec "$build_python" -m marslab.flight.ardupilot_setup --config "$package_root/configs/config.yaml" "$@"
