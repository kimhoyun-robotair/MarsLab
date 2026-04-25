"""Sprint Day 4-5 Task I-B (2026-04-25): M2020 calibrated sensor presets.

These tests cover the two new Camera presets in ``configs/sensors/``:

* ``m2020_navcam.yaml`` — RSM-mounted Navigation Camera (LEFT).
* ``m2020_hazcam.yaml`` — chassis-mounted FRONT-LEFT Hazard Camera.

Acceptance criteria (Reviewer 2):

1. Both YAMLs round-trip cleanly through
   :class:`marslab.config.schema.robot.CameraConfig` (extra='forbid', so
   typos fail at load time).
2. The numerical values match Maki et al. 2020 Tables 2 + 3 to within the
   geometric-vs-diagonal FOV reconciliation documented in the YAML
   comments and ``~/MarsLab/tmp/task_IB_finding.md``.
3. Both presets share the M2020 detector format (5120 × 3840 full /
   1280 × 960 binned 4×) — the resolutions in the preset are a valid
   subset of the flight detector.
4. Focal lengths are positive and inside the M2020 envelope (1 mm <= f
   <= 50 mm — the M2020 mast cameras Mastcam-Z go up to 110 mm but
   engineering cameras stay short).
5. Clipping ranges are well-formed (near > 0, far > near).
6. Mount transforms are well-formed (3-element translation, 3-element
   RPY in degrees, no NaNs).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from marslab.config.schema.robot import CameraConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
SENSORS_DIR = REPO_ROOT / "configs" / "sensors"
NAVCAM_YAML = SENSORS_DIR / "m2020_navcam.yaml"
HAZCAM_YAML = SENSORS_DIR / "m2020_hazcam.yaml"

# M2020 detector format (Maki et al. 2020 Table 2).  Both engineering
# camera families (Navcam + Hazcam) share the same 5120 x 3840 RGB Bayer
# detector with 4.6 um pixel pitch.
FULL_DETECTOR_W = 5120
FULL_DETECTOR_H = 3840
BINNED_DETECTOR_W = 1280  # 4x binned (Maki 2020 Section 2.6)
BINNED_DETECTOR_H = 960


def _load_yaml(path: Path) -> dict:
    """Read a YAML preset and return the parsed mapping."""
    with path.open() as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Navcam preset
# ---------------------------------------------------------------------------
class TestNavcamPreset:
    """Acceptance #1+#2: Navcam YAML loads as ``CameraConfig`` cleanly."""

    def test_yaml_file_exists(self) -> None:
        assert NAVCAM_YAML.is_file(), f"Navcam preset missing: {NAVCAM_YAML}"

    def test_loads_as_camera_config(self) -> None:
        """``CameraConfig.model_validate`` must accept the preset verbatim."""
        cfg = CameraConfig(**_load_yaml(NAVCAM_YAML))
        # Spot-check every public field so a future YAML drift is caught.
        assert cfg.parent_link == "Body_Chassis"
        assert len(cfg.local_translation) == 3
        assert len(cfg.local_orientation_rpy_deg) == 3
        assert len(cfg.resolution) == 2
        assert cfg.focal_length > 0.0
        assert len(cfg.clipping_range) == 2

    def test_focal_length_matches_maki_2020_table_3(self) -> None:
        """Navcam focal length = 19.1 mm (Maki et al. 2020 Table 3)."""
        cfg = CameraConfig(**_load_yaml(NAVCAM_YAML))
        assert cfg.focal_length == pytest.approx(19.1, abs=0.01), (
            "Navcam focal length must match Maki 2020 Table 3 (19.1 mm). "
            "If this assertion fails the YAML drifted from the cited "
            "primary source — see configs/sensors/m2020_navcam.yaml header."
        )

    def test_resolution_is_binned_detector_format(self) -> None:
        """Default preset uses 4x binned 1280 x 960 (Maki 2020 §2.6)."""
        cfg = CameraConfig(**_load_yaml(NAVCAM_YAML))
        assert cfg.resolution == [BINNED_DETECTOR_W, BINNED_DETECTOR_H], (
            "Navcam preset should default to the routine 4x-binned "
            "1280 x 960 size; switch to 5120 x 3840 only for full-frame "
            "data generation runs."
        )

    def test_clipping_range_well_formed(self) -> None:
        cfg = CameraConfig(**_load_yaml(NAVCAM_YAML))
        near, far = cfg.clipping_range
        assert near > 0.0
        assert far > near
        # Hyperfocal-to-infinity per Maki 2020 Table 3; ensure the far
        # plane is "long-range" enough for outdoor SLAM (>= 100 m).
        assert far >= 100.0

    def test_mount_orientation_is_camera_forward(self) -> None:
        """Navcam should look forward in the body frame.

        Isaac Sim's Camera +Z axis is the optical axis pointing into the
        scene; the parent ``Body_Chassis`` frame has +X forward, +Z up.
        Without the 180-deg roll the camera's image-plane Y axis would
        be inverted relative to the rover's up direction.  This test
        verifies the YAML carries the 180-deg X flip (any downstream
        change must update the test deliberately).
        """
        cfg = CameraConfig(**_load_yaml(NAVCAM_YAML))
        roll = cfg.local_orientation_rpy_deg[0]
        assert roll == pytest.approx(180.0, abs=0.5)


# ---------------------------------------------------------------------------
# Hazcam preset
# ---------------------------------------------------------------------------
class TestHazcamPreset:
    """Acceptance #1+#2: Hazcam YAML loads as ``CameraConfig`` cleanly."""

    def test_yaml_file_exists(self) -> None:
        assert HAZCAM_YAML.is_file(), f"Hazcam preset missing: {HAZCAM_YAML}"

    def test_loads_as_camera_config(self) -> None:
        cfg = CameraConfig(**_load_yaml(HAZCAM_YAML))
        assert cfg.parent_link == "Body_Chassis"
        assert len(cfg.local_translation) == 3
        assert len(cfg.local_orientation_rpy_deg) == 3
        assert len(cfg.resolution) == 2
        assert cfg.focal_length > 0.0

    def test_focal_length_matches_maki_2020_table_3(self) -> None:
        """Hazcam focal length = 7.4 mm (Maki et al. 2020 Table 3)."""
        cfg = CameraConfig(**_load_yaml(HAZCAM_YAML))
        assert cfg.focal_length == pytest.approx(7.4, abs=0.01), (
            "Hazcam focal length must match Maki 2020 Table 3 (7.4 mm). "
            "If this fails the YAML drifted from the cited primary source."
        )

    def test_focal_length_shorter_than_navcam(self) -> None:
        """Hazcam is a wide-angle lens; Navcam is the narrower view."""
        navcam = CameraConfig(**_load_yaml(NAVCAM_YAML))
        hazcam = CameraConfig(**_load_yaml(HAZCAM_YAML))
        assert hazcam.focal_length < navcam.focal_length, (
            "Hazcam (wide-angle, body-mounted) must have a shorter focal "
            "length than the Navcam (mast-mounted nav camera)."
        )

    def test_resolution_is_binned_detector_format(self) -> None:
        cfg = CameraConfig(**_load_yaml(HAZCAM_YAML))
        assert cfg.resolution == [BINNED_DETECTOR_W, BINNED_DETECTOR_H]

    def test_clipping_range_well_formed(self) -> None:
        cfg = CameraConfig(**_load_yaml(HAZCAM_YAML))
        near, far = cfg.clipping_range
        assert near > 0.0
        assert far > near
        # Hazcam is local hazard detection — far plane does not need to
        # exceed 100 m (and should not, to keep depth resolution dense
        # in the close-range envelope).
        assert near <= 0.5
        assert 50.0 <= far <= 200.0

    def test_mount_position_is_chassis_front(self) -> None:
        """Front-left Hazcam should sit forward of and below chassis origin."""
        cfg = CameraConfig(**_load_yaml(HAZCAM_YAML))
        x, _, z = cfg.local_translation
        assert x > 0.0, "Front Hazcam must sit forward of chassis origin (X > 0)"
        assert z < 0.0, (
            "Hazcam mount is below chassis origin (chassis is ~2 m above "
            "ground in the URDF; Hazcam sits at ~0.68 m above ground)."
        )


# ---------------------------------------------------------------------------
# Cross-preset invariants
# ---------------------------------------------------------------------------
class TestM2020CameraSharedDetector:
    """Both engineering camera families share the same 5120 x 3840 chip
    (Maki 2020 Table 2).  The resolutions in the YAML must be a valid
    binning of that chip — i.e. either the full detector or one of the
    documented even-divisor binnings.  This catches accidental edits
    that would put a non-flight resolution in the preset."""

    @pytest.mark.parametrize("preset_path", [NAVCAM_YAML, HAZCAM_YAML])
    def test_resolution_divides_full_detector(self, preset_path: Path) -> None:
        cfg = CameraConfig(**_load_yaml(preset_path))
        w, h = cfg.resolution
        assert FULL_DETECTOR_W % w == 0, (
            f"{preset_path.name}: resolution width {w} does not evenly "
            f"divide the M2020 detector width {FULL_DETECTOR_W}"
        )
        assert FULL_DETECTOR_H % h == 0, (
            f"{preset_path.name}: resolution height {h} does not evenly "
            f"divide the M2020 detector height {FULL_DETECTOR_H}"
        )
        # Both presets default to the same 4x binning; if a future edit
        # mixes binnings (Navcam at 4x, Hazcam at full) this still
        # passes — but the specific equal-aspect assertion below traps
        # accidental aspect-ratio drifts.
        full_aspect = FULL_DETECTOR_W / FULL_DETECTOR_H
        preset_aspect = w / h
        assert preset_aspect == pytest.approx(full_aspect, rel=1e-3), (
            f"{preset_path.name}: aspect ratio {preset_aspect:.4f} "
            f"differs from the M2020 detector aspect {full_aspect:.4f}"
        )

    @pytest.mark.parametrize("preset_path", [NAVCAM_YAML, HAZCAM_YAML])
    def test_focal_length_in_engineering_camera_envelope(self, preset_path: Path) -> None:
        """M2020 engineering cameras use lenses between ~5 mm (Hazcam
        wide) and ~25 mm (Navcam).  Anything outside that envelope is
        almost certainly a YAML typo (e.g. 191.0 instead of 19.1)."""
        cfg = CameraConfig(**_load_yaml(preset_path))
        assert 5.0 <= cfg.focal_length <= 25.0, (
            f"{preset_path.name}: focal length {cfg.focal_length} mm is "
            "outside the M2020 engineering camera envelope [5, 25] mm — "
            "verify against Maki 2020 Table 3."
        )


class TestPresetsRejectTypos:
    """``CameraConfig`` is declared with ``extra='forbid'`` (Reviewer 2 #12);
    this test confirms that a hand-written typo on top of the M2020 YAML
    does NOT silently load (regression guard for the schema-bypass class
    of bug)."""

    def test_typo_in_navcam_payload_is_rejected(self) -> None:
        from pydantic import ValidationError

        payload = _load_yaml(NAVCAM_YAML)
        payload["focal_lenght"] = 19.1  # sic
        with pytest.raises(ValidationError):
            CameraConfig(**payload)

    def test_typo_in_hazcam_payload_is_rejected(self) -> None:
        from pydantic import ValidationError

        payload = _load_yaml(HAZCAM_YAML)
        payload["clippping_range"] = [0.5, 100.0]  # sic
        with pytest.raises(ValidationError):
            CameraConfig(**payload)
