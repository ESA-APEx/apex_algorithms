"""
Dummy tests to to help with tooling development.

Note that this test module will be skipped by default.
Use the `--dummy` runtime option to run these tests
and skip all other non-dummy tests.
"""

import pytest


@pytest.mark.parametrize("y", [4, 5, 6])
def test_tracking(track_metric, y):
    x = 3
    track_metric("x squared", x * x)
    track_metric("y", y)
    assert x + y == 8


def test_simple_success():
    x = 3
    assert x + 5 == 8


def test_simple_fail():
    x = 3
    assert x + 5 == "eight"


def test_produce_files_success(tmp_path):
    path = tmp_path / "hello.txt"
    path.write_text("Hello, world.\n")


def test_produce_files_fail(tmp_path):
    path = tmp_path / "hello.txt"
    path.write_text("Hello, world.\n")
    assert 1 == 2


@pytest.mark.parametrize("x", [3, 5])
def test_upload_assets(tmp_path, upload_assets_on_fail, x):
    path = tmp_path / "hello.txt"
    path.write_text("Hello, world.\n")
    upload_assets_on_fail(path)
    assert x == 5


def test_output_stuff():
    print("print print")
    import logging

    logger = logging.getLogger("test_output_stuff")
    logger.info("logger info")
    logger.warning("logger warning")
    logger.error("logger error")
    assert False
