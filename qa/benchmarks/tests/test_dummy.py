"""
Dummy tests to allow setting up additional test tooling
"""


def test_dummy(test_metric):
    x = 3
    y = 5
    test_metric("x squared", x * x)
    test_metric("y", y)
    assert x + y == 7


def test_dummy2():
    x = 3
    y = 5
    assert x + y == 8
