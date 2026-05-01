#!/usr/bin/env python3
"""One-shot rewriter that fills the JPL m2020 URDF with valid mass + inertia.

Background
----------
``assets/m2020-urdf-models/rover/m2020.urdf`` is the JPL-exported
*kinematics-only* URDF (file head says ``commit_time: 2021-08-16``,
``Tool url: git@github.jpl.nasa.gov:CR/rst.git``).  Every one of the
115 ``<link>`` blocks declares ``<mass value="0"/>`` and
``<inertia ixx="0" ... izz="0"/>``.  Consequences:

* RViz ``RobotModel`` "Mass Properties" overlay rejects 28 visual
  links with ``unrealistic inertia, so the equivalent inertia box
  will not be shown``.
* Isaac Sim PhysX dynamics for the 22 non-overridden links
  (RA arm / RSM / HGA / Stabilizers / Caps / Turret / Differential)
  start from zero mass; the YAML override
  (``configs/robots/rover_m2020.yaml``) covers only chassis + 6 wheels
  + 4 suspension elements.

This script rewrites the URDF text in-place so:

* ``Body_Chassis`` carries the chassis bulk (electronics + MMRTG +
  cabling): ``670 kg`` (book-keeping below).
* The 6 wheels carry ``30 kg`` each (aluminum, 0.525 m diameter,
  0.4 m wide -- bbox approximation).
* The 4 rocker-bogie links + 2 differential bars carry ballpark masses
  consistent with their titanium-tube construction.
* The 5-DOF robotic arm distributes 25 kg across RA_Link1..5 plus a
  4 kg ``Body_RA_Base`` mount, with the 45 kg turret split among
  ``Body_Turret`` (housing) + ``Body_CorerFeed`` (drill / corer
  assembly, the heaviest piece) + ``Body_StabilizerNear/Far`` +
  ``Body_WATSON_Cap`` + ``Body_SHERLOC_Cap``.
* The mast (``Body_RSM_AZ``, ``Body_RSM_EL``), HGA, and
  ``Body_MHS_DebrisShield`` get small but realistic masses.
* Every ``Frame_*`` (joint frame, no visual) gets a 0.01 kg
  placeholder with a 1e-6 identity inertia so urdf_parser stays happy
  without polluting RViz Mass Properties (Frame_* have no visual so
  RViz never tries to draw an inertia box for them).
* ``ground`` (deleted at runtime by
  ``rewrite_urdf_root_to_base_link``) gets the same
  ``Frame_*`` placeholder so a stray usage outside the rewrite path
  still parses.

Sum of ``Body_*`` masses = 1025 kg, matching the published Mars 2020
total (NASA Fact Sheet, ``mars.nasa.gov/files/mars2020/Mars2020_Fact_Sheet.pdf``).

Inertia model
-------------
Each link is approximated as a uniform-density solid box whose
dimensions reflect the visible mesh extent.  For a box with mass ``m``
and half-extents ``(a, b, c)`` along x/y/z, the principal moments are:

    Ixx = m/12 * (b**2 + c**2)
    Iyy = m/12 * (a**2 + c**2)
    Izz = m/12 * (a**2 + b**2)

Off-diagonal terms (ixy, ixz, iyz) are set to 0 -- the URDF link
``origin`` (CoM offset) is preserved as JPL authored it, so the
solid-box approximation is taken in the link's own inertial frame.

Usage
-----
::

    python3 tools/fix_urdf_inertia.py

Idempotent: reads the URDF, replaces each ``<mass value="0"/>`` and
``<inertia ... ="0" .../>`` line, writes back.  Re-running on an
already-fixed URDF is a no-op (the regex anchors require the literal
``"0"`` zeros that only the JPL-exported original carries).

Sources cited
-------------
* Total rover mass 1025 kg: NASA Mars 2020 Fact Sheet, March 2020.
* Wheel diameter 52.5 cm, aluminum: NASA / JPL "Mars 2020 Rover Gets
  Its Wheels", 2019.
* Robotic-arm turret mass 45 kg, arm length 2.1 m, 5-DOF: JPL
  Perseverance Mission Press Kit, 2020.
* Rocker-bogie titanium tubes: NASA Science -- Perseverance Rover
  Components page.
* Mastcam-Z mounting on RSM ~2 m above surface: Bell et al. 2021,
  Space Science Reviews.

Per-link masses below are book-kept so total ``Body_*`` = 1025 kg
exactly (no rounding drift).  Bbox dimensions are eyeballed from the
.gltf mesh extents inside ``assets/m2020-urdf-models/rover/meshes/``
plus the URDF link origins; they are not load-bearing for this fix
because RViz's reject criterion is simply ``mass > 0`` plus a
positive-definite inertia tensor, both of which the box approximation
satisfies trivially for any non-degenerate ``(a, b, c)``.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
URDF_PATH = REPO_ROOT / "assets" / "m2020-urdf-models" / "rover" / "m2020.urdf"


# (mass_kg, bbox_x, bbox_y, bbox_z) per Body_* link.
# Sum check at module-load time: must equal 1025 kg.
_BODY_LINKS: dict[str, tuple[float, float, float, float]] = {
    # Chassis: bulk of the rover (MMRTG + electronics + cabling).
    "Body_Chassis": (670.0, 2.0, 1.4, 1.0),
    # Six aluminum wheels, 0.525 m diameter, 0.4 m wide.
    "Body_WheelLeftFront": (30.0, 0.525, 0.4, 0.525),
    "Body_WheelLeftMiddle": (30.0, 0.525, 0.4, 0.525),
    "Body_WheelLeftRear": (30.0, 0.525, 0.4, 0.525),
    "Body_WheelRightFront": (30.0, 0.525, 0.4, 0.525),
    "Body_WheelRightMiddle": (30.0, 0.525, 0.4, 0.525),
    "Body_WheelRightRear": (30.0, 0.525, 0.4, 0.525),
    # Steering actuators (electric motor + reduction).
    "Body_SteerLeftFront": (4.0, 0.15, 0.15, 0.25),
    "Body_SteerLeftRear": (4.0, 0.15, 0.15, 0.25),
    "Body_SteerRightFront": (4.0, 0.15, 0.15, 0.25),
    "Body_SteerRightRear": (4.0, 0.15, 0.15, 0.25),
    # Rocker-bogie suspension (titanium tubes).
    "Body_RockerLeft": (18.0, 1.5, 0.1, 0.4),
    "Body_RockerRight": (18.0, 1.5, 0.1, 0.4),
    "Body_BogieLeft": (12.0, 1.0, 0.1, 0.3),
    "Body_BogieRight": (12.0, 1.0, 0.1, 0.3),
    # Center differential bar.
    "Body_Differential": (8.0, 0.5, 1.5, 0.1),
    # 5-DOF robotic arm (2.1 m total, 25 kg w/o turret per Press Kit
    # subtraction: arm 70 kg total - 45 kg turret = 25 kg arm links).
    "Body_RA_Base": (4.0, 0.2, 0.2, 0.2),
    "Body_RA_Link1": (7.0, 0.4, 0.15, 0.15),
    "Body_RA_Link2": (6.0, 0.5, 0.12, 0.12),
    "Body_RA_Link3": (5.0, 0.5, 0.10, 0.10),
    "Body_RA_Link4": (4.0, 0.3, 0.10, 0.10),
    "Body_RA_Link5": (3.0, 0.2, 0.10, 0.10),
    # Turret (45 kg total per Press Kit).
    "Body_Turret": (5.0, 0.3, 0.3, 0.3),
    "Body_CorerFeed": (30.0, 0.6, 0.2, 0.2),
    "Body_StabilizerFar": (2.0, 0.05, 0.05, 0.4),
    "Body_StabilizerNear": (2.0, 0.05, 0.05, 0.3),
    "Body_WATSON_Cap": (3.0, 0.15, 0.15, 0.2),
    "Body_SHERLOC_Cap": (3.0, 0.15, 0.15, 0.2),
    # Remote Sensing Mast (mast tower + Mastcam-Z + NavCam plate).
    "Body_RSM_AZ": (2.0, 0.2, 0.2, 0.3),
    "Body_RSM_EL": (8.0, 0.4, 0.4, 0.3),
    # High Gain Antenna.
    "Body_HGA_AZ": (1.0, 0.15, 0.15, 0.15),
    "Body_HGA_EL": (4.0, 0.3, 0.3, 0.05),
    # MHS Debris Shield (panel cover).
    "Body_MHS_DebrisShield": (2.0, 0.5, 0.5, 0.05),
}

# Frame_* and ``ground`` placeholder: 0.01 kg + 1e-6 identity inertia.
# These have no visual mesh (verified by inspection), so RViz Mass
# Properties never tries to render an inertia box for them; the
# placeholder exists purely to keep urdf_parser's positive-definite
# check happy if any consumer ever reads them.
_PLACEHOLDER_MASS = 0.01
_PLACEHOLDER_INERTIA = 1e-6


def _box_inertia(mass: float, a: float, b: float, c: float) -> tuple[float, float, float]:
    """Return (Ixx, Iyy, Izz) for a uniform solid box of given dims."""
    ixx = mass / 12.0 * (b * b + c * c)
    iyy = mass / 12.0 * (a * a + c * c)
    izz = mass / 12.0 * (a * a + b * b)
    return ixx, iyy, izz


_LINK_RE = re.compile(r'(<link\s+name="([^"]+)">)(.*?)(</link>)', re.DOTALL)
_MASS_RE = re.compile(r'<mass\s+value="0"\s*/>')
_INERTIA_RE = re.compile(
    r'<inertia\s+ixx="0"\s+ixy="0"\s+ixz="0"\s+iyy="0"\s+iyz="0"\s+izz="0"\s*/>'
)


def _build_replacement_for_link(name: str) -> tuple[str, str]:
    """Return ``(mass_xml, inertia_xml)`` for ``name``."""
    if name in _BODY_LINKS:
        mass, a, b, c = _BODY_LINKS[name]
        ixx, iyy, izz = _box_inertia(mass, a, b, c)
    else:
        # Frame_* or ground -- placeholder.
        mass = _PLACEHOLDER_MASS
        ixx = iyy = izz = _PLACEHOLDER_INERTIA
    mass_xml = f'<mass value="{mass:.4f}"/>'
    inertia_xml = (
        f'<inertia ixx="{ixx:.6e}" ixy="0" ixz="0" ' f'iyy="{iyy:.6e}" iyz="0" izz="{izz:.6e}"/>'
    )
    return mass_xml, inertia_xml


def fix_urdf_inertia(urdf_path: Path = URDF_PATH) -> dict[str, float]:
    """Rewrite ``urdf_path`` in place, return ``{link_name: mass}`` map."""
    text = urdf_path.read_text(encoding="utf-8")

    masses_applied: dict[str, float] = {}

    def _replace_link(match: re.Match[str]) -> str:
        head, name, body, tail = match.group(1), match.group(2), match.group(3), match.group(4)
        mass_xml, inertia_xml = _build_replacement_for_link(name)
        body = _MASS_RE.sub(mass_xml, body, count=1)
        body = _INERTIA_RE.sub(inertia_xml, body, count=1)
        if name in _BODY_LINKS:
            masses_applied[name] = _BODY_LINKS[name][0]
        return f"{head}{body}{tail}"

    new_text = _LINK_RE.sub(_replace_link, text)
    urdf_path.write_text(new_text, encoding="utf-8")
    return masses_applied


def _verify_total_mass() -> None:
    """Module-load-time sanity check: Body_* sum == 1025 kg."""
    total = sum(spec[0] for spec in _BODY_LINKS.values())
    expected = 1025.0
    if abs(total - expected) > 0.01:
        raise AssertionError(
            f"Body_* mass sum is {total:.2f} kg, expected {expected:.2f} kg "
            "(NASA Mars 2020 Fact Sheet)"
        )


_verify_total_mass()


if __name__ == "__main__":
    applied = fix_urdf_inertia()
    print(f"Rewrote {len(applied)} Body_* links in {URDF_PATH}.")
    print(f"Total Body_* mass: {sum(applied.values()):.2f} kg")
