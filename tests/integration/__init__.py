"""Integration test package.

These tests require a functioning Isaac Sim installation plus a GPU
and are skipped by default in ``pytest tests/unit/`` runs. Invoke
them through ``scripts/run_integration_test.py`` (wraps
``scripts/isaac_python.sh``).

Per-test scaffolding uses ``pytest.importorskip("isaacsim")`` so a
plain ``python3 -m pytest tests/integration/`` on a ROS2-only host
does NOT crash -- it skips cleanly with a readable reason.
"""
