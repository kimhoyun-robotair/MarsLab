"""Unit tests for :class:`marslab.ros2_bridge.context.BridgeContext`.

These tests keep the dataclass semantics pinned so downstream callers
(``rclpy_integration``, Stage-3 runtime, tests) can treat
``BridgeContext`` as a plain value type.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass


class TestBridgeContextDataclass:
    def test_is_a_dataclass(self) -> None:
        from marslab.ros2_bridge.context import BridgeContext

        assert is_dataclass(BridgeContext)

    def test_has_expected_fields_in_order(self) -> None:
        from marslab.ros2_bridge.context import BridgeContext

        names = [f.name for f in fields(BridgeContext)]
        assert names == [
            "node",
            "cmd_vel_subscription",
            "static_tf_broadcaster",
            "odom_ctx",
            "twist_state",
        ]

    def test_constructible_with_placeholder_values(self) -> None:
        from marslab.ros2_bridge.context import BridgeContext

        ctx = BridgeContext(
            node=object(),
            cmd_vel_subscription=object(),
            static_tf_broadcaster=object(),
            odom_ctx=object(),
            twist_state={"v": 0.0, "w": 0.0},
        )
        assert ctx.twist_state == {"v": 0.0, "w": 0.0}

    def test_same_identity_as_package_reexport(self) -> None:
        """``marslab.ros2_bridge.BridgeContext`` is the one from context.py."""
        import marslab.ros2_bridge as bridge
        from marslab.ros2_bridge.context import BridgeContext as ContextCls

        assert bridge.BridgeContext is ContextCls
