"""Scan each scenario YAML and diff its mars_env / rendering block vs master."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml


def flatten(d: dict, prefix: str = "") -> dict:
    """Flatten nested dict to dotted keys."""
    out: dict = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = v
    return out


def norm(v: object) -> object:
    """Normalise booleans and numeric types for comparison."""
    if isinstance(v, list):
        return tuple(norm(x) for x in v)
    if isinstance(v, bool):
        return bool(v)
    if isinstance(v, (int, float)):
        return float(v)
    return v


def diff(scenario: dict, master: dict) -> dict:
    """Return per-key status: 'same', 'override', 'scenario_only', 'master_only'."""
    fm = flatten(master)
    fs = flatten(scenario)
    keys = sorted(set(fm) | set(fs))
    rows = {}
    for k in keys:
        if k in fm and k in fs:
            rows[k] = "same" if norm(fm[k]) == norm(fs[k]) else f"override ({fs[k]!r} vs master {fm[k]!r})"
        elif k in fs:
            rows[k] = f"scenario_only ({fs[k]!r})"
        else:
            rows[k] = f"master_only ({fm[k]!r})"
    return rows


def main() -> None:
    master = yaml.safe_load(open("configs/mars_env.yaml"))
    master_me = master["mars_env"]
    master_rd = master["rendering"]

    scen_dir = Path("configs/scenarios")
    scens = sorted(scen_dir.glob("*.yaml"))

    for path in scens:
        data = yaml.safe_load(open(path))
        print(f"\n## {path.name}")
        me = data.get("mars_env", {})
        rd = data.get("rendering", {})

        print("### mars_env diff:")
        rows = diff(me, master_me)
        for k, status in rows.items():
            if status != "same":
                print(f"  {k}: {status}")

        print("### rendering diff:")
        rows = diff(rd, master_rd)
        for k, status in rows.items():
            if status != "same":
                print(f"  {k}: {status}")


if __name__ == "__main__":
    main()
