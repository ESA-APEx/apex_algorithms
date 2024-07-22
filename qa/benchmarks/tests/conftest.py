import logging
import os
import random
from typing import Callable

import openeo
import pytest
import requests

# TODO: how to make sure the logging/printing from this plugin is actually visible by default?
_log = logging.getLogger(__name__)

pytest_plugins = [
    "apex_algorithm_qa_tools.test_metrics",
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
