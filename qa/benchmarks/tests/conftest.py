import logging
import os
import random
import re
import urllib.parse
from typing import Callable

import openeo
import pytest
import requests

# TODO: how to make sure the logging/printing from this plugin is actually visible by default?
_log = logging.getLogger(__name__)

pytest_plugins = [
    "apex_algorithm_qa_tools.pytest.pytest_track_metrics",
    "apex_algorithm_qa_tools.pytest.pytest_upload_assets",
]


def pytest_addoption(parser):
    parser.addoption(
        "--random-subset",
        metavar="N",
        action="store",
        default=-1,
        type=int,
        help="Only run random selected subset benchmarks.",
    )
    parser.addoption(
        "--dummy",
        action="store_true",
        help="Toggle to only run dummy benchmarks/tests (instead of skipping them)",
    )
    parser.addoption(
        "--override-backend",
        action="store",
        type=str,
        help="When provided this url will be used instead of the backend listed in the benchmark json files.",
    )
    parser.addoption(
        "--backend-filter",
        action="store",
        type=str,
        help="A regex patter to filter the available scenarios by backend.",
    )
    parser.addoption(
        "--maximum-job-time-in-minutes",
        action="store",
        default=None,
        type=int,
        help="Maximum time in minutes a batch job is allowed to run before the test fails due to timeout.",
    )
    parser.addoption(
        "--upload-benchmark-report",
        action="store_true",
        help="Upload a benchmark report (scenario metadata and job ID) as an asset on test failure.",
    )


def pytest_ignore_collect(collection_path, config):
    """
    Pytest hook to ignore certain directories/files during test collection.
    """
    # Note: there as some subtleties about the return values of this hook,
    # which makes the logic slightly more complex than a naive approach would suggest:
    # - `True` means to ignore the path,
    # - `False` means to forcefully include it regardless of other plugins,
    # - `None` means to keep it for now, but allow other plugins to still ignore.
    dummy_mode = bool(config.getoption("--dummy"))
    is_dummy_path = bool("dummy" in collection_path.name)
    if dummy_mode and not is_dummy_path:
        return True
    elif not dummy_mode and is_dummy_path:
        return True
    else:
        return None


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session, config, items):
    """
    Pytest hook to filter/reorder collected test items.
    """
    # Optionally, select a random subset of benchmarks to run.
    # based on https://alexwlchan.net/til/2024/run-random-subset-of-tests-in-pytest/
    subset_size = config.getoption("--random-subset")
    if subset_size >= 0:
        _log.info(f"Selecting random subset of {subset_size} from {len(items)} benchmarks.")
        if subset_size < len(items):
            selected = random.sample(items, k=subset_size)
            selected_ids = set(item.nodeid for item in selected)
            deselected = [item for item in items if item.nodeid not in selected_ids]
            config.hook.pytest_deselected(items=deselected)
            items[:] = selected