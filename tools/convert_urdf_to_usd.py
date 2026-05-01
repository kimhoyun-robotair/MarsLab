"""One-shot URDF -> USD conversion for the Perseverance (M2020) rover.

Reads the NASA JPL m2020-urdf-models URDF from
``assets/m2020-urdf-models/`` (a fork of github.com/nasa-jpl/m2020-urdf-models
shipped as a git submodule) and writes a standalone USD into
``assets/robots/rover/``.  Runtime code must load the resulting USD; it
must not re-run URDF import at simulation time.

The NASA JPL URDF is authored for visualization tools (rviz / browser
viewers) and contains constructs that Isaac Sim's URDF importer rejects:

* All <limit> attributes use +/-1.79769e+308 (DBL_MAX) which overflows
  the importer's 32-bit float parser.
* Two joints use type="floating" which the importer does not support.

A small in-memory sanitizer rewrites the URDF into a sibling temp file
before handing it to URDFParseAndImportFile. The temp file lives in the
same directory as the original so mesh references (./meshes/*.gltf)
still resolve, and is removed in a finally block.

Usage:
    marslab/isaac_python.sh tools/convert_urdf_to_usd.py

Optional flags:
    --urdf PATH   Override the input URDF path.
    --usd PATH    Override the output USD path.
"""

import argparse
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_URDF = os.path.join(REPO_ROOT, "assets", "m2020-urdf-models", "rover", "m2020.urdf")
DEFAULT_USD = os.path.join(REPO_ROOT, "assets", "robots", "rover", "m2020.usd")

_DBL_MAX_RE = r"-?1\.79769e\+308"

# Continuous-rotation joints (drive wheels) need effectively unlimited limits.
# ±3.14159 caused wheels to lock at 180° rotation. ±1e6 is safe for PhysX
# float32 while allowing millions of revolutions.
_DRIVE_JOINT_NAMES = {"LF_DRIVE", "LM_DRIVE", "LR_DRIVE", "RF_DRIVE", "RM_DRIVE", "RR_DRIVE"}
# (attribute_name, replacement_value) applied in order; order is load-bearing
# because later passes (drive-joint widening) rely on the ±3.14159 markers.
_LIMIT_REPLACEMENTS = [
    (re.compile(rf'{_attr}="{_DBL_MAX_RE}"'), f'{_attr}="{_val}"')
    for _attr, _val in (
        ("lower", "-3.14159"),
        ("upper", "3.14159"),
        ("effort", "100"),
        ("velocity", "10"),
    )
]

_JOINT_ROOT_RE = re.compile(
    r'<joint\s+name="JointRoot"\s+type="floating">.*?</joint>\s*',
    re.DOTALL,
)

_GROUND_LINK_RE = re.compile(
    r'<link\s+name="ground">.*?</link>\s*',
    re.DOTALL,
)

_DEBRIS_SHIELD_RE = re.compile(r'(<joint\s+name="Joint_MHS_DebrisShield"\s+type=")floating(")')


def sanitize_urdf(source_path: str) -> str:
    """Rewrite the NASA JPL m2020 URDF so Isaac Sim's importer accepts it.

    Writes a sibling temp file next to ``source_path`` and returns its
    path. Caller is responsible for removing the temp file.
    """
    with open(source_path, "r", encoding="utf-8") as handle:
        content = handle.read()

    limit_count = content.count("<limit ")

    total_dblmax_replaced = 0
    for pattern, replacement in _LIMIT_REPLACEMENTS:
        content, n = pattern.subn(replacement, content)
        total_dblmax_replaced += n
    print(
        f"[sanitize] replaced {total_dblmax_replaced} DBL_MAX tokens "
        f"across {limit_count} limits"
    )

    # Widen limits for continuous-rotation drive joints. The global pass
    # above clamped all DBL_MAX to ±pi which is correct for steer/suspension
    # but locks drive wheels after 180°. Override with ±1e6.
    _DRIVE_JOINT_RE = re.compile(
        r'(<joint\s+name="(?:' + "|".join(_DRIVE_JOINT_NAMES) + r')"[^>]*>)' r"(.*?)" r"(</joint>)",
        re.DOTALL,
    )
    drive_widen_count = 0

    def _widen_drive_limits(m: re.Match) -> str:
        nonlocal drive_widen_count
        body = m.group(2)
        body = re.sub(r'lower="-3\.14159"', 'lower="-1000000"', body)
        body = re.sub(r'upper="3\.14159"', 'upper="1000000"', body)
        drive_widen_count += 1
        return m.group(1) + body + m.group(3)

    content = _DRIVE_JOINT_RE.sub(_widen_drive_limits, content)
    if drive_widen_count:
        print(f"[sanitize] widened drive joint limits to +/-1e6 ({drive_widen_count} joints)")

    content, root_removed = _JOINT_ROOT_RE.subn("", content)
    if root_removed:
        print(f"[sanitize] removed floating joint: JointRoot ({root_removed})")

    content, ground_removed = _GROUND_LINK_RE.subn("", content)
    if ground_removed:
        print(f"[sanitize] removed ground link ({ground_removed})")

    content, shield_converted = _DEBRIS_SHIELD_RE.subn(r"\1fixed\2", content)
    if shield_converted:
        print(f"[sanitize] converted Joint_MHS_DebrisShield -> fixed " f"({shield_converted})")

    if 'parent link="ground"' in content:
        raise RuntimeError(
            "[sanitize] 'ground' link still referenced as a parent after "
            "removal; manual URDF inspection required"
        )
    if 'type="floating"' in content:
        raise RuntimeError(
            '[sanitize] residual type="floating" joint detected after '
            "sanitizer pass; add explicit handling"
        )

    link_names = re.findall(r'<link\s+name="([^"]+)"', content)
    child_refs = set(re.findall(r'<child\s+link="([^"]+)"', content))
    root_candidates = [name for name in link_names if name not in child_refs]
    if len(root_candidates) != 1:
        raise RuntimeError(
            f"[sanitize] expected exactly 1 root link, found "
            f"{len(root_candidates)}: {root_candidates}"
        )
    print(f"[sanitize] articulation root link: {root_candidates[0]}")

    temp_path = source_path + ".isaac_tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return temp_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", default=DEFAULT_URDF, help="Input URDF path")
    parser.add_argument("--usd", default=DEFAULT_USD, help="Output USD path")
    return parser.parse_args()


def main() -> int:
    """Convert the sanitized m2020 URDF into a USD asset.

    Temp-file lifecycle invariant:
        The temp URDF written by ``sanitize_urdf`` is removed before
        ``os._exit(0)`` (see line 261-263 in the success branch).  The
        ``finally`` block is a fallback only -- it is reachable only
        when an exception escapes after sanitize but before
        ``URDFParseAndImportFile`` returns.  ``os._exit`` is used in
        the success and failure branches because Isaac Sim 5.x's Kit
        shutdown path heap-corrupts after URDF import, which would
        prevent normal Python finalizers from running.
    """
    args = parse_args()

    urdf_path = os.path.abspath(args.urdf)
    usd_path = os.path.abspath(args.usd)

    if not os.path.isfile(urdf_path):
        print(f"[convert_urdf_to_usd] URDF not found: {urdf_path}", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(usd_path), exist_ok=True)

    # URDFParseAndImportFile reuses an existing file at dest_path instead of
    # overwriting it. Any previous (possibly broken) USD must be removed so
    # the importer creates a fresh stage.
    if os.path.exists(usd_path):
        os.remove(usd_path)
        print(f"[convert_urdf_to_usd] Removed stale USD: {usd_path}", flush=True)

    temp_urdf = sanitize_urdf(urdf_path)
    sys.stdout.flush()

    try:
        from isaacsim import SimulationApp

        kit = SimulationApp({"renderer": "RaytracedLighting", "headless": True})

        import omni.kit.commands

        status, import_config = omni.kit.commands.execute("URDFCreateImportConfig")
        if not status:
            print(
                "[convert_urdf_to_usd] URDFCreateImportConfig failed",
                file=sys.stderr,
            )
            kit.close()
            return 2

        # NASA JPL m2020 URDF is rviz-only by default: <collision>=0,
        # mass=0 on all 115 links, 83 fixed joints for Frame_* markers.
        # The flags below absorb those defects at convert time:
        #
        # * merge_fixed_joints=True collapses Frame_* fixed-joint
        #   markers, leaving 33 articulation rigid bodies.
        # * collision_from_visuals=True synthesises collision shapes
        #   from visual meshes (URDF has no <collision> blocks).
        # * import_inertia_tensor=True: consume the URDF <inertial>
        #   mass + diagonal inertia.  ``tools/fix_urdf_inertia.py``
        #   populates the URDF with a bbox/density-derived 1025 kg
        #   distribution before this converter runs, so PhysX gets
        #   valid mass on every Body_*.  The previous False setting
        #   + ``density=500.0`` did NOT convert density to mass on
        #   the imported USD prims (USD inspection confirmed
        #   ``physics:mass=0`` on every articulation rigid body),
        #   which destabilised the PhysX articulation -- the rover
        #   collapsed at spawn.
        # * density=500.0 is preserved as a fallback for the rare
        #   Frame_* link that ends up surviving merge_fixed_joints
        #   without an explicit <inertial>.
        import_config.merge_fixed_joints = True
        import_config.collision_from_visuals = True
        import_config.density = 500.0
        import_config.convex_decomp = False
        import_config.replace_cylinders_with_capsules = True
        import_config.import_inertia_tensor = True
        import_config.fix_base = False
        import_config.self_collision = False
        import_config.create_physics_scene = False
        import_config.distance_scale = 1.0
        import_config.make_default_prim = True

        print(
            f"[convert_urdf_to_usd] Importing URDF: {temp_urdf}",
            flush=True,
        )
        print(
            f"[convert_urdf_to_usd] dest_path: {usd_path}",
            flush=True,
        )
        status, prim_path = omni.kit.commands.execute(
            "URDFParseAndImportFile",
            urdf_path=temp_urdf,
            import_config=import_config,
            dest_path=usd_path,
            get_articulation_root=True,
        )
        if not status:
            print(
                "[convert_urdf_to_usd] URDFParseAndImportFile failed",
                file=sys.stderr,
            )
            # kit.close() skipped: Isaac Sim 5.x shutdown path heap-corrupts
            # after URDF import. Bypass via os._exit to guarantee the shell
            # wrapper sees our failure code (3).
            # kit.close()
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(3)

        print(f"[convert_urdf_to_usd] Imported root prim: {prim_path}", flush=True)

        # Success path: clean up temp URDF and verify outputs BEFORE attempting
        # any Kit shutdown. The finally block is unreliable because kit.close()
        # triggers a heap-corruption abort in Isaac Sim 5.x that prevents
        # Python finalizers from running.
        if os.path.exists(temp_urdf):
            os.remove(temp_urdf)
            print(f"[convert_urdf_to_usd] Removed temp URDF: {temp_urdf}", flush=True)

        # Wrapper USD is a thin sublayers+references file (~1.5 KB in practice);
        # the heavy mesh data lives in configuration/m2020_base.usd below.
        if not os.path.isfile(usd_path) or os.path.getsize(usd_path) < 512:
            print(
                f"[convert_urdf_to_usd] USD wrapper missing or too small: {usd_path}",
                file=sys.stderr,
            )
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(4)

        base_usd_path = os.path.join(os.path.dirname(usd_path), "configuration", "m2020_base.usd")
        if not os.path.isfile(base_usd_path) or os.path.getsize(base_usd_path) < 1024 * 1024:
            print(
                f"[convert_urdf_to_usd] base USD missing or too small "
                f"(meshes not serialized?): {base_usd_path}",
                file=sys.stderr,
            )
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(5)

        print(
            f"[convert_urdf_to_usd] Verified base USD: "
            f"{base_usd_path} ({os.path.getsize(base_usd_path)} bytes)",
            flush=True,
        )
        print("[convert_urdf_to_usd] Done.", flush=True)
        sys.stdout.flush()
        sys.stderr.flush()

        # kit.close() skipped: Isaac Sim 5.x shutdown path heap-corrupts after
        # URDF import (corrupted double-linked list in simulation_app.py:838).
        # All outputs are already on disk and verified above, so os._exit(0)
        # returns success to the shell wrapper without touching the broken
        # shutdown path. Keep the call commented for documentation.
        # kit.close()
        os._exit(0)
    finally:
        # Fallback only: the success and failure branches above already clean
        # up via os._exit, but if sanitize_urdf succeeds and an exception is
        # raised before URDFParseAndImportFile returns, we still want the
        # temp file gone.
        if os.path.exists(temp_urdf):
            os.remove(temp_urdf)


if __name__ == "__main__":
    raise SystemExit(main())
