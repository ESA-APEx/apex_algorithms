"""
Pytest plugin to record test/benchmark metrics to a JSON file.


Usage:

-   Enable the plugin in `conftest.py`:

    ```python
    pytest_plugins = [
        "apex_algorithm_qa_tools.test_metrics",
    ]
    ```

-   Use the `test_metric` fixture to record test metrics:

    ```python
    def test_dummy(test_metric):
        x = 3
        test_metric("x squared", x*x)
    ...

-   Run the tests with `--test-metrics=path/to/metrics.json`
    to store metrics in a JSON file
"""

import json
from pathlib import Path
from typing import Any, Callable, List, Tuple, Union

import pytest

_TEST_METRICS_PATH = "test_metrics_path"
_TEST_METRICS_REPORTER = "test_metrics_reporter"


def pytest_addoption(parser):
    parser.addoption(
        "--test-metrics",
        metavar="PATH",
        action="store",
        dest=_TEST_METRICS_PATH,
        default=None,
        help="Path to JSON file to store test/benchmark metrics.",
    )


def pytest_configure(config):
    test_metrics_path = config.getoption(_TEST_METRICS_PATH)
    if (
        test_metrics_path
        # Don't register on xdist worker nodes
        and not hasattr(config, "workerinput")
    ):
        config.pluginmanager.register(
            MetricsReporter(path=test_metrics_path),
            name=_TEST_METRICS_REPORTER,
        )


def pytest_unconfigure(config):
    if config.pluginmanager.hasplugin(_TEST_METRICS_REPORTER):
        config.pluginmanager.unregister(name=_TEST_METRICS_REPORTER)


class MetricsReporter:
    def __init__(
        self, path: Union[str, Path], user_properties_key: str = "test_metrics"
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
                    "metrics": self.get_test_metrics(report.user_properties),
                }
            )

    def pytest_sessionfinish(self, session):
        with self.path.open("w", encoding="utf8") as f:
            json.dump(self.metrics, f, indent=2)

    def pytest_terminal_summary(self, terminalreporter):
        terminalreporter.write_sep("-", f"Generated test metrics report: {self.path}")

    def get_test_metrics(
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
def test_metric(
    pytestconfig: pytest.Config, request: pytest.FixtureRequest
) -> Callable[[str, Any], None]:
    """
    Fixture to record a test metrics during openEO tests/benchmarks,
    which will be stored in the pytest node's "user_properties".
    """

    reporter = pytestconfig.pluginmanager.get_plugin(_TEST_METRICS_REPORTER)

    def append(name: str, value: Any):
        reporter.get_test_metrics(request.node.user_properties).append((name, value))

    return append
