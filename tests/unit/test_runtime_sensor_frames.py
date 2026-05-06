"""Offline unit tests for ``marslab.runtime.sensor_frames``."""

from __future__ import annotations

from marslab.runtime.sensor_frames import (
    build_sensor_frames,
    sensor_frames_to_tuples,
)


def _full_sensors_cfg() -> dict:
    """Return a sensor block that exercises all four sensor types."""
    return {
        "camera": {
            "local_translation": [0.30, 0.10, -0.40],
            "local_orientation_rpy_deg": [0.0, 15.0, 0.0],
        },
        "lidar_3d": {
            "local_translation": [0.20, 0.00, -0.55],
            "local_orientation_rpy_deg": [0.0, 0.0, 0.0],
        },
        "lidar_2d": {
            "local_translation": [0.50, 0.00, -0.30],
            "local_orientation_rpy_deg": [0.0, 0.0, 90.0],
        },
        "imu": {
            "local_translation": [0.00, 0.00, -0.10],
            "local_orientation_rpy_deg": [0.0, 0.0, 0.0],
        },
    }


def test_build_sensor_frames_full_set() -> None:
    """All four sensors present -> 4 frame dicts in canonical order."""
    sensors_cfg = _full_sensors_cfg()
    frames = build_sensor_frames(sensors_cfg)

    child_frames = [f["child_frame"] for f in frames]
    assert child_frames == ["camera_link", "lidar_link", "scan_frame", "imu_link"]
    for frame in frames:
        assert len(frame["local_translation"]) == 3
        assert len(frame["local_orientation_rpy_deg"]) == 3


def test_build_sensor_frames_legacy_lidar_alias() -> None:
    """``sensors.lidar`` is accepted as an alias for ``sensors.lidar_3d``."""
    sensors_cfg = {
        "camera": {
            "local_translation": [0.0, 0.0, 0.0],
        },
        "lidar": {  # legacy alias
            "local_translation": [0.1, 0.2, 0.3],
        },
        "imu": {
            "local_translation": [0.0, 0.0, 0.0],
        },
    }
    frames = build_sensor_frames(sensors_cfg)
    lidar_frames = [f for f in frames if f["child_frame"] == "lidar_link"]
    assert len(lidar_frames) == 1
    assert lidar_frames[0]["local_translation"] == [0.1, 0.2, 0.3]


def test_build_sensor_frames_default_rpy() -> None:
    """Missing ``local_orientation_rpy_deg`` defaults to ``[0, 0, 0]``."""
    sensors_cfg = {
        "camera": {"local_translation": [0.0, 0.0, 0.0]},
    }
    frames = build_sensor_frames(sensors_cfg)
    assert len(frames) == 1
    assert frames[0]["local_orientation_rpy_deg"] == [0.0, 0.0, 0.0]


def test_build_sensor_frames_skips_missing_sensors() -> None:
    """Absent sensor keys produce no entries (silent skip)."""
    sensors_cfg = {
        "camera": {"local_translation": [0.0, 0.0, 0.0]},
        # lidar_3d, lidar_2d, imu intentionally absent
    }
    frames = build_sensor_frames(sensors_cfg)
    assert [f["child_frame"] for f in frames] == ["camera_link"]


def test_build_sensor_frames_preserves_translation_order() -> None:
    """``local_translation`` is copied verbatim (no implicit Y/Z flip)."""
    xyz = [0.123, -0.456, 0.789]
    sensors_cfg = {"camera": {"local_translation": xyz}}
    frames = build_sensor_frames(sensors_cfg)
    assert frames[0]["local_translation"] == xyz


def test_build_sensor_frames_skips_block_without_translation() -> None:
    """A sensor block without ``local_translation`` is skipped."""
    sensors_cfg = {
        "camera": {"local_translation": [0.0, 0.0, 0.0]},
        # IMU block present but malformed (no translation): skipped, not raised
        "imu": {"local_orientation_rpy_deg": [0.0, 0.0, 0.0]},
    }
    frames = build_sensor_frames(sensors_cfg)
    assert [f["child_frame"] for f in frames] == ["camera_link"]


def test_sensor_frames_to_tuples_round_trip() -> None:
    """Adapter outputs ``(child_frame, xyz, rpy_deg)`` 3-tuples.

    ``tf_broadcaster.build_static_sensor_transforms`` consumes the
    3-tuple shape so the YAML ``local_orientation_rpy_deg`` reaches
    the broadcast quaternion -- a 2-tuple (identity rotation) leaves
    camera_link inheriting the Body_Chassis graphics-style axis and
    the depth_pcl PointCloud2 surfaces in RViz pointing at the sky
    (NVIDIA Forum: "Incorrect orientation of data from depth_pcl").
    """
    frames = build_sensor_frames(_full_sensors_cfg())
    tuples = sensor_frames_to_tuples(frames)
    assert tuples == [
        ("camera_link", [0.30, 0.10, -0.40], [0.0, 15.0, 0.0]),
        ("lidar_link", [0.20, 0.00, -0.55], [0.0, 0.0, 0.0]),
        ("scan_frame", [0.50, 0.00, -0.30], [0.0, 0.0, 90.0]),
        ("imu_link", [0.00, 0.00, -0.10], [0.0, 0.0, 0.0]),
    ]


def test_sensor_frames_to_tuples_default_rpy_when_missing() -> None:
    """Adapter falls back to [0,0,0] when local_orientation_rpy_deg absent.

    ``build_sensor_frames`` already injects [0,0,0] into the dict when
    the YAML key omits the field, but the adapter's ``.get`` default
    is the canonical safety net for hand-built dicts feeding the
    static broadcaster directly.
    """
    frames = [
        {"child_frame": "camera_link", "local_translation": [1.0, 2.0, 3.0]},
    ]
    tuples = sensor_frames_to_tuples(frames)
    assert tuples == [("camera_link", [1.0, 2.0, 3.0], [0.0, 0.0, 0.0])]
