import json
import logging
import os
import random
from pathlib import Path
from typing import Any, Callable, List, Tuple, Union

import openeo
import pytest
import requests

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
    parser.addoption(
        "--openeo-metrics",
        metavar="path",
        action="store",
        dest="openeo_metrics_path",
        default=None,
        help="File to store openEO metrics.",
    )


def pytest_configure(config):
    openeo_metrics_path = config.getoption("openeo_metrics_path")
    if (
        openeo_metrics_path
        # Don't register on xdist worker nodes
        and not hasattr(config, "workerinput")
    ):
        config.pluginmanager.register(
            # TODO: create config for this path
            OpeneoMetricReporter(openeo_metrics_path),
            name="openeo_metrics_reporter",
        )


def pytest_unconfigure(config):
    if config.pluginmanager.hasplugin("openeo_metrics_report"):
        config.pluginmanager.unregister(name="openeo_metrics_reporter")


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


@pytest.fixture
def openeo_metric(request: pytest.FixtureRequest) -> Callable[[str, Any], None]:
    """
    Fixture to record openEO metrics during openEO tests/benchmarks,
    which will be stored in the pytest node's "user_properties".

    Collect and export these metrics with OpeneoMetricReporter.
    """

    def append(name: str, value: Any):
        _get_openeo_metrics(request.node.user_properties).append((name, value))

    return append


def _get_openeo_metrics(user_properties: List[Tuple[str, Any]]) -> List:
    for name, value in user_properties:
        if name == OpeneoMetricReporter.USER_PROPERTY_KEY:
            return value
    # Not found: create it
    metrics = []
    user_properties.append((OpeneoMetricReporter.USER_PROPERTY_KEY, metrics))
    return metrics


class OpeneoMetricReporter:
    # TODO: isolate all this openeo_metrics stuff to proper plugin
    USER_PROPERTY_KEY = "openeo_metrics"

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self.metrics = []

    def pytest_runtest_logreport(self, report: pytest.TestReport):
        if report.when == "call":
            self.metrics.append(
                {
                    "nodeid": report.nodeid,
                    "outcome": report.outcome,
                    "openeo_metrics": _get_openeo_metrics(report.user_properties),
                    "duration": report.duration,
                    "start": report.start,
                    "stop": report.stop,
                    "longrepr": repr(report.longrepr),
                }
            )

    def pytest_sessionfinish(self, session):
        with self.path.open("w") as f:
            json.dump(self.metrics, f, indent=2)

    def pytest_terminal_summary(self, terminalreporter):
        terminalreporter.write_sep("-", f"Generated openEO metrics report: {self.path}")


def _get_client_credentials_env_var(url: str) -> str:
    """
    Get client credentials env var name for a given backend URL.
    """
    # TODO: parse url to more reliably extract hostname
    if url == "openeofed.dataspace.copernicus.eu":
        return "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED"
    else:
        raise ValueError(f"Unsupported backend: {url}")


@pytest.fixture
def connection_factory(request, capfd) -> Callable[[], openeo.Connection]:
    """
    Fixture for a function that sets up an authenticated connection to an openEO backend.

    This is implemented as a fixture to have access to other fixtures that allow
    deeper integration with the pytest framework.
    For example, the `request` fixture allows to identify the currently running test/benchmark.
    """

    # Identifier for the current test/benchmark, to be injected automatically
    # into requests to the backend for tracking/cross-referencing purposes
    origin = f"apex-algorithms/benchmarks/{request.session.name}/{request.node.name}"

    def get_connection(url: str) -> openeo.Connection:
        session = requests.Session()
        session.params["_origin"] = origin

        _log.info(f"Connecting to {url!r}")
        connection = openeo.connect(url, auto_validate=False, session=session)
        connection.default_headers["X-OpenEO-Client-Context"] = (
            "APEx Algorithm Benchmarks"
        )

        # Authentication:
        # In production CI context, we want to extract client credentials
        # from environment variables (based on backend url).
        # In absence of such environment variables, to allow local development,
        # we fall back on a traditional `authenticate_oidc()`
        # which automatically supports various authentication flows (device code, refresh token, client credentials, etc.)
        auth_env_var = _get_client_credentials_env_var(url)
        _log.info(f"Checking for {auth_env_var=} to drive auth against {url=}.")
        if auth_env_var in os.environ:
            client_credentials = os.environ[auth_env_var]
            provider_id, client_id, client_secret = client_credentials.split("/", 2)
            connection.authenticate_oidc_client_credentials(
                provider_id=provider_id,
                client_id=client_id,
                client_secret=client_secret,
            )
        else:
            # Temporarily disable output capturing,
            # to make sure that the OIDC device code instructions are shown
            # to the user running interactively.
            with capfd.disabled():
                # Use a shorter max poll time by default
                # to alleviate the default impression that the test seem to hang
                # because of the OIDC device code poll loop.
                max_poll_time = int(
                    os.environ.get("OPENEO_OIDC_DEVICE_CODE_MAX_POLL_TIME") or 30
                )
                connection.authenticate_oidc(max_poll_time=max_poll_time)

        return connection

    return get_connection
