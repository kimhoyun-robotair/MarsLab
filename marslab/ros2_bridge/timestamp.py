"""Convert sample timestamps without consulting a ROS node clock."""

from __future__ import annotations

from typing import Any


def split_stamp_ns(stamp_ns: int) -> tuple[int, int]:
    """Validate non-negative integer nanoseconds and split ROS time fields."""
    if isinstance(stamp_ns, bool) or not isinstance(stamp_ns, int):
        raise TypeError("stamp_ns must be an integer number of nanoseconds")
    if stamp_ns < 0:
        raise ValueError("stamp_ns must be non-negative")
    return divmod(stamp_ns, 1_000_000_000)


def ros_stamp_from_ns(stamp_ns: int) -> Any:
    """Create a ROS timestamp at the runtime message boundary."""
    from builtin_interfaces.msg import Time

    sec, nanosec = split_stamp_ns(stamp_ns)
    return Time(sec=sec, nanosec=nanosec)
