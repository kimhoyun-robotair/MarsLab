"""Unit tests for the ``structure_assets:`` drop-in pathway (Task H).

P3 offline-first: these tests exercise schema validation + the
``StructureAsset`` resolution helpers + a mocked ``load_structure_assets``
batch end-to-end without a live Isaac Sim Kit. The conversion call
(``convert_mesh_to_usd``) is replaced by a stub that records the args
and writes a placeholder USD so the rest of the pipeline runs.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List, Tuple
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError

from marslab.config.loader import load_and_validate
from marslab.config.scenario_loader import load_scenario_config
from marslab.config.schema import (
    MarsLabConfig,
    SceneConfig,
    StructureAssetConfig,
)
from marslab.scene.structure_loader import (
    STRUCTURE_ASSET_EXTENSIONS,
    StructureAsset,
    build_structure_asset,
    load_structure_assets,
    resolve_asset_name,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"
OBJ_FIXTURE = FIXTURE_DIR / "sample_rock.obj"
STL_FIXTURE = FIXTURE_DIR / "sample_rock.stl"


# --- Fixture file presence ---------------------------------------------------


def test_obj_fixture_exists_and_small():
    """OBJ fixture is checked in and well under the 10 KB binary cap."""
    assert OBJ_FIXTURE.is_file(), f"missing OBJ fixture: {OBJ_FIXTURE}"
    size = OBJ_FIXTURE.stat().st_size
    assert size > 0, "OBJ fixture is empty"
    assert size < 10_000, f"OBJ fixture exceeds 10 KB binary cap: {size} bytes"


def test_stl_fixture_exists_and_small():
    """STL fixture is checked in and well under the 10 KB binary cap."""
    assert STL_FIXTURE.is_file(), f"missing STL fixture: {STL_FIXTURE}"
    size = STL_FIXTURE.stat().st_size
    assert size > 0, "STL fixture is empty"
    assert size < 10_000, f"STL fixture exceeds 10 KB binary cap: {size} bytes"


# --- StructureAssetConfig (pydantic schema) ---------------------------------


def test_schema_minimum_required_fields():
    """``path`` and ``position`` are required."""
    with pytest.raises(ValidationError):
        StructureAssetConfig()
    with pytest.raises(ValidationError):
        StructureAssetConfig(path="x.obj")  # missing position
    with pytest.raises(ValidationError):
        StructureAssetConfig(position=[0, 0, 0])  # missing path


def test_schema_defaults():
    """Optional fields take the documented defaults."""
    cfg = StructureAssetConfig(path="x.obj", position=[1.0, 2.0, 3.0])
    assert cfg.rotation_rpy_deg == [0.0, 0.0, 0.0]
    assert cfg.scale == 1.0
    assert cfg.name is None


def test_schema_rejects_unsupported_extension():
    """Anything that is not ``.obj`` / ``.stl`` is rejected."""
    with pytest.raises(ValidationError):
        StructureAssetConfig(path="x.fbx", position=[0, 0, 0])
    with pytest.raises(ValidationError):
        StructureAssetConfig(path="x.usd", position=[0, 0, 0])


def test_schema_accepts_both_supported_extensions():
    """``.obj`` and ``.stl`` both validate."""
    StructureAssetConfig(path="x.obj", position=[0, 0, 0])
    StructureAssetConfig(path="x.stl", position=[0, 0, 0])


def test_schema_rejects_invalid_name():
    """USD-token violations on explicit names fail validation."""
    with pytest.raises(ValidationError):
        StructureAssetConfig(path="x.obj", position=[0, 0, 0], name="bad name")
    with pytest.raises(ValidationError):
        StructureAssetConfig(path="x.obj", position=[0, 0, 0], name="bad/name")
    with pytest.raises(ValidationError):
        StructureAssetConfig(path="x.obj", position=[0, 0, 0], name="1bad")


def test_schema_rejects_wrong_position_length():
    """Position must be a 3-vector."""
    with pytest.raises(ValidationError):
        StructureAssetConfig(path="x.obj", position=[1.0, 2.0])
    with pytest.raises(ValidationError):
        StructureAssetConfig(path="x.obj", position=[1.0, 2.0, 3.0, 4.0])


def test_schema_extra_forbid():
    """Misspelled keys fail validation (extra='forbid')."""
    with pytest.raises(ValidationError):
        StructureAssetConfig(
            path="x.obj",
            position=[0, 0, 0],
            scaale=1.0,  # type: ignore[call-arg]
        )


# --- SceneConfig wiring + MarsLabConfig --------------------------------------


def test_scene_default_includes_empty_structure_assets():
    """Default :class:`SceneConfig` exposes empty ``structure_assets``."""
    sc = SceneConfig()
    assert sc.structure_assets == []
    assert sc.structures == []


def test_scene_parses_structure_assets_block():
    """A scene block with ``structure_assets`` validates."""
    sc = SceneConfig(
        structure_assets=[
            {
                "path": "tests/fixtures/sample_rock.obj",
                "position": [1.0, 2.0, 3.0],
                "rotation_rpy_deg": [0.0, 0.0, 45.0],
                "scale": 1.5,
                "name": "boulder_01",
            }
        ]
    )
    assert len(sc.structure_assets) == 1
    assert sc.structure_assets[0].name == "boulder_01"
    assert sc.structure_assets[0].scale == 1.5


def test_marslab_config_accepts_structure_assets():
    """Drop-in via top-level :class:`MarsLabConfig` works end-to-end."""
    from marslab.config.schema.terrain import TerrainConfig

    mlc = MarsLabConfig(
        terrain=TerrainConfig(source="procedural", procedural_preset="flat"),
        scene={
            "structure_assets": [
                {
                    "path": "tests/fixtures/sample_rock.obj",
                    "position": [0.0, 0.0, 0.0],
                }
            ]
        },
    )
    assert len(mlc.scene.structure_assets) == 1


# --- resolve_asset_name + build_structure_asset ------------------------------


def test_resolve_asset_name_explicit_passthrough():
    """An explicit name is preserved verbatim."""
    assert resolve_asset_name("my_boulder", "/tmp/whatever.obj") == "my_boulder"


def test_resolve_asset_name_fallback_uses_stem():
    """Missing name falls back to the file stem."""
    assert resolve_asset_name(None, "/tmp/sample_rock.obj") == "sample_rock"


def test_resolve_asset_name_sanitises_bad_chars():
    """Hyphens and dots in the stem become underscores."""
    assert resolve_asset_name(None, "/tmp/sample-rock.v2.obj") == "sample_rock_v2"


def test_resolve_asset_name_prepends_for_leading_digit():
    """A digit-starting stem gets prefixed so the USD token is valid."""
    assert resolve_asset_name(None, "/tmp/01_boulder.obj") == "a_01_boulder"


def test_resolve_asset_name_empty_stem_raises():
    """An empty stem cannot fall back -- caller must supply a name.

    Note: ``os.path.splitext('/tmp/.obj')`` returns ``('/tmp/.obj', '')``
    on POSIX (dotfile rule), so the stem there is ``.obj`` which the
    sanitiser turns into ``_obj`` -- that's a valid USD token. The
    *truly* empty case is a directory-shaped path like ``/tmp/`` where
    ``basename`` returns the empty string.
    """
    with pytest.raises(ValueError):
        resolve_asset_name(None, "/tmp/")


def test_build_structure_asset_round_trip():
    """``StructureAssetConfig`` -> ``StructureAsset`` preserves fields."""
    cfg = StructureAssetConfig(
        path="tests/fixtures/sample_rock.obj",
        position=[1.0, 2.0, 3.0],
        rotation_rpy_deg=[10.0, 20.0, 30.0],
        scale=1.5,
        name="boulder_01",
    )
    asset = build_structure_asset(cfg, repo_root=str(REPO_ROOT))
    assert isinstance(asset, StructureAsset)
    assert asset.name == "boulder_01"
    assert asset.position == (1.0, 2.0, 3.0)
    assert asset.rotation_rpy_deg == (10.0, 20.0, 30.0)
    assert asset.scale == 1.5
    assert asset.source_path == str(OBJ_FIXTURE)
    assert asset.resolved_prim_path() == "/World/StructureAssets/boulder_01"


def test_build_structure_asset_default_name_from_path():
    """When ``name`` is omitted, the stem fallback kicks in."""
    cfg = StructureAssetConfig(
        path="tests/fixtures/sample_rock.stl",
        position=[0.0, 0.0, 0.0],
    )
    asset = build_structure_asset(cfg, repo_root=str(REPO_ROOT))
    assert asset.name == "sample_rock"
    assert asset.source_path == str(STL_FIXTURE)


def test_build_structure_asset_absolute_path_unchanged():
    """Absolute ``path`` is not re-resolved against the repo root."""
    cfg = StructureAssetConfig(
        path=str(OBJ_FIXTURE),
        position=[0.0, 0.0, 0.0],
    )
    asset = build_structure_asset(cfg, repo_root=str(REPO_ROOT))
    assert asset.source_path == str(OBJ_FIXTURE)


# --- load_structure_assets (Isaac Sim mocked) --------------------------------


class _FakePrim:
    """Stand-in for ``pxr.Usd.Prim`` returned by stage queries."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._valid = True

    def IsValid(self) -> bool:  # noqa: N802 -- USD API casing
        return self._valid


class _FakeStage:
    """Recording stub stage. Captures calls so tests can assert on them."""

    def __init__(self) -> None:
        self.refs: List[Tuple[str, str]] = []

    def GetPrimAtPath(self, path: str) -> _FakePrim:  # noqa: N802 -- USD API casing
        return _FakePrim(path)


@pytest.fixture
def mocked_isaac_modules(monkeypatch, tmp_path):
    """Patch ``isaacsim.core.utils.stage`` + ``pxr`` so the loader runs offline."""
    # Stub add_reference_to_stage that records (usd_path, prim_path).
    refs: List[Tuple[str, str]] = []

    def fake_add_reference(usd_path: str, prim_path: str) -> None:
        refs.append((usd_path, prim_path))

    fake_isaacsim_stage = SimpleNamespace(add_reference_to_stage=fake_add_reference)

    # ``pxr.Gf`` / ``pxr.UsdGeom`` get the bare minimum the loader uses.
    class _Op:
        def __init__(self) -> None:
            self.value: Any = None

        def Set(self, v: Any) -> None:  # noqa: N802 -- USD API casing
            self.value = v

    class _Xformable:
        def __init__(self, prim: Any) -> None:
            self.prim = prim
            self.translate = _Op()
            self.orient = _Op()
            self.scale = _Op()
            self.cleared = False

        def ClearXformOpOrder(self) -> None:  # noqa: N802 -- USD API casing
            self.cleared = True

        def AddTranslateOp(self) -> _Op:  # noqa: N802 -- USD API casing
            return self.translate

        def AddOrientOp(self) -> _Op:  # noqa: N802 -- USD API casing
            return self.orient

        def AddScaleOp(self) -> _Op:  # noqa: N802 -- USD API casing
            return self.scale

    class _Vec3:
        def __init__(self, *args: float) -> None:
            self.values = tuple(float(a) for a in args)

    class _Quatf:
        def __init__(self, w: float, x: float, y: float, z: float) -> None:
            self.values = (w, x, y, z)

    fake_pxr = SimpleNamespace(
        Gf=SimpleNamespace(Vec3d=_Vec3, Vec3f=_Vec3, Quatf=_Quatf),
        UsdGeom=SimpleNamespace(Xformable=_Xformable),
    )

    # The loader does ``from isaacsim.core.utils.stage import ...`` and
    # ``from pxr import ...`` inside the function, so we patch the
    # ``sys.modules`` entries that those imports resolve to.
    import sys

    monkeypatch.setitem(
        sys.modules,
        "isaacsim",
        SimpleNamespace(core=SimpleNamespace(utils=SimpleNamespace(stage=fake_isaacsim_stage))),
    )
    monkeypatch.setitem(sys.modules, "isaacsim.core", sys.modules["isaacsim"].core)
    monkeypatch.setitem(sys.modules, "isaacsim.core.utils", sys.modules["isaacsim.core"].utils)
    monkeypatch.setitem(
        sys.modules, "isaacsim.core.utils.stage", sys.modules["isaacsim.core.utils"].stage
    )
    monkeypatch.setitem(sys.modules, "pxr", fake_pxr)

    return SimpleNamespace(refs=refs, fake_isaac_stage=fake_isaacsim_stage, fake_pxr=fake_pxr)


def test_load_structure_assets_invokes_converter_and_attaches_prim(mocked_isaac_modules, tmp_path):
    """End-to-end batch: convert is called once per asset, prim attaches."""
    # Stage a temp .obj so the converter cache can write a sibling .usd.
    src = tmp_path / "boulder.obj"
    src.write_text(OBJ_FIXTURE.read_text())

    asset = StructureAsset(
        name="boulder_01",
        source_path=str(src),
        position=(1.0, 2.0, 3.0),
        rotation_rpy_deg=(0.0, 0.0, 45.0),
        scale=1.0,
    )
    stage = _FakeStage()

    converter_calls: List[Tuple[str, str]] = []

    def fake_convert(source: str, dest: str) -> str:
        converter_calls.append((source, dest))
        Path(dest).write_text("#usda 1.0\n")
        return dest

    paths = load_structure_assets(stage, [asset], converter=fake_convert)

    assert paths == ["/World/StructureAssets/boulder_01"]
    # Converter was called once with the matching cache target.
    assert len(converter_calls) == 1
    assert converter_calls[0][0] == str(src)
    assert converter_calls[0][1].endswith("boulder.usd")
    # add_reference_to_stage was called with the cached USD + correct prim.
    assert mocked_isaac_modules.refs == [
        (str(src.parent / "boulder.usd"), "/World/StructureAssets/boulder_01")
    ]


def test_load_structure_assets_skips_converter_when_cache_fresh(mocked_isaac_modules, tmp_path):
    """An up-to-date sibling ``.usd`` skips re-conversion."""
    src = tmp_path / "boulder.obj"
    src.write_text(OBJ_FIXTURE.read_text())
    cached = tmp_path / "boulder.usd"
    cached.write_text("#usda 1.0\n")
    # Bump cache mtime above source so the loader treats it as fresh.
    os.utime(cached, (src.stat().st_atime + 10, src.stat().st_mtime + 10))

    asset = StructureAsset(
        name="boulder_01",
        source_path=str(src),
        position=(0.0, 0.0, 0.0),
    )
    stage = _FakeStage()

    converter_calls: List[Tuple[str, str]] = []

    def fake_convert(source: str, dest: str) -> str:
        converter_calls.append((source, dest))
        return dest

    load_structure_assets(stage, [asset], converter=fake_convert)
    assert converter_calls == [], "converter should not run when cache is fresh"


def test_load_structure_assets_missing_file_raises(mocked_isaac_modules, tmp_path):
    """A missing source mesh fails fast with FileNotFoundError."""
    asset = StructureAsset(
        name="missing", source_path=str(tmp_path / "absent.obj"), position=(0, 0, 0)
    )
    stage = _FakeStage()

    with pytest.raises(FileNotFoundError):
        load_structure_assets(stage, [asset], converter=lambda s, d: d)


def test_load_structure_assets_invalid_extension_raises(mocked_isaac_modules, tmp_path):
    """Unsupported extension trips the defensive guard inside the loader."""
    src = tmp_path / "boulder.fbx"
    src.write_text("not really fbx, just a guard test")

    asset = StructureAsset(name="boulder", source_path=str(src), position=(0, 0, 0))
    stage = _FakeStage()

    with pytest.raises(ValueError, match="Unsupported structure_assets extension"):
        load_structure_assets(stage, [asset], converter=lambda s, d: d)


def test_supported_extensions_constant_matches_schema():
    """Schema regex + loader extension constant stay in lockstep."""
    assert STRUCTURE_ASSET_EXTENSIONS == (".obj", ".stl")


# --- jezero_flat scenario YAML round-trip ------------------------------------


def test_jezero_flat_yaml_has_structure_assets_example():
    """The example scenario ships with the demonstration entry."""
    path = REPO_ROOT / "configs" / "scenarios" / "jezero_flat.yaml"
    raw = yaml.safe_load(path.read_text())
    assert "scene" in raw
    assert "structure_assets" in raw["scene"]
    entries = raw["scene"]["structure_assets"]
    assert len(entries) == 1
    assert entries[0]["path"].endswith("sample_rock.obj")
    assert entries[0]["name"] == "boulder_01"


def test_jezero_flat_load_scenario_config_does_not_raise():
    """The end-to-end scenario load + base merge succeeds."""
    path = REPO_ROOT / "configs" / "scenarios" / "jezero_flat.yaml"
    cfg = load_scenario_config(str(path))
    assert "scene" in cfg
    assert "structure_assets" in cfg["scene"]
    assert len(cfg["scene"]["structure_assets"]) == 1


def test_jezero_flat_load_and_validate_round_trip(tmp_path):
    """``load_and_validate`` (the pydantic path) accepts the scenario.

    ``load_and_validate`` does not consume the scenario loader's
    ``rover.base_config`` indirection -- it expects a flat config -- so
    we synthesize a minimal sandwich (base + scenario without rover) and
    validate that. This is the same surface ``test_structure_loader_schema``
    uses for the existing ``structures`` block.
    """
    base = REPO_ROOT / "configs" / "scenarios" / "_base.yaml"
    base_data = yaml.safe_load(base.read_text())
    base_data.setdefault("terrain", {})
    base_data["terrain"].update(
        {
            "source": "procedural",
            "procedural_preset": "flat",
            "rock_sfd_k": 0,
        }
    )
    base_data["scene"] = {
        "structure_assets": [
            {
                "path": "tests/fixtures/sample_rock.obj",
                "position": [10.0, 5.0, 0.0],
                "rotation_rpy_deg": [0.0, 0.0, 45.0],
                "scale": 1.0,
                "name": "boulder_01",
            }
        ]
    }
    cfg_path = tmp_path / "scenario.yaml"
    cfg_path.write_text(yaml.safe_dump(base_data))

    mlc = load_and_validate(str(cfg_path))
    assert isinstance(mlc, MarsLabConfig)
    assert len(mlc.scene.structure_assets) == 1
    assert mlc.scene.structure_assets[0].name == "boulder_01"


# --- Offline-safety smoke ----------------------------------------------------


def test_loader_does_not_pull_isaac_at_import_time():
    """Importing the module + calling pure helpers does not import Isaac.

    Regression guard for P3: if a future refactor moves the Isaac Sim
    import to module scope, this test fails on CI nodes without GPU.

    Implementation note: we deliberately avoid ``importlib.reload`` here
    because reloading the module would mint a fresh ``StructureConfig``
    class object, breaking ``isinstance`` checks performed by sibling
    test modules that imported it earlier in the session.
    """
    import sys

    # The top-of-file imports already pulled the module into sys.modules
    # without dragging Isaac in -- if Kit had been loaded, the
    # ``isaacsim.*`` keys would already be present.  Sanity-check the
    # loader module is in fact loaded so the assertion below has weight.
    assert "marslab.scene.structure_loader" in sys.modules

    # resolve_asset_name + build_structure_asset are pure-Python paths.
    cfg = StructureAssetConfig(path="x.obj", position=[0, 0, 0])
    build_structure_asset(cfg, repo_root=str(REPO_ROOT))

    # Allow Isaac modules in sys.modules ONLY if the host is in Kit.
    # The CI node never sets this env var, so the assertion remains tight.
    # NB: another test in this file deliberately injects a fake
    # ``omni.kit.asset_converter`` module via ``patch.dict`` -- pytest
    # tears that down before this test runs because of the patch
    # context manager, so the assertion still holds.
    assert (
        "isaacsim.core.utils.stage" not in sys.modules or os.environ.get("ISAAC_SIM_RUNNING") == "1"
    )


def test_convert_mesh_to_usd_lazy_imports_isaac():
    """``convert_mesh_to_usd`` only imports Isaac inside the function body.

    Verified by patching the import to raise; if the import lived at
    module scope the test wouldn't even reach the patch.
    """
    import sys
    import types as _types

    fake_module = _types.ModuleType("omni.kit.asset_converter")

    def _explode(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("test stub: omni.kit.asset_converter is not real")

    fake_module.AssetConverterContext = _explode  # type: ignore[attr-defined]
    fake_module.get_instance = _explode  # type: ignore[attr-defined]

    with patch.dict(
        sys.modules,
        {
            "omni": _types.ModuleType("omni"),
            "omni.kit": _types.ModuleType("omni.kit"),
            "omni.kit.asset_converter": fake_module,
        },
    ):
        from marslab.scene.structure_loader import convert_mesh_to_usd

        with pytest.raises(RuntimeError, match="test stub"):
            convert_mesh_to_usd(str(OBJ_FIXTURE), "/tmp/never.usd")
