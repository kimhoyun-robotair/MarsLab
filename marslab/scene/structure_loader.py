"""Static USD structure loader for spacecraft / base / outpost scenes.

Attaches pre-authored ``.usd`` / ``.usda`` / ``.usdc`` assets under a
configurable prim path, applies translate/orient/scale, and optionally
enables collision. Pure USD by default; the ``structure_assets`` path
also accepts ``.obj`` / ``.stl`` meshes and converts to USD on the fly
via ``omni.kit.asset_converter``.

Offline-first: ``StructureConfig`` and ``StructureAsset`` stay plain
dataclasses, and importing this module does not touch Isaac Sim
(``pxr`` + ``isaacsim`` imports are deferred to call sites).

``static=True`` applies ``UsdPhysics.CollisionAPI`` only; ``static=False``
additionally applies ``RigidBodyAPI``.  Mass/damping are not modified --
authored USD values win.  No Mars-physics constants live here.
"""

from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Iterable, List, Tuple

from marslab.quaternion import rpy_to_quat

# The OBJ/STL drop-in pathway uses ``omni.kit.asset_converter``,
# documented at
# ``docs.omniverse.nvidia.com/extensions/latest/ext_asset-converter.html``
# (kit-105+).  The extension exposes ``AssetConverterContext`` +
# ``create_converter_task`` which is driven synchronously inside
# :func:`convert_mesh_to_usd`.
STRUCTURE_ASSET_EXTENSIONS: Tuple[str, ...] = (".obj", ".stl")

_LOG = logging.getLogger(__name__)

# Sanitiser regex shared by ``_default_asset_name`` and tests.  USD child
# tokens must match ``[A-Za-z_][A-Za-z0-9_]*``; anything else is
# replaced with ``_`` and ``a_`` is prepended if the leading char
# becomes a digit.
_USD_TOKEN_BAD = re.compile(r"[^A-Za-z0-9_]")

__all__ = [
    "STRUCTURE_ASSET_EXTENSIONS",
    "StructureAsset",
    "StructureConfig",
    "build_structure_asset",
    "convert_mesh_to_usd",
    "load_structure",
    "load_structure_assets",
    "load_structures",
    "resolve_asset_name",
]


@dataclass
class StructureConfig:
    """Declarative spec for a single static USD structure in the scene.

    Attributes:
        name: Short identifier used in the default prim path and log
            lines.  Must be a valid USD child name (alphanumeric /
            underscore, no leading digit).
        asset_path: Filesystem path to the ``.usd`` / ``.usda`` /
            ``.usdc`` file.  Absolute, or relative to the project root
            resolved by the caller before construction.
        spawn_xyz: World-frame translation in metres.
        spawn_rpy_deg: World-frame orientation as ZYX intrinsic roll /
            pitch / yaw in **degrees**.  Degrees chosen over radians so
            the YAML stays human-readable.
        scale: Per-axis scale factor applied after orient.  ``(1, 1, 1)``
            is identity; negative values are allowed but not
            recommended.
        static: If ``True`` the structure is rigid and does not
            participate in dynamics -- only :class:`UsdPhysics.CollisionAPI`
            is applied.  If ``False``, :class:`UsdPhysics.RigidBodyAPI`
            is additionally applied so the body can be pushed at runtime.
        collision: Gate for the CollisionAPI application.  When
            ``False`` the structure is visually present but has no
            physics response (sensors + rays still see it; dynamic
            bodies pass through).
        prim_path: Destination prim path on the stage.  Empty string
            triggers the default ``/World/Structures/{name}``.
    """

    name: str
    asset_path: str
    spawn_xyz: Tuple[float, float, float]
    spawn_rpy_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    static: bool = True
    collision: bool = True
    prim_path: str = ""

    def resolved_prim_path(self) -> str:
        """Return ``prim_path`` if non-empty, else the default layout.

        Default is ``/World/Structures/{name}`` so unrelated scenarios
        (rover spawns at ``/World/Rover``, terrain at ``/World/Terrain``)
        stay namespace-isolated from structures.
        """
        if self.prim_path:
            return self.prim_path
        return f"/World/Structures/{self.name}"


def _validate_asset(asset_path: str) -> str:
    """Return ``asset_path`` if it exists on disk, else raise.

    Kept as a module-level helper so the error message format is
    consistent between :func:`load_structure` and any future callers.

    Raises:
        FileNotFoundError: With a diagnostic message including the
            absolute path.  The hint points users at
            ``assets/mars_assets/`` + ``LICENSES.md`` since the actual
            Blender / NASA assets are produced out-of-band.
    """
    abs_path = os.path.abspath(asset_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(
            f"Structure USD asset not found: {abs_path}. "
            "Populate assets/mars_assets/ per LICENSES.md and rebuild."
        )
    return abs_path


def load_structure(stage: Any, cfg: StructureConfig) -> str:
    """Attach one USD structure to ``stage`` and return its prim path.

    Steps, in order:

    1. Validate ``cfg.asset_path`` exists on disk (hard failure -- a
       missing placeholder is a config error, not a warning).
    2. Resolve the destination prim path (``cfg.resolved_prim_path()``).
    3. Add a USD reference via ``isaacsim.core.utils.stage.add_reference_to_stage``.
    4. Apply translate → orient → scale on the xform.
    5. Apply :class:`UsdPhysics.CollisionAPI` if ``collision`` is set.
    6. Apply :class:`UsdPhysics.RigidBodyAPI` if ``static`` is ``False``.

    Args:
        stage: Active USD stage (post-``SimulationApp()`` init).
        cfg: :class:`StructureConfig` describing the asset placement.

    Returns:
        The absolute prim path under which the structure was attached.

    Raises:
        FileNotFoundError: If ``cfg.asset_path`` is missing.
        RuntimeError: If the referenced prim fails to resolve after
            attach (USD layer did not load).
    """
    # Isaac-Sim imports live inside the function so importing this
    # module outside Kit (unit tests, CI) does not pull libnvomni*.
    from isaacsim.core.utils.stage import add_reference_to_stage
    from pxr import Gf, UsdGeom, UsdPhysics

    abs_asset = _validate_asset(cfg.asset_path)
    prim_path = cfg.resolved_prim_path()

    add_reference_to_stage(usd_path=abs_asset, prim_path=prim_path)

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise RuntimeError(
            f"Structure prim failed to resolve after reference attach: {prim_path} "
            f"(asset={abs_asset}). USD load may have errored; check Kit log."
        )

    xform = UsdGeom.Xformable(prim)
    xform.ClearXformOpOrder()

    translate_op = xform.AddTranslateOp()
    translate_op.Set(
        Gf.Vec3d(
            float(cfg.spawn_xyz[0]),
            float(cfg.spawn_xyz[1]),
            float(cfg.spawn_xyz[2]),
        )
    )

    # rpy_to_quat takes radians; the dataclass stores degrees for
    # YAML readability, so convert here.
    roll_rad = math.radians(float(cfg.spawn_rpy_deg[0]))
    pitch_rad = math.radians(float(cfg.spawn_rpy_deg[1]))
    yaw_rad = math.radians(float(cfg.spawn_rpy_deg[2]))
    qw, qx, qy, qz = rpy_to_quat(roll_rad, pitch_rad, yaw_rad)
    orient_op = xform.AddOrientOp()
    orient_op.Set(Gf.Quatf(float(qw), float(qx), float(qy), float(qz)))

    scale_op = xform.AddScaleOp()
    scale_op.Set(
        Gf.Vec3f(
            float(cfg.scale[0]),
            float(cfg.scale[1]),
            float(cfg.scale[2]),
        )
    )

    if cfg.collision and not prim.HasAPI(UsdPhysics.CollisionAPI):
        UsdPhysics.CollisionAPI.Apply(prim)

    if not cfg.static and not prim.HasAPI(UsdPhysics.RigidBodyAPI):
        UsdPhysics.RigidBodyAPI.Apply(prim)

    return prim_path


def load_structures(stage: Any, cfgs: List[StructureConfig]) -> List[str]:
    """Attach a batch of structures; return the list of prim paths.

    Order-preserving wrapper around :func:`load_structure`.  Failures
    on a single structure abort the batch (no silent partial loads) --
    scenarios declare a small, curated list so fail-fast is the right
    default.

    Args:
        stage: Active USD stage.
        cfgs: List of :class:`StructureConfig` specs.

    Returns:
        List of absolute prim paths in the same order as ``cfgs``.
    """
    prim_paths: List[str] = []
    for cfg in cfgs:
        try:
            prim_paths.append(load_structure(stage, cfg))
        except FileNotFoundError as exc:
            # Re-raise with batch context so the YAML line that referenced
            # the missing asset is easy to locate.
            raise FileNotFoundError(f"Missing asset for structure {cfg.name!r}: {exc}") from exc
    return prim_paths


# --- structure_assets: OBJ/STL drop-in --------------------------------------
#
# The ``structure_assets:`` block in scenario YAML lets users drop in a
# ``.obj`` / ``.stl`` mesh without going through an offline USD bake.
# Conversion happens at scene-build time via ``omni.kit.asset_converter``
# (see module docstring for the doc link); the converted ``.usd`` is
# cached next to the source file so repeated runs do not re-convert.
#
# Module is offline-safe: ``StructureAsset`` is a pure dataclass and the
# conversion helper imports Isaac Sim lazily, so unit tests can exercise
# the resolution / sanitisation logic without Kit booted.


@dataclass
class StructureAsset:
    """Resolved OBJ/STL drop-in spec ready for runtime conversion.

    Distinct from :class:`StructureConfig` (USD-only) so the runtime
    pipeline can decide which loader to dispatch on.

    Attributes:
        name: USD-safe child name. ``resolve_asset_name`` derives a
            default from the file stem when the YAML omits it.
        source_path: Absolute path to the ``.obj`` / ``.stl`` file.
        position: World-frame translation in metres.
        rotation_rpy_deg: ZYX intrinsic [roll, pitch, yaw] in degrees.
        scale: Uniform scale factor applied after orient.
        prim_path: Destination prim path -- defaults to
            ``/World/StructureAssets/{name}`` for namespace isolation
            from the pre-baked USD structures.
    """

    name: str
    source_path: str
    position: Tuple[float, float, float]
    rotation_rpy_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: float = 1.0
    prim_path: str = ""

    def resolved_prim_path(self) -> str:
        """Return ``prim_path`` if non-empty, else the default layout.

        Default ``/World/StructureAssets/{name}`` keeps the drop-in
        meshes namespace-isolated from the pre-baked USD structures
        (``/World/Structures/...``).
        """
        if self.prim_path:
            return self.prim_path
        return f"/World/StructureAssets/{self.name}"


def resolve_asset_name(raw_name: str | None, source_path: str) -> str:
    """Return a USD-safe child name for ``StructureAsset``.

    USD tokens must match ``[A-Za-z_][A-Za-z0-9_]*``.  This helper
    strips path separators / whitespace from the file stem, replaces
    illegal characters with ``_``, and prepends ``a_`` if the result
    starts with a digit.

    Args:
        raw_name: Optional explicit name from YAML.  Pre-validated by
            :class:`StructureAssetConfig` to already be USD-safe; this
            function returns it untouched when supplied.
        source_path: Source mesh path used as the fallback stem.

    Returns:
        USD-safe child token suitable for the prim path.
    """
    if raw_name:
        return raw_name
    stem = os.path.splitext(os.path.basename(source_path))[0]
    if not stem:
        raise ValueError(
            f"Cannot derive structure_assets name from empty stem: {source_path!r}. "
            "Provide an explicit ``name`` in YAML."
        )
    cleaned = _USD_TOKEN_BAD.sub("_", stem)
    if cleaned[0].isdigit():
        cleaned = "a_" + cleaned
    return cleaned


def _resolve_source_path(source_path: str, repo_root: str | None = None) -> str:
    """Expand ``source_path`` against the repo root when relative.

    Mirrors the behaviour of
    :func:`marslab.config.yaml_loader._resolve_path` (kept as a sibling
    rather than importing it: ``yaml_loader`` is config-layer, this is
    scene-layer; pulling the import would cross module boundaries for
    a four-line helper).
    """
    if os.path.isabs(source_path):
        return source_path
    if repo_root is None:
        # Climb three levels: ``marslab/scene/structure_loader.py`` ->
        # repo root.  Kept as a fallback so call sites can stay terse.
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.abspath(os.path.join(repo_root, source_path))


def build_structure_asset(
    cfg: Any,
    repo_root: str | None = None,
) -> StructureAsset:
    """Convert a :class:`StructureAssetConfig` into a runtime dataclass.

    ``cfg`` is typed loosely (``Any``) so this module does not import
    pydantic just for a type hint -- pydantic stays a config-layer
    concern.  The duck-typed access keeps the function offline-safe.

    Args:
        cfg: ``StructureAssetConfig`` (pydantic) instance from the
            scenario YAML.
        repo_root: Repo root used to resolve relative paths.  Defaults
            to MarsLab's repository root.

    Returns:
        Fully resolved :class:`StructureAsset` ready for
        :func:`load_structure_assets`.
    """
    name = resolve_asset_name(getattr(cfg, "name", None), cfg.path)
    source = _resolve_source_path(cfg.path, repo_root=repo_root)
    pos = tuple(float(v) for v in cfg.position)
    rpy = tuple(float(v) for v in cfg.rotation_rpy_deg)
    return StructureAsset(
        name=name,
        source_path=source,
        position=(pos[0], pos[1], pos[2]),
        rotation_rpy_deg=(rpy[0], rpy[1], rpy[2]),
        scale=float(cfg.scale),
    )


def _validate_mesh_source(source_path: str) -> str:
    """Return ``source_path`` if it exists + has a supported extension.

    Raises:
        FileNotFoundError: With absolute path so the YAML author can
            spot a typo without re-running with ``--verbose``.
        ValueError: If the extension is not in
            :data:`STRUCTURE_ASSET_EXTENSIONS`.  Pydantic already rejects
            this at YAML-load time but the loader keeps a defensive
            guard for direct ``StructureAsset`` callers.
    """
    abs_path = os.path.abspath(source_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(
            f"structure_assets source mesh not found: {abs_path}. "
            "Confirm the path is repo-relative (or absolute) and the file exists."
        )
    ext = os.path.splitext(abs_path)[1].lower()
    if ext not in STRUCTURE_ASSET_EXTENSIONS:
        raise ValueError(
            f"Unsupported structure_assets extension {ext!r} for {abs_path}. "
            f"Supported: {STRUCTURE_ASSET_EXTENSIONS}."
        )
    return abs_path


def convert_mesh_to_usd(source_path: str, dest_path: str) -> str:
    """Convert ``.obj`` / ``.stl`` to ``.usd`` via Isaac Sim.

    Uses ``omni.kit.asset_converter`` -- the canonical extension for
    OBJ/STL -> USD inside Kit (kit-105+, see
    ``docs.omniverse.nvidia.com/extensions/latest/ext_asset-converter.html``).
    The function blocks until the converter task completes; for the
    small props this loader targets (rocks, tools, pebbles) the
    conversion runs in well under a second.

    Args:
        source_path: Absolute path to the ``.obj`` / ``.stl`` file.
        dest_path: Absolute path for the output ``.usd`` file.  The
            parent directory must already exist.

    Returns:
        ``dest_path`` after a successful conversion (mirrors back so
        callers can chain).

    Raises:
        FileNotFoundError: If ``source_path`` is missing.
        RuntimeError: If the converter task returns a non-success status.
    """
    import asyncio

    import omni.kit.asset_converter as asset_converter  # noqa: PLC0415

    _validate_mesh_source(source_path)

    context = asset_converter.AssetConverterContext()
    # Defaults are tuned for static prop import: skip absent materials,
    # keep the original mesh hierarchy.  ``ignore_materials`` is True
    # because OBJ MTL paths usually break when files move; the caller
    # can flip this if material-faithful import becomes a follow-up
    # requirement.
    context.ignore_materials = True
    context.ignore_camera = True
    context.ignore_animations = True
    context.ignore_light = True
    context.single_mesh = False
    context.smooth_normals = True

    instance = asset_converter.get_instance()
    task = instance.create_converter_task(source_path, dest_path, None, context)

    # ``asyncio.get_event_loop()`` raises ``DeprecationWarning`` on
    # Python 3.10+ when no loop is running and is removed in 3.12+.
    # Inside Isaac Sim Kit there is usually a running loop; in unit-test
    # paths the converter is stubbed entirely.  Any freshly created
    # loop is closed in the ``finally`` block so the loop does not leak.
    created_loop = False
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        created_loop = True
    try:
        success = loop.run_until_complete(task.wait_until_finished())
    finally:
        if created_loop:
            loop.close()
    if not success:
        raise RuntimeError(
            f"omni.kit.asset_converter failed for {source_path} -> {dest_path}: "
            f"{task.get_status()} ({task.get_error_message()})"
        )
    return dest_path


def _cached_usd_path(source_path: str) -> str:
    """Return the cache path for the ``.usd`` twin of ``source_path``.

    Cache layout: sibling ``.usd`` next to the source file. The
    converter writes there only if the destination is missing OR older
    than the source (handled by :func:`load_structure_assets`).
    """
    return os.path.splitext(source_path)[0] + ".usd"


def load_structure_assets(
    stage: Any,
    assets: Iterable[StructureAsset],
    *,
    converter: Any = None,
) -> List[str]:
    """Convert + attach a batch of OBJ/STL drop-ins; return prim paths.

    Each asset is converted to USD (cached next to the source) and
    referenced into the stage with translate/orient/scale applied.
    Failures abort the batch -- structure assets are scenario-critical,
    so a missing file is a hard config error, not a warning.

    Args:
        stage: Active USD stage.
        assets: Iterable of :class:`StructureAsset` specs.
        converter: Optional callable ``(source, dest) -> dest`` used in
            place of :func:`convert_mesh_to_usd`. Tests inject a stub so
            unit coverage runs without Isaac Sim.

    Returns:
        List of prim paths in iteration order.

    Raises:
        FileNotFoundError: If any source mesh is missing.
        RuntimeError: If the converter or the USD reference fails to
            resolve after attach.
    """
    from isaacsim.core.utils.stage import add_reference_to_stage  # noqa: PLC0415
    from pxr import Gf, UsdGeom  # noqa: PLC0415

    convert = converter if converter is not None else convert_mesh_to_usd
    prim_paths: List[str] = []
    for asset in assets:
        abs_source = _validate_mesh_source(asset.source_path)
        cached_usd = _cached_usd_path(abs_source)
        if not os.path.isfile(cached_usd) or (
            os.path.getmtime(cached_usd) < os.path.getmtime(abs_source)
        ):
            convert(abs_source, cached_usd)

        prim_path = asset.resolved_prim_path()
        add_reference_to_stage(usd_path=cached_usd, prim_path=prim_path)

        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise RuntimeError(
                f"structure_assets prim failed to resolve after convert+attach: "
                f"{prim_path} (source={abs_source}, usd={cached_usd})"
            )

        xform = UsdGeom.Xformable(prim)
        xform.ClearXformOpOrder()

        translate_op = xform.AddTranslateOp()
        translate_op.Set(
            Gf.Vec3d(
                float(asset.position[0]),
                float(asset.position[1]),
                float(asset.position[2]),
            )
        )

        roll_rad = math.radians(float(asset.rotation_rpy_deg[0]))
        pitch_rad = math.radians(float(asset.rotation_rpy_deg[1]))
        yaw_rad = math.radians(float(asset.rotation_rpy_deg[2]))
        qw, qx, qy, qz = rpy_to_quat(roll_rad, pitch_rad, yaw_rad)
        orient_op = xform.AddOrientOp()
        orient_op.Set(Gf.Quatf(float(qw), float(qx), float(qy), float(qz)))

        scale_op = xform.AddScaleOp()
        s = float(asset.scale)
        scale_op.Set(Gf.Vec3f(s, s, s))

        prim_paths.append(prim_path)
    return prim_paths
