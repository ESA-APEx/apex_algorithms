"""
Pytest plugin to track test/benchmark metrics and report them with a JSON file.


Usage:

-   Enable the plugin in `conftest.py`:

    ```python
    pytest_plugins = [
        "apex_algorithm_qa_tools.pytest.pytest_track_metrics",
    ]
    ```

-   Use the `track_metric` fixture to record metrics during tests:

    ```python
    def test_dummy(track_metric):
        x = 3
        track_metric("x squared", x*x)
    ...

-   Run the tests with desired configuration through CLI options and env vars:
    - CLI option to store metrics to (local) JSON file:
      `--track-metrics-json=path/to/metrics.json`
    - CLI option to store metrics to local Parquet file:
      `--track-metrics-parquet=path/to/metrics.parquet`
    - CLI options to store metrics to Parquet file on S3:
      `--track-metrics-parquet-s3-bucket=BUCKET` to set the S3 bucket
      and `--track-metrics-parquet-s3-key=KEY` to specify the key/path in the bucket.
      Additional env vars to further configure S3 access:
        - S3 credentials with env vars `APEX_ALGORITHMS_S3_ACCESS_KEY_ID`
        and `APEX_ALGORITHMS_S3_SECRET_ACCESS_KEY`
        (Note that the classic `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
        are also supported as fallback)
        - S3 endpoint URL with env var `APEX_ALGORITHMS_S3_ENDPOINT_URL`
        (Note that the classic `AWS_ENDPOINT_URL` is also supported as fallback).
    - CLI option `--track-metrics-parquet-partitioning=PARTITIONING`
      to define how to partition the Parquet files.
"""

import dataclasses
import datetime
import json
import os
import warnings
from pathlib import Path
from typing import Any, Callable, List, Tuple, Union

import pyarrow
import pyarrow.dataset
import pyarrow.fs
import pyarrow.parquet
import pytest
from apex_algorithm_qa_tools.pytest import get_run_id

_TRACK_METRICS_PLUGIN_NAME = "track_metrics"


_S3_KEY_DEFAULT = "metrics/v0/metrics.parquet"


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--track-metrics-json",
        metavar="PATH",
        help="Path to JSON file to store test/benchmark metrics.",
    )
    parser.addoption(
        "--track-metrics-parquet",
        metavar="PATH",
        help="Path to local Parquet file to store test/benchmark metrics.",
    )
    parser.addoption(
        "--track-metrics-parquet-s3-bucket",
        metavar="BUCKET",
        help="S3 bucket to use for Parquet storage of metrics.",
    )
    parser.addoption(
        "--track-metrics-parquet-s3-key",
        metavar="KEY",
        default=_S3_KEY_DEFAULT,
        help="S3 key to use for Parquet storage of metrics.",
    )
    parser.addoption(
        "--track-metrics-parquet-partitioning",
        metavar="PARTITIONING",
        default=None,
        help="""
            Define how to partition the Parquet files. One of:
            - "false" to disable partitioning (will overwrite existing files).
            - "simple" to just put everything in a single partition in append mode.
            - "YYYYMM" to partition by year and month (in append mode).
        """,
    )


def pytest_configure(config):
    if hasattr(config, "workerinput"):
        warnings.warn("`track_metrics` plugin is not supported on xdist worker nodes.")
        return

    track_metrics_json = config.getoption("--track-metrics-json")

    track_metrics_parquet = config.getoption("--track-metrics-parquet")
    track_metrics_parquet_s3_bucket = config.getoption(
        "--track-metrics-parquet-s3-bucket"
    )
    track_metrics_parquet_s3_key = config.getoption(
        "--track-metrics-parquet-s3-key", _S3_KEY_DEFAULT
    )
    track_metrics_parquet_partitioning = config.getoption(
        "--track-metrics-parquet-partitioning", None
    )

    if track_metrics_json or track_metrics_parquet or track_metrics_parquet_s3_bucket:
        config.pluginmanager.register(
            TrackMetricsReporter(
                json_path=track_metrics_json,
                parquet_local=track_metrics_parquet,
                parquet_s3=(
                    _ParquetS3StorageSettings(
                        bucket=track_metrics_parquet_s3_bucket,
                        key=track_metrics_parquet_s3_key,
                    )
                    if track_metrics_parquet_s3_bucket
                    else None
                ),
                parquet_partitioning=track_metrics_parquet_partitioning,
            ),
            name=_TRACK_METRICS_PLUGIN_NAME,
        )


@dataclasses.dataclass(frozen=True)
class _ParquetS3StorageSettings:
    bucket: str
    key: str = _S3_KEY_DEFAULT


class TrackMetricsReporter:
    def __init__(
        self,
        json_path: Union[None, str, Path] = None,
        parquet_local: Union[None, str, Path] = None,
        parquet_s3: _ParquetS3StorageSettings | None = None,
        user_properties_key: str = "track_metrics",
        parquet_partitioning: str | None = None,
    ):
        self._json_path = Path(json_path) if json_path else None
        self._parquet_local = Path(parquet_local) if parquet_local else None
        self._parquet_s3 = parquet_s3
        self._parquet_partitioning = parquet_partitioning
        self._suite_metrics: List[dict] = []
        self._user_properties_key = user_properties_key
        self._run_id = get_run_id()

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

        if self._parquet_local:
            self._write_parquet(
                location=self._parquet_local,
                # Use no partitioning by default for local parquet files
                partitioning_mode=self._parquet_partitioning or "false",
                filesystem=None,
            )

        if self._parquet_s3:
            fs = pyarrow.fs.S3FileSystem(
                access_key=os.environ.get("APEX_ALGORITHMS_S3_ACCESS_KEY_ID"),
                secret_key=os.environ.get("APEX_ALGORITHMS_S3_SECRET_ACCESS_KEY"),
                endpoint_override=os.environ.get("APEX_ALGORITHMS_S3_ENDPOINT_URL"),
            )
            root_path = f"{self._parquet_s3.bucket}/{self._parquet_s3.key}"
            self._write_parquet(
                location=root_path,
                # Use simple partitioning by default for S3 parquet files
                partitioning_mode=self._parquet_partitioning or "simple",
                filesystem=fs,
            )

    def _write_json_report(self, path: Union[str, Path]):
        with Path(path).open("w", encoding="utf8") as f:
            json.dump(self._suite_metrics, f, indent=2)

    def _to_pyarrow_table(self) -> pyarrow.Table:
        """Compile all (free-form) metrics into a more rigid table"""
        columns = set()
        suite_metrics = []
        for m in self._suite_metrics:
            test_start = m["report"]["start"]
            test_start_datetime = datetime.datetime.fromtimestamp(
                test_start, tz=datetime.timezone.utc
            )
            node_metrics = {
                "suite:run_id": self._run_id,
                "test:nodeid": m["nodeid"],
                "test:outcome": m["report"]["outcome"],
                "test:duration": m["report"]["duration"],
                "test:start": test_start,
                "test:start:datetime": test_start_datetime.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                # Note: this YYYYMM format is intended for partitioning reasons.
                "test:start:YYYYMM": test_start_datetime.strftime("%Y-%m"),
                "test:stop": m["report"]["stop"],
            }
            for k, v in m["metrics"]:
                assert k not in node_metrics, f"Duplicate metric key: {k}"
                node_metrics[k] = v
            columns.update(node_metrics.keys())
            suite_metrics.append(node_metrics)

        table = pyarrow.Table.from_pydict(
            {col: [m.get(col) for m in suite_metrics] for col in columns}
        )
        return table

    def _write_parquet(
        self,
        location: str,
        partitioning_mode: str | bool,
        filesystem: pyarrow.fs.FileSystem | None = None,
    ):
        table = self._to_pyarrow_table()

        if partitioning_mode in {"false", False}:
            pyarrow.parquet.write_table(
                table=table, where=location, filesystem=filesystem
            )
        else:
            if partitioning_mode == "simple":
                # Simple partitioning: just one partition, but still support append mode
                fields = []
            elif partitioning_mode == "YYYYMM":
                fields = [("test:start:YYYYMM", pyarrow.string())]
            else:
                # TODO: more partitioning options?
                raise ValueError(
                    f"Invalid parquet partitioning mode: {partitioning_mode}"
                )

            # Partitioning flavor `None`` means DirectoryPartitioning (unfortunately, there is currently
            # no way to specify this more explicitly https://github.com/apache/arrow/issues/43863)
            # TODO: support hive partitioning too, e.g. through prefix `hive:` in --track-metrics-parquet-partitioning
            partitioning_flavor = None
            write_partitioning = pyarrow.dataset.partitioning(
                schema=pyarrow.schema(fields=fields), flavor=partitioning_flavor
            )
            pyarrow.parquet.write_to_dataset(
                table=table,
                root_path=location,
                partitioning=write_partitioning,
                filesystem=filesystem,
                # "overwrite_or_ignore" enables append mode
                existing_data_behavior="overwrite_or_ignore",
                basename_template=f"{self._run_id}-{{i}}.parquet",
            )

    def pytest_report_header(self):
        return f"Plugin `track_metrics` is active, reporting to json={self._json_path}, parquet_local={self._parquet_local}, parquet_s3={self._parquet_s3}"

    def pytest_terminal_summary(self, terminalreporter):
        reports = []
        if self._json_path:
            reports.append(str(self._json_path))
        if self._parquet_local:
            reports.append(str(self._parquet_local))
        if self._parquet_s3:
            reports.append(str(self._parquet_s3))
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