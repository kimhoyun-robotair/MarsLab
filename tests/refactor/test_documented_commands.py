from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPOSITORY_ROOT / "README.md"
DOCUMENTED_COMMAND_PATHS = (
    "assets/scene/jezero_plain/jezero_plain.usdz",
    "configs/default.yaml",
    "configs/rover_m2020.yaml",
)
SCAN_PATHS = ("README.md", "configs", "AGENTS.md", "marslab")
LEGACY_USDA_ALLOWLIST = {
    "README.md",
    "AGENTS.md",
    "configs/default.yaml",
    "marslab/isaac_python.sh",
    "marslab/main.py",
}


def _assert_existing_target(repository_root: Path, documented_path: str) -> None:
    target = repository_root / documented_path
    assert target.exists(), f"documented target is missing: {documented_path} ({target})"


def test_readme_documents_existing_legacy_runtime_command() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "MarsLab-Utils" not in readme
    assert "/home/hoyunkim" not in readme
    assert "marslab/isaac_python.sh marslab/main.py" in readme
    assert "--usda assets/scene/jezero_plain/jezero_plain.usdz" in readme

    for documented_path in DOCUMENTED_COMMAND_PATHS:
        _assert_existing_target(REPOSITORY_ROOT, documented_path)


def test_readme_local_markdown_links_are_tracked() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    documented_paths = set(re.findall(r"\]\(([^)#]+)\)", readme))

    assert documented_paths, "README must retain at least one checked local documentation target"
    for documented_path in documented_paths:
        _assert_existing_target(REPOSITORY_ROOT, documented_path)
        tracked = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if tracked.returncode == 0:
            tracked = subprocess.run(
                ["git", "ls-files", "--error-unmatch", documented_path],
                cwd=REPOSITORY_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            assert tracked.returncode == 0, f"documented target is not tracked: {documented_path}"


def test_current_help_preserves_legacy_usda_flag() -> None:
    result = subprocess.run(
        [sys.executable, "marslab/main.py", "--help"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--usda" in result.stdout


def test_maintained_text_has_no_external_or_personal_path() -> None:
    result = subprocess.run(
        ["rg", "-n", "MarsLab-Utils|/home/hoyunkim", *SCAN_PATHS],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, result.stdout


def test_legacy_usda_references_are_allowlisted() -> None:
    result = subprocess.run(
        ["rg", "-l", "--", "--usda", *SCAN_PATHS],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    observed_paths = set(result.stdout.splitlines())
    assert observed_paths <= LEGACY_USDA_ALLOWLIST, observed_paths - LEGACY_USDA_ALLOWLIST


def test_missing_target_fixture() -> None:
    with pytest.raises(
        AssertionError, match=r"documented target is missing: docs/missing-target-fixture.md"
    ):
        _assert_existing_target(REPOSITORY_ROOT, "docs/missing-target-fixture.md")
