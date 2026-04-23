"""Static USD structure loader for spacecraft / base / outpost scenes.

This module attaches pre-authored ``.usd`` / ``.usda`` / ``.usdc``
assets under a configurable prim path, applies translate/orient/scale,
and optionally enables collision.  It mirrors the layering used by
``marslab.robots.rover`` so the call site pattern stays familiar:

    from marslab.scene import StructureConfig, load_structures
    load_structures(stage, [StructureConfig(name="lander", ...), ...])

Design notes:

* **Pure USD only.**  Per ``reference_rover_usd_source`` the project
  forbids runtime URDF / OBJ / FBX import.  Callers must convert assets
  offline first; this loader only knows how to attach a USD reference.
* **Offline-first (P3).**  ``StructureConfig`` is a plain dataclass and
  importing this module does not touch Isaac Sim.  The Isaac-Sim /
  ``pxr`` imports are deferred inside :func:`load_structure` so
  ``from marslab.scene.structure_loader import StructureConfig`` works
  from unit tests with no Kit session.
* **static=True** applies ``UsdPhysics.CollisionAPI`` only; dynamic
  props (``static=False``) additionally apply ``RigidBodyAPI``.  We do
  NOT modify mass / damping here -- authored USD values win.
* **G5.**  Zero Mars-physics constants live in this module; callers
  drive everything from :class:`StructureConfig` instances built from
  YAML (see :class:`marslab.config.schema.scene.SceneConfig`).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, List, Tuple

from marslab.math.quaternion import rpy_to_quat

__all__ = [
    "StructureConfig",
    "load_structure",
    "load_structures",
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
            ``assets/structures/`` + ``LICENSES.md`` since the actual
            Blender / NASA assets are produced out-of-band.
    """
    abs_path = os.path.abspath(asset_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(
            f"Structure USD asset not found: {abs_path}. "
            "Populate assets/structures/ per LICENSES.md and rebuild."
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
    import math

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
            # Re-raise with batch context -- the spacecraft / base
            # scenarios ship placeholder paths while the artist team
            # produces the real assets.  The error already names the
            # file; include the structure name so the YAML line is
            # easy to locate.
            print(
                f"[marslab.scene.structure_loader] Missing asset for "
                f"structure '{cfg.name}': {exc}",
                file=sys.stderr,
            )
            raise
    return prim_paths


# Defensive re-bind so static type checkers pick up the module-level
# default_factory pattern without importing ``dataclasses.field``
# transitively.  Keeping the import visible silences ``F401`` on
# ``field`` which may be used by downstream subclasses.
_ = field  # noqa: F841
