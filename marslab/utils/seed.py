"""Global seed management for reproducibility."""

import random

import numpy as np


def set_global_seed(seed: int) -> None:
    """Set random seeds for reproducibility across all randomized backends.

    Sets seeds for Python's ``random`` module, NumPy, and optionally PyTorch
    if it is installed.

    Args:
        seed: Non-negative integer seed value.

    Raises:
        ValueError: If seed is negative.
    """
    if seed < 0:
        raise ValueError(f"Seed must be non-negative, got {seed}")

    random.seed(seed)
    np.random.seed(seed)

    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass
