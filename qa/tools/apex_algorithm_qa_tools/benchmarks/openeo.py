import logging
import os
import re

import openeo
import pytest
import requests
import urllib
from pathlib import Path
import signal

_log = logging.getLogger(__name__)


def _get_client_credentials_env_var(url: str) -> str:
    """
    Get client credentials env var name for a given backend URL.
    """
    if not re.match(r"https?://", url):
        url = f"https://{url}"
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname

    if var := {
        # TODO: move this mapping to a config file
        #       instead of trying to keep this up to date for different environments.
        "openeo.dataspace.copernicus.eu": "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSE",
        "openeo-staging.dataspace.copernicus.eu": "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSESTAG",
        "openeofed.dataspace.copernicus.eu": "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSE",
        "openeo.vito.be": "OPENEO_AUTH_CLIENT_CREDENTIALS_TERRASCOPE",
        "openeo-dev.vito.be": "OPENEO_AUTH_CLIENT_CREDENTIALS_TERRASCOPE",
        "openeo.terrascope.be": "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSE",
        "openeo-staging.terrascope.be": "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSE",
        "openeo-dev.terrascope.be": "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSE",
        "openeo.cloud": "OPENEO_AUTH_CLIENT_CREDENTIALS_EGI",
        "openeo.eodc.eu": "OPENEO_AUTH_CLIENT_CREDENTIALS_EGI",
    }.get(hostname):
        return var
    elif re.fullmatch(r"openeo\.dev\.([a-z0-9-]+)\.openeo-int\.v1\.dataspace\.copernicus\.eu", hostname):
        return "OPENEO_AUTH_CLIENT_CREDENTIALS_CDSESTAG"
    else:
        raise ValueError(f"Unsupported backend: {url=} ({hostname=})")


def get_openeo_backend(scenario, request):
    # Check if a backend override has been provided via cli options.
    override_backend = request.config.getoption("--override-backend")
    backend_filter = request.config.getoption("--backend-filter")
    if backend_filter and not re.match(backend_filter, scenario.backend):
        # TODO apply filter during scenario retrieval, but seems to be hard to retrieve cli param
        pytest.skip(
            f"skipping scenario {scenario.id} because backend "
            f"{scenario.backend} does not match filter {backend_filter!r}"
        )
    if override_backend:
        _log.info(f"Overriding backend URL with {override_backend!r}")
        return override_backend
    return scenario.backend


def create_openeo_connection(*, backend: str, origin: str | None = None) -> openeo.Connection:
    session = requests.Session()
    session.params["_origin"] = origin

    _log.info(f"Connecting to {backend!r}")
    connection = openeo.connect(backend, auto_validate=False, session=session)
    connection.default_headers["X-OpenEO-Client-Context"] = "APEx Algorithm Benchmarks"

    # Authentication:
    # In production CI context, we want to extract client credentials
    # from environment variables (based on backend url).
    # In absence of such environment variables, to allow local development,
    # we fall back on a traditional `authenticate_oidc()`
    # which automatically supports various authentication flows (device code, refresh token, client credentials, etc.)

    auth_env_var = _get_client_credentials_env_var(backend)
    _log.info(f"Checking for {auth_env_var=} to drive auth against {backend=}.")
    if auth_env_var in os.environ:
        client_credentials = os.environ[auth_env_var]
        provider_id, client_id, client_secret = client_credentials.split("/", 2)
        _log.info(f"Extracted {provider_id=} {client_id=} from {auth_env_var=}")
        connection.authenticate_oidc_client_credentials(
            provider_id=provider_id,
            client_id=client_id,
            client_secret=client_secret,
        )
    else:
        max_poll_time = int(os.environ.get("OPENEO_OIDC_DEVICE_CODE_MAX_POLL_TIME") or 30)
        connection.authenticate_oidc(max_poll_time=max_poll_time)
    return connection


def create_openeo_job(*, connection, scenario):
    return connection.create_job(
        process_graph=scenario.process_graph,
        title=f"APEx benchmark {scenario.id}",
        additional=scenario.job_options,
    )


def run_openeo_job(*, job, max_minutes: int | None):
    if max_minutes:

        def _timeout_handler(signum, frame):
            raise TimeoutError(f"Batch job {job.job_id} exceeded maximum allowed time of {max_minutes} minutes")

        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(max_minutes * 60)
    try:
        job.start_and_wait()
    finally:
        if max_minutes:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


def collect_openeo_metadata(*, job):
    return job.get_results()


def download_openeo_results(*, results, actual_dir: Path):
    return results.download_files(target=actual_dir, include_stac_metadata=True)
