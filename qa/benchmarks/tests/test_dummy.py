"""
Dummy tests to allow setting up additional test tooling
"""


def test_dummy(openeo_metric):
    x = 3
    y = 5
    openeo_metric("x", x)
    openeo_metric("y", y)
    assert x + y == 7


def test_dummy2():
    x = 3
    y = 5
    assert x + y == 8
