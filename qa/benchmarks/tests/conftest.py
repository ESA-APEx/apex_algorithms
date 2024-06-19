import logging
import random

# TODO: how to make sure the logging/printing from this plugin is actually visible by default?
_log = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--random-subset",
        metavar="N",
        action="store",
        default=-1,
        type=int,
        help="Only run random selected subset benchmarks.",
    )


def pytest_collection_modifyitems(session, config, items):
    """
    Pytest plugin to select a random subset of benchmarks to run.

    based on https://alexwlchan.net/til/2024/run-random-subset-of-tests-in-pytest/
    """
    subset_size = config.getoption("--random-subset")

    if subset_size >= 0:
        _log.warning(
            f"Selecting random subset of {subset_size} from {len(items)} benchmarks."
        )
        items[:] = random.sample(items, k=subset_size)
