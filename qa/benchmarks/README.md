
# APEx Algorithms Benchmark suite

This is a pytest-based benchmark suite for APEx algorithms.
The goal is to run hosted algorithms according to pre-defined scenarios
against real openEO backends and observe their outcome and performance.


## Set up

Make sure to work in a virtual environment
(e.g. with `python -m venv venv`),
to ensure isolation from other projects.

Install the test dependencies, including the reusable tools from `apex-algorithm-qa-tools`,
e.g. when working from the `qa/benchmarks` folder:

```bash
# Install apex-algorithm-qa-tools
pip install ../tools
# Install general test requirements
pip install -r requirements.txt
```

When intending to do development on `apex-algorithm-qa-tools`,
consider including the `-e` flag to install in editable mode.

## Run benchmarks

From `qa/benchmarks` folder, run:

```bash
pytest
```

Use the normal pytest flags and options to control the benchmark run.
For example, to run a specific benchmark scenario by its id, say "max_ndvi",
with increased verbosity and live logging at DEBUG level:

```bash
pytest -vv --log-cli-level=DEBUG -k '[max_ndvi]'
```

## `openeo` client library

The test suite heavily relies on the
[`openeo` Python client library](https://open-eo.github.io/openeo-python-client/)
to interact with the openEO backends, e.g. to create openEO jobs,
wait for their completion, retrieve their results, ...


## Authentication

The test suite defines a fixture `connection_factory` (in `conftest.py`)
to create an authenticated `openeo.Connection` object for a given
target openEO backend to be used by the benchmark tests.

By default, the authentication is done with a standard
`connection.authenticate_oidc()` call, which supports
refresh token based authentication, device code flow and client credentials
depending on the run context and environment variables as explained
in the [the docs](https://open-eo.github.io/openeo-python-client/auth.html#oidc-authentication-dynamic-method-selection).
This should support most development use cases where
one wants to run one or more tests under their own account.

However, a full, automated CI run (in GitHub Actions at the moment)
comes with the problem that multiple openEO backends might have to be tested,
and each backend might require its own set of client credentials.
That is not supported by a simple environment variable driven
`connection.authenticate_oidc()` call,
as it only supports a fixed environment variable set.
The `connection_factory` fixture adds support for multiple backends
with multiple client credentials as follows:
- an environment variable is dynamically determined from the backend URL,
  e.g. `OPENEO_AUTH_CLIENT_CREDENTIALS_CDSEFED` for the CDSE Federation
- that environment variable is expected to contain provider id,
  client id and client   secret, concatenated as a single string
  using a `/` separator,
  e.g. `CDSE/openeo-apexbenchmark-service-account/p655w0r6!!`

At the moment this is set up in GitHub Actions through
[GitHub Actions secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions).
