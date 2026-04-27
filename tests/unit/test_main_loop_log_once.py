"""Unit tests for :func:`marslab.runtime.main_loop._log_once`.

Verifies the consolidated helper preserves the original behaviour:
emit during the leading grace window, stay silent afterwards. Also
guards the ``ERROR`` level contract so downstream log collectors keep
filtering on severity rather than message substrings.
"""

from __future__ import annotations

import logging

import pytest

from marslab.runtime.main_loop import _DEFAULT_GRACE_STEPS, _log_once

_MODULE_LOGGER_NAME = "marslab.runtime.main_loop"


def test_log_once_logs_during_grace_period(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Inside the default grace window every call emits one ERROR record."""
    caplog.set_level(logging.ERROR)
    caplog.set_level(logging.ERROR, logger=_MODULE_LOGGER_NAME)
    target_logger = logging.getLogger(_MODULE_LOGGER_NAME)
    target_logger.propagate = True
    exc = RuntimeError("articulation handle missing")

    _log_once(target_logger, exc, "joint_target_set_failed", step_count=0)
    _log_once(target_logger, exc, "joint_target_set_failed", step_count=42)
    _log_once(
        target_logger,
        exc,
        "joint_target_set_failed",
        step_count=_DEFAULT_GRACE_STEPS - 1,
    )

    assert len(caplog.records) == 3
    for record in caplog.records:
        assert record.levelno == logging.ERROR
        assert "joint_target_set_failed" in record.getMessage()
        assert "RuntimeError('articulation handle missing')" in record.getMessage()


def test_log_once_silent_after_grace_period(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """At or beyond the grace boundary the helper must stay silent."""
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger=_MODULE_LOGGER_NAME)
    target_logger = logging.getLogger(_MODULE_LOGGER_NAME)
    target_logger.propagate = True
    exc = ValueError("imu frame empty")

    _log_once(
        target_logger,
        exc,
        "imu_frame_fetch_failed",
        step_count=_DEFAULT_GRACE_STEPS,
    )
    _log_once(
        target_logger,
        exc,
        "imu_frame_fetch_failed",
        step_count=_DEFAULT_GRACE_STEPS + 10_000,
    )

    assert caplog.records == []


def test_log_once_respects_custom_grace(caplog: pytest.LogCaptureFixture) -> None:
    """An explicit ``grace_steps`` overrides the module default."""
    caplog.set_level(logging.ERROR)
    caplog.set_level(logging.ERROR, logger=_MODULE_LOGGER_NAME)
    target_logger = logging.getLogger(_MODULE_LOGGER_NAME)
    target_logger.propagate = True
    exc = OSError("transient sensor read")

    _log_once(target_logger, exc, "velocity_query_failed", step_count=4, grace_steps=5)
    _log_once(target_logger, exc, "velocity_query_failed", step_count=5, grace_steps=5)
    _log_once(target_logger, exc, "velocity_query_failed", step_count=6, grace_steps=5)

    assert len(caplog.records) == 1
    assert "velocity_query_failed (step=4)" in caplog.records[0].getMessage()


def test_log_once_uses_error_level(caplog: pytest.LogCaptureFixture) -> None:
    """Level must be ``ERROR`` so log retention policies honour the signal."""
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger=_MODULE_LOGGER_NAME)
    target_logger = logging.getLogger(_MODULE_LOGGER_NAME)
    target_logger.propagate = True
    exc = Exception("odom publish dropped")

    _log_once(target_logger, exc, "odom_publish_failed", step_count=1)

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "ERROR"
    assert record.name == _MODULE_LOGGER_NAME
