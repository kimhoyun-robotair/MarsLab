"""Unit tests for :class:`marslab.config.schema.robot.DepthSensorConfig`.

Path 2 of the Camera depth pipeline.  The schema describes the
realistic stereo-disparity simulation parameters that map onto the
``OmniSensorDepthSensorSingleViewAPI`` USD schema; the runtime
applies those attributes to the camera render product so the depth
output simulates a stereo pair (RealSense-style noise + occlusion
holes + confidence map) instead of the renderer's noiseless
``DistanceToImagePlane`` AOV.

Schema source: ``isaacsim/extscache/
omni.usd.schema.omni_sensors-0.0.0+69cbf6ad/usd_plugins/
generatedSchema.usda`` (``OmniSensorDepthSensorSingleViewAPI``).

These tests exercise pure pydantic validation, no Isaac Sim required.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestDepthSensorConfigDefaults:
    """``DepthSensorConfig`` instantiates with RealSense D455-ballpark defaults."""

    def test_defaults_match_realsense_d455(self) -> None:
        from marslab.config.schema.robot import DepthSensorConfig

        cfg = DepthSensorConfig()
        # Default: disabled (preserves v0.7 / v1.0 raw-depth behaviour).
        assert cfg.enabled is False
        # RealSense D455 baseline = 55 mm.
        assert cfg.baseline_mm == 55.0
        # Reasonable indoor / near-field defaults.
        assert cfg.min_distance_m == 0.3
        assert cfg.max_distance_m == 10.0
        assert cfg.noise_mean == 0.0
        assert cfg.noise_sigma == 0.005
        assert cfg.confidence_threshold == 0.95
        assert cfg.max_disparity_pixel == 110.0

    def test_explicit_enable_accepted(self) -> None:
        from marslab.config.schema.robot import DepthSensorConfig

        cfg = DepthSensorConfig(enabled=True, baseline_mm=420.0)
        assert cfg.enabled is True
        assert cfg.baseline_mm == 420.0


class TestDepthSensorConfigForbidsExtra:
    """``extra='forbid'`` rejects misspelled YAML keys at load time."""

    def test_unknown_key_rejected(self) -> None:
        from marslab.config.schema.robot import DepthSensorConfig

        with pytest.raises(ValidationError):
            DepthSensorConfig(baseline_milimeters=55.0)  # typo

    def test_typoed_threshold_rejected(self) -> None:
        from marslab.config.schema.robot import DepthSensorConfig

        with pytest.raises(ValidationError):
            DepthSensorConfig(confidance_threshold=0.95)  # typo


class TestDepthSensorConfigBounds:
    """Numeric bounds reject obviously wrong values at load time."""

    def test_baseline_below_minimum_rejected(self) -> None:
        from marslab.config.schema.robot import DepthSensorConfig

        with pytest.raises(ValidationError):
            DepthSensorConfig(baseline_mm=0.5)

    def test_baseline_above_maximum_rejected(self) -> None:
        from marslab.config.schema.robot import DepthSensorConfig

        with pytest.raises(ValidationError):
            DepthSensorConfig(baseline_mm=600.0)

    def test_confidence_threshold_above_one_rejected(self) -> None:
        from marslab.config.schema.robot import DepthSensorConfig

        with pytest.raises(ValidationError):
            DepthSensorConfig(confidence_threshold=1.5)

    def test_confidence_threshold_below_zero_rejected(self) -> None:
        from marslab.config.schema.robot import DepthSensorConfig

        with pytest.raises(ValidationError):
            DepthSensorConfig(confidence_threshold=-0.1)

    def test_negative_noise_sigma_rejected(self) -> None:
        from marslab.config.schema.robot import DepthSensorConfig

        with pytest.raises(ValidationError):
            DepthSensorConfig(noise_sigma=-0.01)

    def test_zero_max_distance_rejected(self) -> None:
        from marslab.config.schema.robot import DepthSensorConfig

        with pytest.raises(ValidationError):
            DepthSensorConfig(max_distance_m=0.0)

    def test_zero_max_disparity_rejected(self) -> None:
        from marslab.config.schema.robot import DepthSensorConfig

        with pytest.raises(ValidationError):
            DepthSensorConfig(max_disparity_pixel=0.0)

    def test_max_distance_must_exceed_min_distance(self) -> None:
        from marslab.config.schema.robot import DepthSensorConfig

        with pytest.raises(ValidationError):
            DepthSensorConfig(min_distance_m=10.0, max_distance_m=5.0)


class TestCameraConfigDepthSensorIntegration:
    """``CameraConfig.depth_sensor`` is optional and accepts a ``DepthSensorConfig``."""

    @pytest.fixture
    def base_camera_kwargs(self) -> dict:
        return {
            "local_translation": [0.3, 0.0, -2.1],
            "resolution": [640, 480],
            "focal_length": 24.0,
            "clipping_range": [0.1, 1000.0],
        }

    def test_camera_without_depth_sensor_block(self, base_camera_kwargs: dict) -> None:
        """Existing scenarios that omit the block keep validating cleanly."""
        from marslab.config.schema.robot import CameraConfig

        cfg = CameraConfig(**base_camera_kwargs)
        assert cfg.depth_sensor is None

    def test_camera_with_depth_sensor_block(self, base_camera_kwargs: dict) -> None:
        from marslab.config.schema.robot import CameraConfig

        cfg = CameraConfig(
            **base_camera_kwargs,
            depth_sensor={
                "enabled": True,
                "baseline_mm": 420.0,
                "min_distance_m": 0.5,
                "max_distance_m": 50.0,
            },
        )
        assert cfg.depth_sensor is not None
        assert cfg.depth_sensor.enabled is True
        assert cfg.depth_sensor.baseline_mm == 420.0

    def test_camera_with_invalid_depth_sensor_block_rejected(
        self, base_camera_kwargs: dict
    ) -> None:
        from marslab.config.schema.robot import CameraConfig

        with pytest.raises(ValidationError):
            CameraConfig(
                **base_camera_kwargs,
                depth_sensor={"enabled": True, "baseline_mm": 9999.0},  # exceeds upper bound
            )


class TestRoverYamlRoundTrip:
    """The shipped rover_m2020.yaml carries a default-disabled depth_sensor block."""

    def test_yaml_block_loads_via_camera_schema(self) -> None:
        """The YAML defaults match :class:`DepthSensorConfig` defaults."""
        import yaml

        from marslab.config.schema.robot import CameraConfig

        with open("configs/robots/rover_m2020.yaml") as fp:
            rover_yaml = yaml.safe_load(fp)

        camera_block = rover_yaml["sensors"]["camera"]
        cfg = CameraConfig.model_validate(camera_block)
        assert cfg.depth_sensor is not None
        # YAML-shipped block defaults to disabled to preserve current behaviour.
        assert cfg.depth_sensor.enabled is False
        assert cfg.depth_sensor.baseline_mm == 55.0
