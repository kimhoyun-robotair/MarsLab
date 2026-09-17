"""Prepare the companion's URDF without importing the MarsLab runtime."""

from __future__ import annotations

import re
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit


_MESH_PATH_RE = re.compile(r'''(<mesh\b[^>]*?\bfilename=)(["'])([^"']+)\2''')
_JOINT_ROOT_BLOCK_RE = re.compile(
    r'<joint\s+name="JointRoot"\s+type="floating"\s*>.*?</joint>\s*',
    flags=re.DOTALL,
)
_GROUND_LINK_RE = re.compile(r'<link\s+name="ground">.*?</link>\s*', flags=re.DOTALL)


def sanitize_urdf_for_robot_state_publisher(urdf_text: str) -> str:
    """Root articulation at Body_Chassis and fix the unsupported floating shield."""
    out = _JOINT_ROOT_BLOCK_RE.sub("", urdf_text)
    out = _GROUND_LINK_RE.sub("", out)
    return re.sub(
        r'(<joint\s+name="Joint_MHS_DebrisShield"\s+type=")floating(")',
        r"\1fixed\2",
        out,
    )


def rewrite_mesh_paths_to_file_uri(urdf_text: str, urdf_dir: str | Path) -> str:
    """Resolve the rover's relative mesh references for the companion process."""
    abs_dir = Path(urdf_dir).resolve()

    def _replace(match: re.Match[str]) -> str:
        filename = unescape(match.group(3))
        if Path(filename).is_absolute() or urlsplit(filename).scheme:
            return match.group(0)
        mesh_uri = (abs_dir / filename).resolve().as_uri()
        return f"{match.group(1)}{match.group(2)}{mesh_uri}{match.group(2)}"

    return _MESH_PATH_RE.sub(_replace, urdf_text)


def build_robot_description(urdf_path: str) -> str:
    """Read, prepare, and resolve the URDF owned by robot_state_publisher."""
    path = Path(urdf_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"URDF not found at {str(path)!r}. Set urdf_path:=<abs path> when launching."
        )
    urdf_text = sanitize_urdf_for_robot_state_publisher(path.read_text(encoding="utf-8"))
    return rewrite_mesh_paths_to_file_uri(urdf_text, path.parent)
