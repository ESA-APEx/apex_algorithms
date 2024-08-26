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

-   Run the tests with `--track-metrics-json=path/to/metrics.json`
    to store metrics in a JSON file
"""

import json
import warnings
from pathlib import Path
from typing import Any, Callable, List, Tuple, Union

import pyarrow
import pyarrow.parquet
import pytest

_TRACK_METRICS_PLUGIN_NAME = "track_metrics"


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--track-metrics-json",
        metavar="PATH",
        help="Path to JSON file to store test/benchmark metrics.",
    )
    parser.addoption(
        "--track-metrics-parquet",
        metavar="PATH",
        # TODO: allow "s3://" URLs too?
        help="Path to JSON file to store test/benchmark metrics.",
    )


def pytest_configure(config):
    if hasattr(config, "workerinput"):
        warnings.warn("`track_metrics` plugin is not supported on xdist worker nodes.")
        return

    track_metrics_json = config.getoption("track_metrics_json")
    track_metrics_parquet = config.getoption("track_metrics_parquet")
    if track_metrics_json or track_metrics_parquet:
        config.pluginmanager.register(
            TrackMetricsReporter(
                json_path=track_metrics_json, parquet_path=track_metrics_parquet
            ),
            name=_TRACK_METRICS_PLUGIN_NAME,
        )


class TrackMetricsReporter:
    def __init__(
        self,
        json_path: Union[None, str, Path] = None,
        parquet_path: Union[None, str, Path] = None,
        user_properties_key: str = "track_metrics",
    ):
        self._json_path = Path(json_path) if json_path else None
        self._parquet_path = parquet_path
        self._suite_metrics: List[dict] = []
        self._user_properties_key = user_properties_key

    def pytest_runtest_logreport(self, report: pytest.TestReport):
        if report.when == "call":
            self._suite_metrics.append(
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
        if self._json_path:
            self._write_json_report(self._json_path)

        if self._parquet_path:
            self._write_parquet_report(self._parquet_path)

    def _write_json_report(self, path: Union[str, Path]):
        with Path(path).open("w", encoding="utf8") as f:
            json.dump(self._suite_metrics, f, indent=2)

    def _write_parquet_report(self, path: Union[str, Path]):
        # Compile all (free-form) metrics into a more rigid table
        columns = set()
        suite_metrics = []
        for m in self._suite_metrics:
            node_metrics = {
                "nodeid": m["nodeid"],
                "outcome": m["report"]["outcome"],
                "duration": m["report"]["duration"],
                "start": m["report"]["start"],
                "stop": m["report"]["stop"],
                # TODO: also include runid (like in upload_assets)
            }
            for k, v in m["metrics"]:
                assert k not in node_metrics, f"Duplicate metric key: {k}"
                node_metrics[k] = v
            columns.update(node_metrics.keys())
            suite_metrics.append(node_metrics)

        table = pyarrow.Table.from_pydict(
            {col: [m.get(col) for m in suite_metrics] for col in columns}
        )

        # TODO: add support for partitioning (date and nodeid)
        # TODO: support for S3 with custom credential env vars
        pyarrow.parquet.write_table(table, self._parquet_path)

    def pytest_report_header(self):
        return f"Plugin `track_metrics` is active, reporting to json={self._json_path}, parquet={self._parquet_path}"

    def pytest_terminal_summary(self, terminalreporter):
        reports = []
        if self._json_path:
            reports.append(str(self._json_path))
        if self._parquet_path:
            reports.append(str(self._parquet_path))
        if reports:
            terminalreporter.write_sep(
                "-", f"Generated track_metrics report: {', '.join(reports)}"
            )

    def get_metrics(
        self, user_properties: List[Tuple[str, Any]]
    ) -> List[Tuple[str, Any]]:
        """
        Extract existing test metrics items from user properties
        or create new one.
        """
        for name, value in user_properties:
            if name == self._user_properties_key:
                return value
        # Not found: create it
        metrics = []
        user_properties.append((self._user_properties_key, metrics))
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

    reporter: TrackMetricsReporter | None = pytestconfig.pluginmanager.get_plugin(
        _TRACK_METRICS_PLUGIN_NAME
    )

    if reporter:

        def append(name: str, value: Any):
            reporter.get_metrics(request.node.user_properties).append((name, value))
    else:
        warnings.warn("Fixture `track_metric` is a no-op (incomplete set up).")

        def append(name: str, value: Any):
            pass

    return append
