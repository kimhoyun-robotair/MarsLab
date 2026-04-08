"""Unit tests for marslab.utils.seed."""

import random

import numpy as np
import pytest

from marslab.utils.seed import set_global_seed


def test_determinism():
    """Same seed produces identical sequences."""
    set_global_seed(42)
    a_py = random.random()
    a_np = np.random.random()

    set_global_seed(42)
    b_py = random.random()
    b_np = np.random.random()

    assert a_py == b_py
    assert a_np == b_np


def test_different_seeds():
    """Different seeds produce different sequences."""
    set_global_seed(42)
    a = random.random()

    set_global_seed(99)
    b = random.random()

    assert a != b


def test_seed_zero():
    """Seed 0 is valid."""
    set_global_seed(0)
    random.random()  # should not raise


def test_negative_seed_raises():
    """Negative seed raises ValueError."""
    with pytest.raises(ValueError, match="non-negative"):
        set_global_seed(-1)


def test_large_seed():
    """Large seed value is valid."""
    set_global_seed(2**31 - 1)
    random.random()  # should not raise
