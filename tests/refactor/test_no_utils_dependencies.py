from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from marslab.main import _PRE_S05_ROVER_USD_PATH, _abs_repo_path, _load_rover_cfg

REPO_ROOT = Path(__file__).resolve().parents[2]
ROVER_YAML = REPO_ROOT / "configs" / "rover_m2020.yaml"
FORBIDDEN_RUNTIME_TEXT = (
    "MarsLab-Utils",
    "/home/hoyunkim",
    "trajectory_start",
    "trajectory_path",
    "gt_publisher",
)
CONVERSION_MODULES = {"convert_urdf_to_usd.py", "fix_urdf_inertia.py"}


def test_legacy_cli_accepts_current_s01_interface() -> None:
    # Given: the supported pre-S06 script entry point.
    command = [sys.executable, str(REPO_ROOT / "marslab" / "main.py"), "--help"]

    # When: an operator asks argparse for the current interface.
    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, check=False)

    # Then: parsing succeeds and the three retained input flags are advertised.
    assert result.returncode == 0, result.stderr
    assert all(flag in result.stdout for flag in ("--usda", "--scenario", "--rover-yaml"))


def test_rover_yaml_still_resolves_rover_usd() -> None:
    # Given: the canonical Rover YAML.
    config = _load_rover_cfg(str(ROVER_YAML))

    # When: its Rover USD input is resolved through the current resolver.
    resolved = Path(_abs_repo_path(_PRE_S05_ROVER_USD_PATH))

    # Then: it points at the checked-in Rover USD until S05 changes ownership.
    assert config.spawn.mode == "dem_center"
    assert resolved == REPO_ROOT / "assets" / "robots" / "rover" / "m2020.usd"
    assert resolved.is_file()


def test_removed_trajectory_start_fails_before_kit(tmp_path: Path) -> None:
    # Given: a Rover config requesting the removed trajectory-driven spawn mode.
    config = yaml.safe_load(ROVER_YAML.read_text(encoding="utf-8"))
    config["spawn"] = {"mode": "trajectory_start", "trajectory_path": "route.tum"}
    rover_yaml = tmp_path / "rover.yaml"
    rover_yaml.write_text(yaml.safe_dump(config), encoding="utf-8")

    # When/Then: the offline Rover-config boundary rejects it by name.
    with pytest.raises(ValidationError, match="trajectory_start"):
        _load_rover_cfg(str(rover_yaml))


def test_production_runtime_has_no_forbidden_dependencies() -> None:
    # Given: production Python/config files, excluding the retained offline converters.
    files = [
        *(
            path
            for path in (REPO_ROOT / "marslab").rglob("*.py")
            if path.name not in CONVERSION_MODULES
        ),
        *(REPO_ROOT / "configs").rglob("*.yaml"),
    ]

    # When: their source text is inspected as shipped.
    hits = {
        str(path.relative_to(REPO_ROOT)): token
        for path in files
        for token in FORBIDDEN_RUNTIME_TEXT
        if token in path.read_text(encoding="utf-8")
    }

    # Then: no runtime path names an external checkout or removed behavior.
    assert hits == {}


def test_runtime_does_not_import_conversion_modules() -> None:
    # Given: every production module other than the standalone conversion tools.
    files = [
        path
        for path in (REPO_ROOT / "marslab").rglob("*.py")
        if path.name not in CONVERSION_MODULES
    ]

    # When: import statements are inspected.
    imports = {
        str(path.relative_to(REPO_ROOT)): line.strip()
        for path in files
        for line in path.read_text(encoding="utf-8").splitlines()
        if any(module.removesuffix(".py") in line for module in CONVERSION_MODULES)
    }

    # Then: the offline conversion tools are not runtime dependencies.
    assert imports == {}
