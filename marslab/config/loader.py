"""Provide the compatibility import for canonical config loading.
The runtime reads one integrated YAML document through this name.
Split loaders are intentionally absent from the public surface."""

from marslab.config.yaml_loader import load_config

__all__ = ["load_config"]
