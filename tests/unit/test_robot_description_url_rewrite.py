"""Cover for ``rewrite_urdf_root_to_base_link``.

The function does three text-level rewrites on the JPL m2020 URDF so
the URDF root link agrees with the OG-side TF tree's ``base_link``
frame_id. Tests exercise the helper on:

* a synthetic minimal URDF (anchors + idempotency),
* the actual ``assets/m2020-urdf-models/rover/m2020.urdf`` (smoke
  check the global rewrite hits every reference + parses with
  ``xml.etree.ElementTree`` as a urdf_parser sanity proxy).

The current rewrite removes the JointRoot block entirely so
``base_link`` becomes the natural URDF tree root. An earlier "switch
JointRoot to fixed" approach left ``<parent link="ground"/>``
dangling, which ``urdf_parser/src/model.cpp`` rejects. Tests below
pin the current behaviour.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from marslab.ros2_bridge.robot_description_publisher import (
    rewrite_urdf_root_to_base_link,
)

# ---------------------------------------------------------------------------
# Synthetic URDF fixture
# ---------------------------------------------------------------------------


_SYNTHETIC_URDF = """<?xml version="1.0"?>
<robot name="m2020">
  <link name="ground">
    <inertial>
      <mass value="0"/>
      <inertia ixx="0" ixy="0" ixz="0" iyy="0" iyz="0" izz="0"/>
    </inertial>
  </link>
  <link name="Body_Chassis">
    <visual><geometry><box size="1 1 0.5"/></geometry></visual>
  </link>
  <joint name="JointRoot" type="floating">
    <origin xyz="0 0 0" rpy="0 -0 0"/>
    <parent link="ground"/>
    <child link="Body_Chassis"/>
  </joint>
  <joint name="WheelFL" type="revolute">
    <parent link="Body_Chassis"/>
    <child link="Body_WheelLeftFront"/>
    <axis xyz="0 1 0"/>
  </joint>
  <link name="Body_WheelLeftFront"/>
</robot>
"""


class TestRewriteUrdfRootToBaseLink:
    def test_strips_ground_link(self) -> None:
        out = rewrite_urdf_root_to_base_link(_SYNTHETIC_URDF)
        assert '<link name="ground">' not in out

    def test_jointroot_block_removed_entirely(self) -> None:
        """JointRoot is deleted, not converted to fixed.

        An earlier "switch type to fixed" approach left
        ``<parent link="ground"/>`` dangling, which urdf_parser
        rejects. Pin the current behaviour: no ``JointRoot``
        substring of any kind survives the rewrite.
        """
        out = rewrite_urdf_root_to_base_link(_SYNTHETIC_URDF)
        assert "JointRoot" not in out
        # The dangling parent reference disappears with the block.
        assert 'parent link="ground"' not in out

    def test_renames_body_chassis_link_declaration(self) -> None:
        out = rewrite_urdf_root_to_base_link(_SYNTHETIC_URDF)
        assert '<link name="base_link">' in out
        assert "Body_Chassis" not in out

    def test_renames_parent_and_child_references(self) -> None:
        """Other joints' parent/child references rename through the same regex."""
        out = rewrite_urdf_root_to_base_link(_SYNTHETIC_URDF)
        assert '<parent link="base_link"/>' in out

    def test_idempotent_on_second_pass(self) -> None:
        once = rewrite_urdf_root_to_base_link(_SYNTHETIC_URDF)
        twice = rewrite_urdf_root_to_base_link(once)
        assert once == twice

    def test_preserves_other_link_names(self) -> None:
        """A link with a name that *contains* Body_Chassis substring is left alone."""
        urdf = '<robot><link name="Body_ChassisExtension"/></robot>'
        out = rewrite_urdf_root_to_base_link(urdf)
        # The boundary regex ([\"\s] on both sides) must NOT match the
        # substring inside ``Body_ChassisExtension``.
        assert "Body_ChassisExtension" in out
        assert "base_link" not in out

    def test_preserves_sibling_joints(self) -> None:
        """Non-greedy ``.*?</joint>`` must not swallow neighbouring joints."""
        out = rewrite_urdf_root_to_base_link(_SYNTHETIC_URDF)
        # WheelFL is the joint right after JointRoot in the synthetic URDF.
        assert 'name="WheelFL"' in out

    def test_synthetic_parses_with_elementtree(self) -> None:
        """xml.etree sanity proxy for urdf_parser/src/model.cpp."""
        out = rewrite_urdf_root_to_base_link(_SYNTHETIC_URDF)
        # Should not raise.
        root = ET.fromstring(out)
        # No JointRoot in the parsed joint set.
        joints = {j.get("name") for j in root.findall("joint")}
        assert "JointRoot" not in joints

    def test_synthetic_root_is_base_link(self) -> None:
        """After rewrite, base_link is the only never-child link."""
        out = rewrite_urdf_root_to_base_link(_SYNTHETIC_URDF)
        root = ET.fromstring(out)
        all_links = {link.get("name") for link in root.findall("link")}
        child_links = {
            j.find("child").get("link")
            for j in root.findall("joint")
            if j.find("child") is not None
        }
        roots = all_links - child_links
        assert roots == {"base_link"}


_REAL_URDF_PATH = "assets/m2020-urdf-models/rover/m2020.urdf"


@pytest.mark.skipif(
    not os.path.isfile(_REAL_URDF_PATH),
    reason="Real m2020 URDF not present (asset checkout required)",
)
class TestRewriteOnRealUrdf:
    """Smoke test on the actual JPL URDF used in production."""

    @pytest.fixture
    def real_urdf_text(self) -> str:
        return Path(_REAL_URDF_PATH).read_text(encoding="utf-8")

    def test_global_rewrite_eliminates_all_body_chassis_tokens(self, real_urdf_text: str) -> None:
        out = rewrite_urdf_root_to_base_link(real_urdf_text)
        # 46 raw occurrences observed in production. After the rewrite,
        # the JointRoot block is deleted wholesale, taking with it ONE
        # ``<child link="Body_Chassis"/>`` reference inside the block.
        # The remaining 45 references all rename to ``base_link``.
        # Pin both expectations.
        assert "Body_Chassis" not in out
        body_chassis_count = real_urdf_text.count("Body_Chassis")
        # ``base_link`` may also appear in mesh filenames or comments;
        # use ``>=`` to allow that, but the exact body_chassis_count - 1
        # bound is the meaningful invariant for the rename.
        assert out.count("base_link") >= body_chassis_count - 1

    def test_real_urdf_jointroot_completely_gone(self, real_urdf_text: str) -> None:
        """Strengthened from the original ``floating only`` check.

        The current rewrite regex deletes the whole block, so the
        substring ``JointRoot`` must not survive.
        ``Joint_MHS_DebrisShield`` does not contain ``JointRoot`` as
        a substring, so this check is precise.
        """
        out = rewrite_urdf_root_to_base_link(real_urdf_text)
        assert "JointRoot" not in out

    def test_real_urdf_no_dangling_ground_parent(self, real_urdf_text: str) -> None:
        """The original urdf_parser rejection ('parent link [ground] not found')."""
        out = rewrite_urdf_root_to_base_link(real_urdf_text)
        assert 'parent link="ground"' not in out

    def test_real_urdf_no_ground_link(self, real_urdf_text: str) -> None:
        out = rewrite_urdf_root_to_base_link(real_urdf_text)
        assert '<link name="ground">' not in out

    def test_real_urdf_parses_with_elementtree(self, real_urdf_text: str) -> None:
        """Closest sanity proxy for the C++ urdf_parser inside RViz."""
        out = rewrite_urdf_root_to_base_link(real_urdf_text)
        # Replace mesh paths with placeholders so the test does not
        # require the meshes/ folder to be present for parsing.
        ET.fromstring(out)  # raises on malformed XML

    def test_real_urdf_root_is_base_link(self, real_urdf_text: str) -> None:
        """After rewrite, base_link is the only URDF tree root."""
        out = rewrite_urdf_root_to_base_link(real_urdf_text)
        root = ET.fromstring(out)
        all_links = {link.get("name") for link in root.findall("link")}
        child_links = {
            j.find("child").get("link")
            for j in root.findall("joint")
            if j.find("child") is not None
        }
        roots = all_links - child_links
        assert roots == {"base_link"}, f"Expected {{base_link}}, got {roots!r}"

    def test_real_urdf_idempotent(self, real_urdf_text: str) -> None:
        """Two rewrite passes on the real URDF must produce identical output."""
        once = rewrite_urdf_root_to_base_link(real_urdf_text)
        twice = rewrite_urdf_root_to_base_link(once)
        assert once == twice


# ---------------------------------------------------------------------------
# publish_robot_description rename flag (C1)
# ---------------------------------------------------------------------------


class _StubPublisher:
    """Minimal stand-in for ``rclpy.publisher.Publisher``."""

    def __init__(self) -> None:
        self.published: list[object] = []

    def publish(self, msg: object) -> None:
        self.published.append(msg)


class _StubNode:
    """Minimal stand-in for ``rclpy.node.Node``.

    ``publish_robot_description`` only consults ``create_publisher``;
    nothing else on ``Node`` is invoked.  Keeping the stub tiny so the
    test does not silently hide a future regression where the function
    starts depending on additional ``Node`` methods.
    """

    def __init__(self) -> None:
        self.last_args: tuple = ()

    def create_publisher(self, msg_type: object, topic: str, qos: object) -> _StubPublisher:
        self.last_args = (msg_type, topic, qos)
        return _StubPublisher()


@pytest.fixture
def fake_std_msgs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a fake ``std_msgs.msg.String`` so the import succeeds offline."""
    import sys
    import types

    class _String:
        def __init__(self) -> None:
            self.data: str = ""

    std_msgs_msg = types.ModuleType("std_msgs.msg")
    std_msgs_msg.String = _String  # type: ignore[attr-defined]
    std_msgs = types.ModuleType("std_msgs")
    std_msgs.msg = std_msgs_msg  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "std_msgs", std_msgs)
    monkeypatch.setitem(sys.modules, "std_msgs.msg", std_msgs_msg)


class TestPublishRobotDescriptionRenameFlag:
    """C1: ``publish_robot_description`` honours ``rename_root_to_base_link``.

    Default ``True`` preserves the legacy nameOverride-paired rewrite;
    ``False`` keeps the URDF link names verbatim so the URDF and the
    OmniGraph-published joint owners share a single source of truth
    (the C3 default).
    """

    def test_rename_default_true_rewrites_root_to_base_link(
        self, fake_std_msgs: None, tmp_path: Path
    ) -> None:
        from marslab.ros2_bridge.robot_description_publisher import publish_robot_description

        urdf_path = tmp_path / "rover.urdf"
        urdf_path.write_text(_SYNTHETIC_URDF)
        node = _StubNode()
        ctx = publish_robot_description(node, str(urdf_path), qos=object())

        assert '<link name="base_link"' in ctx.urdf_text
        assert '<link name="Body_Chassis"' not in ctx.urdf_text
        assert "JointRoot" not in ctx.urdf_text

    def test_rename_false_keeps_body_chassis(self, fake_std_msgs: None, tmp_path: Path) -> None:
        from marslab.ros2_bridge.robot_description_publisher import publish_robot_description

        urdf_path = tmp_path / "rover.urdf"
        urdf_path.write_text(_SYNTHETIC_URDF)
        node = _StubNode()
        ctx = publish_robot_description(
            node,
            str(urdf_path),
            qos=object(),
            rename_root_to_base_link=False,
        )

        assert '<link name="Body_Chassis"' in ctx.urdf_text
        assert '<link name="base_link"' not in ctx.urdf_text
        # Mesh-path rewrite is independent of the rename flag.
        # ``_SYNTHETIC_URDF`` does not declare meshes so we just
        # confirm the urdf_text round-trips through the rewriter.
        assert ctx.urdf_text != ""
