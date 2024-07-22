"""
Dummy tests to allow setting up additional test tooling
"""

import pytest


@pytest.mark.parametrize("y", [4, 5, 6])
def test_dummy(track_metric, y):
    x = 3
    track_metric("x squared", x * x)
    track_metric("y", y)
    assert x + y == 8


def test_dummy2():
    x = 3
    y = 5
    assert x + y == 8
