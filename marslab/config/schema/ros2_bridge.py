"""ROS2 bridge schema: OmniGraph prim path + rclpy subscription tuning.

R4-5 extension (2026-04-23) promoted two literals that had been sitting
as module constants / Python defaults inside the ROS2 bridge into a
pydantic ``Ros2BridgeConfig`` block:

* ``GRAPH_PATH = "/World/Stage3ROS2Graph"`` in
  ``marslab/ros2_bridge/sensor_graph.py:35`` was a bare module-level
  constant — every scenario shipped the same prim path and the only
  way to relocate the action graph was a source edit.
* ``queue_size=10`` in
  ``marslab/ros2_bridge/cmd_vel_subscriber.create_cmd_vel_subscriber``
  was a Python default that the caller (rclpy_integration) never
  overrode, so a noisy Nav2 controller_server could not back-pressure
  through YAML.

Both are now declared here.  ``configs/robots/rover_m2020.yaml``
(``rover.ros2`` block) gains an optional ``graph_path`` +
``cmd_vel_queue_size`` pair.  Absent values fall back to the historical
constants via the pydantic defaults so existing scenarios keep loading.

The schema enforces prim-path hygiene (non-empty, ``/``-prefixed, no
internal whitespace) with ``model_validator`` so a typo like
``" /World/Graph"`` fails at load time rather than surfacing as an
opaque ``omni.graph.core`` failure inside Isaac Sim.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

__all__ = ["Ros2BridgeConfig"]


class Ros2BridgeConfig(BaseModel):
    """Configuration for the Stage-3 ROS2 bridge plumbing.

    Mirrors the ``rover.ros2`` YAML sub-block.  Only the keys that
    used to live as Python constants are declared here; the existing
    free-form ``namespace`` / ``topics`` / ``rates`` / ``odom_publisher``
    keys continue to flow through ``init_rclpy_side`` as an untyped
    dict because they are already covered by legacy tests.  A later
    pass (R4-6+) may promote the remaining dict keys.
    """

    graph_path: str = Field(
        default="/World/Stage3ROS2Graph",
        description=(
            "USD prim path for the Stage-3 OmniGraph action graph.  The "
            "Isaac Sim stage must not already contain a prim at this "
            "path.  Previously hardcoded as ``GRAPH_PATH`` in "
            "``marslab/ros2_bridge/sensor_graph.py``.  Promoted to "
            "schema in R4-5 (2026-04-23) so scenarios with unusual "
            "stage layouts (e.g. multi-robot Stage-4) can relocate the "
            "graph without a source edit."
        ),
    )
    cmd_vel_queue_size: int = Field(
        default=10,
        ge=1,
        le=1000,
        description=(
            "rclpy subscription queue depth for the ``/<ns>/cmd_vel`` "
            "topic.  Previously hardcoded as ``queue_size=10`` in "
            "``marslab/ros2_bridge/cmd_vel_subscriber.py``.  Promoted "
            "in R4-5 (2026-04-23) so Nav2 tuning that needs a deeper "
            "buffer (bursty controller_server output) can be expressed "
            "in YAML.  Upper bound of 1000 prevents accidental "
            "misconfigurations that would swamp rclpy with unbounded "
            "queues."
        ),
    )

    @model_validator(mode="after")
    def check_graph_path(self) -> "Ros2BridgeConfig":
        """Enforce USD prim-path hygiene on ``graph_path``.

        Rules:
        * Non-empty.
        * Must start with ``/`` (USD absolute prim path convention).
        * No internal whitespace (whitespace in USD prim paths is a
          syntax error downstream inside ``omni.graph.core``).
        """
        value = self.graph_path
        if not value:
            raise ValueError("graph_path must be a non-empty string")
        if not value.startswith("/"):
            raise ValueError(
                f"graph_path must start with '/' (USD absolute prim path); got {value!r}"
            )
        if any(ch.isspace() for ch in value):
            raise ValueError(f"graph_path must not contain whitespace; got {value!r}")
        return self
