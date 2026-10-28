"""Expose the canonical MarsLab configuration API.
Callers receive the validated root model and scenario/profile loader.
Schema layout remains private to this facade."""

from marslab.config.schema.root import MarsLabConfig
from marslab.config.yaml_loader import ROBOT_NAMES, load_config

__all__ = ["MarsLabConfig", "ROBOT_NAMES", "load_config"]
