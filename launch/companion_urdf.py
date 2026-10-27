"""Prepare the companion's URDF without importing the MarsLab runtime."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit

_MESH_PATH_RE = re.compile(r"""(<mesh\b[^>]*?\bfilename=)(["'])([^"']+)\2""")
_JOINT_ROOT_BLOCK_RE = re.compile(
    r'<joint\s+name="JointRoot"\s+type="floating"\s*>.*?</joint>\s*',
    flags=re.DOTALL,
)
_GROUND_LINK_RE = re.compile(r'<link\s+name="ground">.*?</link>\s*', flags=re.DOTALL)


def resolve_companion_settings(
    config_path: str,
    *,
    robot: str = "",
    urdf_path: str = "",
    namespace: str = "",
    joint_states_topic: str = "",
) -> dict[str, str]:
    """Use the simulation's scenario/profile merge for companion defaults.

    This imports the pure configuration API, without Isaac Sim or ROS bindings.
    Explicit launch values retain precedence over the selected profile.
    """
    repository_root = str(Path(__file__).resolve().parents[1])
    if repository_root not in sys.path:
        sys.path.insert(0, repository_root)
    try:
        from marslab.config import load_config
    except ImportError as exc:
        raise RuntimeError(
            "Loading a MarsLab companion profile requires the project's PyYAML and "
            "Pydantic 2 dependencies in the ROS Python environment."
        ) from exc

    config = load_config(config_path, robot=robot or None)
    rover = config.rover
    return {
        "robot": rover.name,
        "urdf_path": urdf_path or str(rover.urdf_source_path),
        "namespace": namespace or rover.ros2.namespace,
        "joint_states_topic": joint_states_topic or rover.ros2.topics.joint_states,
    }


def sanitize_urdf_for_robot_state_publisher(urdf_text: str) -> str:
    """Retain rover URDFs, applying the two legacy M2020 floating-joint fixes."""
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


def robot_root_link(urdf_text: str) -> str:
    """Resolve the prepared URDF's root for the base_link identity connector."""
    robot = ET.fromstring(urdf_text)
    links = {link.attrib["name"] for link in robot.findall("link")}
    children = {child.attrib["link"] for child in robot.findall("joint/child")}
    roots = links - children
    if len(roots) != 1:
        raise ValueError(f"Rover URDF must have exactly one root link; found {sorted(roots)}")
    return roots.pop()


def build_robot_description(urdf_path: str) -> str:
    """Read, prepare, and resolve the URDF owned by robot_state_publisher."""
    path = Path(urdf_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"URDF not found at {str(path)!r}. Set urdf_path:=<abs path> when launching."
        )
    urdf_text = sanitize_urdf_for_robot_state_publisher(path.read_text(encoding="utf-8"))
    return rewrite_mesh_paths_to_file_uri(urdf_text, path.parent)
