#!/usr/bin/env python3
"""Run integration tests requiring Isaac Sim.

This entry point is intended to be launched via the Isaac Sim Python
runtime wrapper ``scripts/isaac_python.sh``.  It strips
``-m 'not integration'`` from the pyproject ``addopts`` and runs
exactly the ``integration``-marked suite, so the default
``pytest tests/unit/`` remains GPU-free.

Usage::

    # Run all integration tests
    scripts/isaac_python.sh scripts/run_integration_test.py

    # Run a single file
    scripts/isaac_python.sh scripts/run_integration_test.py \
        tests/integration/test_imu_gravity_actual.py

    # Run a single test by nodeid
    scripts/isaac_python.sh scripts/run_integration_test.py \
        tests/integration/test_imu_gravity_actual.py::test_imu_z_gravity_within_mars_band

If you bypass ``scripts/isaac_python.sh`` and invoke with system Python,
every integration test is reported SKIPPED with a readable reason
(``pytest.importorskip("isaacsim")`` gate).  That mode is safe but
useless -- the whole point of these tests is to exercise Isaac Sim.
"""

from __future__ import annotations

import os
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_TARGET = REPO_ROOT / "tests" / "integration"


def main() -> int:
    """Invoke pytest on the integration suite with ``-m integration``."""
    import pytest  # deferred: keep top-level importable even without pytest

    targets = sys.argv[1:] or [str(DEFAULT_TARGET)]

    # Ensure the repo root is on sys.path so ``marslab`` imports resolve
    # under Isaac Sim's bundled Python, which does not install the repo
    # as an editable package by default.
    sys.path.insert(0, str(REPO_ROOT))
    os.environ.setdefault("PYTHONPATH", str(REPO_ROOT))

    args = ["-v", "-m", "integration", "--override-ini", "addopts=", *targets]
    return pytest.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
