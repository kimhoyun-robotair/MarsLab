"""Publish the M2020 URDF on ``/robot_description`` for RViz RobotModel display.

Without this publisher RViz shows only the wireframe TF tree and no
rover mesh.

Design constraints adopted from
``marslab/ros2_bridge/odometry_publisher.py``:

* ``rclpy`` imports are deferred to function bodies so the module is
  importable without a ROS 2 distro on PYTHONPATH.  Unit tests stub
  ``std_msgs`` / ``rclpy.qos`` via ``monkeypatch.setitem(sys.modules, ...)``
  exactly like ``tests/unit/test_tf_broadcaster.py:14-27``.
* Returning a context dataclass (mirroring
  :class:`OdometryPublisherContext` at ``odometry_publisher.py:37-52``)
  keeps the publisher handle alive after ``init_rclpy_side`` returns; if
  the caller drops the handle, rclpy garbage-collects the publisher and
  the latched ``transient_local`` sample disappears.

QoS rationale: RViz's ``RobotModel`` display subscribes to the URDF topic
with ``RELIABLE`` + ``TRANSIENT_LOCAL``.  When the publisher is
``VOLATILE`` (the default), an RViz that connects after the runtime
boots never receives the URDF and shows the "RobotModel: No transform"
error.
``TRANSIENT_LOCAL`` makes the latest sample latch on the publisher side
so late joiners get it on subscription.  Depth is 1 because the URDF is
published exactly once.

Mesh-path rewriting: the JPL m2020 URDF references mesh files as
``./meshes/CHASSIS.gltf`` (relative to the URDF directory).  RViz cannot
resolve relative paths because the RViz process has a different CWD.
The fix is to rewrite each ``./meshes/X`` reference to an absolute
``file:///abs/.../meshes/X`` URI.  ``package://`` and ``http://`` URIs
are passed through untouched so a future scenario that ships meshes via
ROS package resource lookup keeps working.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Optional

__all__ = [
    "RobotDescriptionContext",
    "publish_robot_description",
    "rewrite_mesh_paths_to_file_uri",
    "rewrite_urdf_root_to_base_link",
]


# Regex matches the exact JPL m2020 form ``filename="./meshes/X"`` (or
# ``filename="meshes/X"``) but only when the filename does NOT already
# carry a recognised URI scheme.  ``(?!file://|http://|package://)`` is a
# negative lookahead so already-rewritten input is left alone — that is
# what makes :func:`rewrite_mesh_paths_to_file_uri` idempotent.
_MESH_PATH_RE = re.compile(r'<mesh\s+filename="(?!file://|http://|package://)\.?/?meshes/([^"]+)"')


# Root-rename regexes.  See :func:`rewrite_urdf_root_to_base_link` for
# the full rationale.

# Match the entire ``<joint name="JointRoot" type="floating">...</joint>``
# block.  The block is anchored on BOTH ``name="JointRoot"`` and
# ``type="floating"`` so the regex is naturally idempotent (a re-run finds
# nothing) and so a future ``name="JointRootSensor"`` cannot accidentally
# match (``\s+`` after the closing ``"`` blocks the substring extension).
# The non-greedy ``.*?</joint>`` with ``re.DOTALL`` stops at the first
# closing ``</joint>`` tag without crossing into the next sibling joint.
# Verified against ``assets/m2020-urdf-models/rover/m2020.urdf:1029-1033``
# (block) and ``:1034`` (``Joint_MHS_DebrisShield`` immediately after).
# The trailing ``\s*`` consumes the newline + tab between the deleted
# block and the next sibling so cleanup is whitespace-clean.
#
# An earlier approach only flipped ``floating`` -> ``fixed`` and left
# the joint's ``<parent link="ground"/>`` reference dangling, which
# urdf_parser/src/model.cpp:253 rejects with
# "parent link [ground] of joint [JointRoot] not found".  Removing the
# whole block makes ``base_link`` the URDF tree root by elimination
# (every other joint's parent is one of ``Body_Chassis``, ``Body_*``,
# never ``ground``, verified by single-grep match for the literal
# ``parent link="ground"``).
_JOINT_ROOT_BLOCK_RE = re.compile(
    r'<joint\s+name="JointRoot"\s+type="floating"\s*>.*?</joint>\s*',
    flags=re.DOTALL,
)

# Match ``<link name="ground">...</link>`` placeholder.  ``re.DOTALL``
# lets ``.`` cross newlines so the multi-line inertial block is captured
# without crossing into a sibling link.  The JPL m2020 URDF has exactly
# one such block (verified at ``assets/m2020-urdf-models/rover/m2020.urdf:6``).
_GROUND_LINK_RE = re.compile(
    r'<link\s+name="ground">.*?</link>\s*',
    flags=re.DOTALL,
)

# Match ``Body_Chassis`` only when bounded on both sides by whitespace
# or ``"`` (so a future ``Body_ChassisExtension`` link is not silently
# mangled).  The JPL m2020 URDF currently has 46 occurrences across
# link declarations and joint parent/child references; the global
# substitution renames them all.
_BODY_CHASSIS_RE = re.compile(r'(["\s])Body_Chassis(["\s])')


@dataclass
class RobotDescriptionContext:
    """Handles + state retained across the runtime main loop.

    Attributes:
        publisher: The ``rclpy.publisher.Publisher`` for ``std_msgs/String``.
            Held by the caller so rclpy does not garbage-collect it (the
            ``transient_local`` latched sample lives on the publisher).
        node: The owning ``rclpy.node.Node``.  Kept around so a future
            re-publish (URDF hot-swap) can call ``publisher.publish``
            without re-creating the publisher.
        urdf_text: The mesh-path-rewritten URDF string that was actually
            published.  Stored verbatim so a unit test or runtime
            inspection can verify the published content without
            round-tripping through rclpy.
        topic: The fully-qualified topic name (default ``/robot_description``).
    """

    publisher: Any
    node: Any
    urdf_text: str
    topic: str


def rewrite_mesh_paths_to_file_uri(urdf_text: str, urdf_dir: str) -> str:
    """Rewrite relative ``<mesh filename="./meshes/X"/>`` to absolute file:// URIs.

    The function is **idempotent** by design: running it twice on the
    same input produces the same output, because the regex skips inputs
    that already carry a ``file://``, ``http://``, or ``package://``
    scheme.  This matters because the integration call site
    (``init_rclpy_side``) may be invoked twice in a single Isaac Sim
    session if the user resets the simulation.

    Args:
        urdf_text: Raw URDF XML as a string.  Not parsed structurally —
            this function operates on the text via regex so XML comments,
            whitespace, and attribute order are preserved exactly.
        urdf_dir: Directory containing the URDF file.  Mesh paths are
            resolved relative to this directory.  Made absolute via
            ``os.path.abspath`` before being substituted, so the caller
            may pass a relative directory.

    Returns:
        The URDF string with each matching ``filename="./meshes/X"`` (or
        ``filename="meshes/X"``) replaced by
        ``filename="file:///{abs(urdf_dir)}/meshes/X"``.

    Examples:
        >>> rewrite_mesh_paths_to_file_uri(
        ...     '<mesh filename="./meshes/CHASSIS.gltf"/>',
        ...     '/home/user/m2020',
        ... )
        '<mesh filename="file:///home/user/m2020/meshes/CHASSIS.gltf"/>'
    """
    abs_dir = os.path.abspath(urdf_dir)

    def _replace(match: re.Match[str]) -> str:
        rel_path = match.group(1)
        return f'<mesh filename="file://{abs_dir}/meshes/{rel_path}"'

    return _MESH_PATH_RE.sub(_replace, urdf_text)


def rewrite_urdf_root_to_base_link(urdf_text: str) -> str:
    """Bring the JPL m2020 URDF in line with the REP-105 ``base_link`` root.

    Three text-level edits, applied in order:

    1. Strip the entire ``<joint name="JointRoot" type="floating">...</joint>``
       block.  The joint's ``<parent link="ground"/>`` reference would
       otherwise dangle after step 2, and urdf_parser/src/model.cpp:253
       rejects dangling joint parents
       ("Failed to build tree: parent link [ground] of joint [JointRoot]
       not found").  After deletion, ``base_link`` (renamed in step 3)
       becomes the natural URDF tree root because no other joint has
       ``parent link="ground"`` in the m2020 URDF.
    2. Strip the ``<link name="ground">...</link>`` block (URDF-import
       placeholder, not a real kinematic body).  Done after step 1 so
       step 1's regex anchor never depends on whether step 2 ran first.
    3. Rename every ``Body_Chassis`` reference (link declaration +
       parent / child links on every joint) to ``base_link`` so the
       URDF agrees with the OG-side TF tree (the rover articulation
       root carries ``isaac:nameOverride="base_link"``).

    The function is **idempotent** by construction: a second pass finds
    no JointRoot block, no ``ground`` link block, and no
    ``Body_Chassis`` token -- all three regexes degenerate to no-ops.

    Args:
        urdf_text: Raw URDF XML as a string.  Operated on as text via
            regex (no XML parsing) so attribute order, whitespace, and
            comments are preserved exactly.

    Returns:
        The rewritten URDF string.

    Notes:
        Without this rewrite, RViz reports
        "RobotModel: No transform from [Body_Chassis] to [odom]" and
        renders nothing because the URDF root link name disagrees with
        the OmniGraph-published frame_id.  Citation: JPL URDF root
        layout at ``assets/m2020-urdf-models/rover/m2020.urdf:6,1029-1033``.
    """
    out = _JOINT_ROOT_BLOCK_RE.sub("", urdf_text)
    out = _GROUND_LINK_RE.sub("", out)
    out = _BODY_CHASSIS_RE.sub(r"\1base_link\2", out)
    return out


def _build_default_qos() -> Any:
    """Construct ``TRANSIENT_LOCAL + RELIABLE + KEEP_LAST(1)`` QoS.

    Lazy ``rclpy.qos`` import keeps the module importable without rclpy
    on PYTHONPATH (offline unit tests under ``tests/unit/``).  The
    profile is the canonical RViz ``RobotModel`` subscriber profile so a
    late-joining RViz still latches the URDF.
    """
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
    rename_root_to_base_link: bool = True,
) -> RobotDescriptionContext:
    """Read the URDF, rewrite mesh paths, publish once on a latched topic.

    Args:
        node: A ``rclpy.node.Node`` instance.  The publisher is created
            on this node, so its lifetime governs the topic's lifetime.
        urdf_path: Filesystem path to the URDF.  Resolved with
            ``os.path.abspath`` for the error message and to derive the
            mesh directory.
        topic: Fully-qualified topic name.  Default ``/robot_description``
            matches the ROS convention that RViz auto-discovers.
        qos: Optional ``rclpy.qos.QoSProfile``.  When ``None`` the
            function builds the canonical RViz profile
            (``RELIABLE`` + ``TRANSIENT_LOCAL`` + ``KEEP_LAST(1)``) so a
            late-joining RViz subscriber still latches the URDF.
        rename_root_to_base_link: When ``True`` (default for backwards
            compatibility with the OmniGraph PubTF + nameOverride
            workflow) the URDF root link ``Body_Chassis`` is rewritten
            to ``base_link``.  Pass ``False`` to keep the URDF link
            names verbatim so the published URDF matches the OmniGraph
            ``ROS2PublishJointState`` joint owners (single source of
            truth for ``robot_state_publisher`` consumption).

    Returns:
        :class:`RobotDescriptionContext` so the caller can keep the
        publisher alive (rclpy garbage-collects publishers whose
        Python-side reference is dropped).

    Raises:
        FileNotFoundError: When ``urdf_path`` does not exist.  The
            absolute path is included in the message so a typo in
            ``configs/robots/rover_m2020.yaml`` surfaces immediately.
    """
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
    # Optional rewrite of the URDF root link from ``Body_Chassis`` to
    # ``base_link``.  Required for the legacy OmniGraph PubTF +
    # ``isaac:nameOverride='base_link'`` workflow because the
    # OmniGraph-published frame_id had to agree with the URDF root.
    # The robot_state_publisher workflow does not require renaming --
    # the SLAM stack's ``base_frame`` accepts any frame name via launch param
    # -- so callers passing ``rename_root_to_base_link=False`` get the
    # URDF verbatim, which is the single-source-of-truth path.
    urdf_text = rewrite_urdf_root_to_base_link(raw_urdf) if rename_root_to_base_link else raw_urdf
    urdf_text = rewrite_mesh_paths_to_file_uri(urdf_text, urdf_dir)

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
