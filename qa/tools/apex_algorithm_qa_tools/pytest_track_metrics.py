"""
Pytest plugin to track test/benchmark metrics and report them with a JSON file.


Usage:

-   Enable the plugin in `conftest.py`:

    ```python
    pytest_plugins = [
        "apex_algorithm_qa_tools.pytest_track_metrics",
    ]
    ```

-   Use the `track_metric` fixture to record metrics during tests:

    ```python
    def test_dummy(track_metric):
        x = 3
        track_metric("x squared", x*x)
    ...

-   Run the tests with `--track-metrics-report=path/to/metrics.json`
    to store metrics in a JSON file
"""

import json
import warnings
from pathlib import Path
from typing import Any, Callable, List, Tuple, Union

import pytest

_TRACK_METRICS_PLUGIN_NAME = "track_metrics"


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--track-metrics-report",
        metavar="PATH",
        help="Path to JSON file to store test/benchmark metrics.",
    )


def pytest_configure(config):
    track_metrics_path = config.getoption("track_metrics_report")
    if (
        track_metrics_path
        # Don't register on xdist worker nodes
        and not hasattr(config, "workerinput")
    ):
        config.pluginmanager.register(
            TrackMetricsReporter(path=track_metrics_path),
            name=_TRACK_METRICS_PLUGIN_NAME,
        )


def pytest_unconfigure(config):
    if config.pluginmanager.hasplugin(_TRACK_METRICS_PLUGIN_NAME):
        config.pluginmanager.unregister(name=_TRACK_METRICS_PLUGIN_NAME)


class TrackMetricsReporter:
    def __init__(
        self, path: Union[str, Path], user_properties_key: str = "track_metrics"
    ):
        self.path = Path(path)
        self.metrics: List[dict] = []
        self.user_properties_key = user_properties_key

    def pytest_runtest_logreport(self, report: pytest.TestReport):
        if report.when == "call":
            self.metrics.append(
                {
                    "nodeid": report.nodeid,
                    "report": {
                        "outcome": report.outcome,
                        "duration": report.duration,
                        "start": report.start,
                        "stop": report.stop,
                    },
                    "metrics": self.get_metrics(report.user_properties),
                }
            )

    def pytest_sessionfinish(self, session):
        with self.path.open("w", encoding="utf8") as f:
            json.dump(self.metrics, f, indent=2)

    def pytest_terminal_summary(self, terminalreporter):
        terminalreporter.write_sep("-", f"Generated track_metrics report: {self.path}")

    def get_metrics(
        self, user_properties: List[Tuple[str, Any]]
    ) -> List[Tuple[str, Any]]:
        """
        Extract existing test metrics items from user properties
        or create new one.
        """
        for name, value in user_properties:
            if name == self.user_properties_key:
                return value
        # Not found: create it
        metrics = []
        user_properties.append((self.user_properties_key, metrics))
        return metrics


@pytest.fixture
def track_metric(
    pytestconfig: pytest.Config, request: pytest.FixtureRequest
) -> Callable[[str, Any], None]:
    """
    Fixture to record a metric during tests/benchmarks,
    which will be stored in the pytest node's "user_properties".

    Returns a callable that expects a metric name and value
    """

    reporter: Union[TrackMetricsReporter, None] = pytestconfig.pluginmanager.get_plugin(
        _TRACK_METRICS_PLUGIN_NAME
    )

    if reporter:

        def append(name: str, value: Any):
            reporter.get_metrics(request.node.user_properties).append((name, value))
    else:
        warnings.warn(
            "The `track_metric` fixture is requested, but no output file is defined (e.g. with `--metrics-tracker-report=path/to/metrics.json`."
        )

        def append(name: str, value: Any):
            pass

    return append
