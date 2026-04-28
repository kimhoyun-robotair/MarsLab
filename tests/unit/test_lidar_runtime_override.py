"""Unit tests for ``_apply_lidar_runtime_overrides``.

Verifies that yaml ``range_min``/``range_max``/``rotation_rate_hz`` /
``horizontal_fov_deg``/``vertical_fov_deg`` scalars land on the
correct ``OmniSensorGenericLidarCoreAPI`` USD attributes after the
RTX LiDAR profile loads.  The OmniLidar prim is mocked so the test
runs without Isaac Sim on the path -- it pins the schema attribute
*names* and the centering / remap arithmetic, not the runtime
behaviour of Isaac Sim itself.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from marslab.sensors.sensor_spawner import _apply_lidar_runtime_overrides

# ---------------------------------------------------------------------------
# Minimal mock USD prim / stage
# ---------------------------------------------------------------------------


class _MockAttribute:
    """Records the most recent ``Set(value)`` call and parrots ``Get()``."""

    def __init__(self, initial: Any = None) -> None:
        self._value = initial

    def Get(self) -> Any:
        return self._value

    def Set(self, value: Any) -> None:
        self._value = value


class _MockPrim:
    """Stub OmniLidar prim that lazily creates ``_MockAttribute`` slots."""

    def __init__(
        self,
        valid: bool = True,
        elevation_array: List[float] | None = None,
    ) -> None:
        self._valid = valid
        self._attrs: Dict[str, _MockAttribute] = {}
        if elevation_array is not None:
            self._attrs["omni:sensor:Core:emitterState:s001:elevationDeg"] = _MockAttribute(
                list(elevation_array)
            )

    def IsValid(self) -> bool:
        return self._valid

    def GetAttribute(self, name: str) -> _MockAttribute:
        if name not in self._attrs:
            self._attrs[name] = _MockAttribute()
        return self._attrs[name]


class _MockStage:
    """Returns one ``_MockPrim`` keyed by path."""

    def __init__(self, prim_by_path: Dict[str, _MockPrim]) -> None:
        self._prim_by_path = prim_by_path

    def GetPrimAtPath(self, path: str) -> _MockPrim | None:
        return self._prim_by_path.get(path)


def _full_lidar_cfg(**overrides: Any) -> Dict[str, Any]:
    """Return a yaml-shaped lidar block with every override field present."""
    base: Dict[str, Any] = {
        "range_min": 0.5,
        "range_max": 30.0,
        "rotation_rate_hz": 10,
        "horizontal_fov_deg": 360.0,
        "vertical_fov_deg": 30.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScalarOverrides:
    """range_min / range_max / rotation_rate_hz are written to the schema attrs."""

    def test_range_min_written_to_near_range_m(self) -> None:
        prim = _MockPrim(elevation_array=[-15.0, 0.0, 10.0])
        stage = _MockStage({"/lidar": prim})
        _apply_lidar_runtime_overrides(stage, "/lidar", _full_lidar_cfg(range_min=2.5))
        assert prim.GetAttribute("omni:sensor:Core:nearRangeM").Get() == 2.5

    def test_range_max_written_to_far_range_m(self) -> None:
        prim = _MockPrim(elevation_array=[-15.0, 0.0, 10.0])
        stage = _MockStage({"/lidar": prim})
        _apply_lidar_runtime_overrides(stage, "/lidar", _full_lidar_cfg(range_max=42.0))
        assert prim.GetAttribute("omni:sensor:Core:farRangeM").Get() == 42.0

    def test_rotation_rate_cast_to_int(self) -> None:
        """``scanRateBaseHz`` is a uint in the schema -- cast from float yaml."""
        prim = _MockPrim(elevation_array=[-15.0, 0.0, 10.0])
        stage = _MockStage({"/lidar": prim})
        _apply_lidar_runtime_overrides(stage, "/lidar", _full_lidar_cfg(rotation_rate_hz=15.7))
        result = prim.GetAttribute("omni:sensor:Core:scanRateBaseHz").Get()
        assert result == 15
        assert isinstance(result, int)


class TestHorizontalFov:
    """``horizontal_fov_deg`` controls validStart/EndAzimuthDeg."""

    def test_full_360_yields_full_sweep(self) -> None:
        prim = _MockPrim(elevation_array=[-15.0, 0.0, 10.0])
        stage = _MockStage({"/lidar": prim})
        _apply_lidar_runtime_overrides(stage, "/lidar", _full_lidar_cfg(horizontal_fov_deg=360.0))
        assert prim.GetAttribute("omni:sensor:Core:validStartAzimuthDeg").Get() == 0.0
        assert prim.GetAttribute("omni:sensor:Core:validEndAzimuthDeg").Get() == 360.0

    def test_270_yields_front_centered_sweep(self) -> None:
        """fov=270 -> [225, 135], i.e. 90° dead zone behind the rover."""
        prim = _MockPrim(elevation_array=[-15.0, 0.0, 10.0])
        stage = _MockStage({"/lidar": prim})
        _apply_lidar_runtime_overrides(stage, "/lidar", _full_lidar_cfg(horizontal_fov_deg=270.0))
        start = prim.GetAttribute("omni:sensor:Core:validStartAzimuthDeg").Get()
        end = prim.GetAttribute("omni:sensor:Core:validEndAzimuthDeg").Get()
        assert start == pytest.approx(225.0)
        assert end == pytest.approx(135.0)

    def test_180_yields_front_hemisphere(self) -> None:
        """fov=180 -> [270, 90], rover front ±90°."""
        prim = _MockPrim(elevation_array=[-15.0, 0.0, 10.0])
        stage = _MockStage({"/lidar": prim})
        _apply_lidar_runtime_overrides(stage, "/lidar", _full_lidar_cfg(horizontal_fov_deg=180.0))
        start = prim.GetAttribute("omni:sensor:Core:validStartAzimuthDeg").Get()
        end = prim.GetAttribute("omni:sensor:Core:validEndAzimuthDeg").Get()
        assert start == pytest.approx(270.0)
        assert end == pytest.approx(90.0)


class TestVerticalFovRemap:
    """``vertical_fov_deg`` linearly remaps the elevation array."""

    def test_remap_compresses_vertical_span(self) -> None:
        """Default 30° (-15..+10, 25° span actually, mid -2.5°) -> yaml 15° -> half-scale."""
        elevation = [-15.0, -7.5, 0.0, 5.0, 10.0]
        prim = _MockPrim(elevation_array=elevation)
        stage = _MockStage({"/lidar": prim})
        _apply_lidar_runtime_overrides(stage, "/lidar", _full_lidar_cfg(vertical_fov_deg=12.5))
        new_array = prim.GetAttribute("omni:sensor:Core:emitterState:s001:elevationDeg").Get()
        # Original span 25°, target 12.5° -> scale 0.5; centred on -2.5°.
        # Original entries map to (e - (-2.5)) * 0.5.
        expected = [(e - (-2.5)) * 0.5 for e in elevation]
        assert new_array == pytest.approx(expected, abs=1e-9)

    def test_remap_preserves_array_length(self) -> None:
        """Channel count is encoded in array length and must not change."""
        elevation = [-15.0, -10.0, -5.0, 0.0, 5.0, 10.0]
        prim = _MockPrim(elevation_array=elevation)
        stage = _MockStage({"/lidar": prim})
        _apply_lidar_runtime_overrides(stage, "/lidar", _full_lidar_cfg(vertical_fov_deg=10.0))
        new_array = prim.GetAttribute("omni:sensor:Core:emitterState:s001:elevationDeg").Get()
        assert len(new_array) == len(elevation)

    def test_remap_skipped_when_vertical_fov_absent(self) -> None:
        """Lidar2DConfig has no vertical_fov_deg key; helper must no-op the array."""
        elevation = [-1.0, 0.0, 1.0]
        prim = _MockPrim(elevation_array=elevation)
        stage = _MockStage({"/lidar": prim})
        cfg = _full_lidar_cfg()
        cfg.pop("vertical_fov_deg")
        _apply_lidar_runtime_overrides(stage, "/lidar", cfg)
        new_array = prim.GetAttribute("omni:sensor:Core:emitterState:s001:elevationDeg").Get()
        assert new_array == elevation

    def test_remap_skipped_when_existing_array_empty(self) -> None:
        """Profile without an emitter elevation array -> no-op (scalar attrs only)."""
        prim = _MockPrim(elevation_array=[])
        stage = _MockStage({"/lidar": prim})
        _apply_lidar_runtime_overrides(stage, "/lidar", _full_lidar_cfg())
        # Scalar attrs still applied.
        assert prim.GetAttribute("omni:sensor:Core:nearRangeM").Get() == 0.5
        # Elevation array left empty.
        assert prim.GetAttribute("omni:sensor:Core:emitterState:s001:elevationDeg").Get() == []


class TestPrimValidation:
    def test_missing_prim_raises(self) -> None:
        stage = _MockStage({})
        with pytest.raises(RuntimeError, match="OmniLidar prim not found"):
            _apply_lidar_runtime_overrides(stage, "/lidar", _full_lidar_cfg())

    def test_invalid_prim_raises(self) -> None:
        prim = _MockPrim(valid=False)
        stage = _MockStage({"/lidar": prim})
        with pytest.raises(RuntimeError, match="OmniLidar prim not found"):
            _apply_lidar_runtime_overrides(stage, "/lidar", _full_lidar_cfg())
