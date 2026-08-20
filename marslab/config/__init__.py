"""Expose the canonical MarsLab configuration API.
Callers receive the validated root model and one-file loader.
Schema layout remains private to this facade."""

from marslab.config.schema.root import MarsLabConfig
from marslab.config.yaml_loader import load_config

__all__ = ["MarsLabConfig", "load_config"]
