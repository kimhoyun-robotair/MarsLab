"""Publish the rover URDF for robot-state visualization.
Mesh references become file URIs before the latched message is sent.
ROS bindings remain deferred for offline import tests."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Optional

__all__ = [
    "RobotDescriptionContext",
    "publish_robot_description",
    "rewrite_mesh_paths_to_file_uri",
]


_MESH_PATH_RE = re.compile(r'<mesh\s+filename="(?!file://|http://|package://)\.?/?meshes/([^"]+)"')


_JOINT_ROOT_BLOCK_RE = re.compile(
    r'<joint\s+name="JointRoot"\s+type="floating"\s*>.*?</joint>\s*',
    flags=re.DOTALL,
)

_GROUND_LINK_RE = re.compile(
    r'<link\s+name="ground">.*?</link>\s*',
    flags=re.DOTALL,
)


@dataclass
class RobotDescriptionContext:
    """Handles + state retained across the runtime main loop."""

    publisher: Any
    node: Any
    urdf_text: str
    topic: str


def rewrite_mesh_paths_to_file_uri(urdf_text: str, urdf_dir: str) -> str:
    """Rewrite relative ``<mesh filename="./meshes/X"/>`` to absolute file:// URIs."""
    abs_dir = os.path.abspath(urdf_dir)

    def _replace(match: re.Match[str]) -> str:
        rel_path = match.group(1)
        return f'<mesh filename="file://{abs_dir}/meshes/{rel_path}"'

    return _MESH_PATH_RE.sub(_replace, urdf_text)


def _build_default_qos() -> Any:
    """Construct ``TRANSIENT_LOCAL + RELIABLE + KEEP_LAST(1)`` QoS."""
    from rclpy.qos import (  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope
        DurabilityPolicy,
        HistoryPolicy,
        QoSProfile,
        ReliabilityPolicy,
    )

    return QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
    )


def publish_robot_description(
    node: Any,
    urdf_path: str,
    *,
    topic: str = "/robot_description",
    qos: Optional[Any] = None,
) -> RobotDescriptionContext:
    """Read the URDF, rewrite mesh paths, publish once on a latched topic."""
    from std_msgs.msg import (
        String,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    abs_urdf_path = os.path.abspath(urdf_path)
    if not os.path.isfile(abs_urdf_path):
        raise FileNotFoundError(
            f"URDF not found at {abs_urdf_path!r} "
            "(robot_description publisher cannot read the file)"
        )

    with open(abs_urdf_path, encoding="utf-8") as fh:
        raw_urdf = fh.read()

    urdf_dir = os.path.dirname(abs_urdf_path)
    urdf_text = rewrite_mesh_paths_to_file_uri(raw_urdf, urdf_dir)

    resolved_qos = qos if qos is not None else _build_default_qos()
    publisher = node.create_publisher(String, topic, resolved_qos)

    msg = String()
    msg.data = urdf_text
    publisher.publish(msg)

    return RobotDescriptionContext(
        publisher=publisher,
        node=node,
        urdf_text=urdf_text,
        topic=topic,
    )
