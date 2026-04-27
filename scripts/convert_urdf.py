"""Generic URDF to USD conversion utility (Isaac Sim importer).

Converts an arbitrary URDF file to USD format using Isaac Sim's URDF
importer and saves the result as a USD file.

For NASA JPL m2020 Perseverance specifically, use
``scripts/phase1/convert_urdf_to_usd.py`` instead.  That variant
handles JPL-specific URDF sanitization (DBL_MAX joint limits, the
floating root joint, mass/inertia placeholders) which this generic
converter does not perform.

Run with: ~/isaacsim/python.sh scripts/convert_urdf.py --urdf <path>
"""

import argparse
import os
import sys

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})

import omni.kit.commands  # noqa: E402
import omni.usd  # noqa: E402


def main() -> None:
    """Convert URDF to USD."""
    parser = argparse.ArgumentParser(description="Convert URDF to USD")
    parser.add_argument("--urdf", required=True, help="Path to URDF file")
    parser.add_argument("--output", default=None, help="Output USD path (default: same dir)")
    args = parser.parse_args()

    urdf_path = os.path.abspath(args.urdf)
    if not os.path.isfile(urdf_path):
        print(f"Error: URDF not found: {urdf_path}")
        sys.exit(1)

    _, import_config = omni.kit.commands.execute("URDFCreateImportConfig")
    import_config.merge_fixed_joints = False
    import_config.fix_base = False

    result = omni.kit.commands.execute(
        "URDFParseAndImportFile",
        urdf_path=urdf_path,
        import_config=import_config,
    )

    robot_path = result if isinstance(result, str) else result[1]
    print(f"[convert_urdf] Imported: {robot_path}")

    if args.output:
        output_path = os.path.abspath(args.output)
        omni.usd.get_context().save_as_stage(output_path)
        print(f"[convert_urdf] Saved: {output_path}")

    simulation_app.close()
    print("[convert_urdf] Done.")


if __name__ == "__main__":
    main()
