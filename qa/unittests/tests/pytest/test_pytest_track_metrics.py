import json
import re
import textwrap
import time
from pathlib import Path
from typing import Callable, List

import dirty_equals
import pandas
import pyarrow.dataset
import pyarrow.parquet
import pytest

CONTENT_CONFTEST = """
    pytest_plugins = [
        "apex_algorithm_qa_tools.pytest.pytest_track_metrics",
    ]
"""

CONTENT_TEST_ADDITION_PY = """
    import pytest

    @pytest.mark.parametrize("x", [5, 6])
    def test_3plus(track_metric, x):
        track_metric("x squared", x * x)
        assert 3 + x == 8
"""


def roughly_now(abs=60):
    return pytest.approx(time.time(), abs=abs)


@pytest.fixture(autouse=True)
def new_run_id(monkeypatch) -> Callable:
    """
    Fixture to automatically initialise the run id
    and allow bumping it too (e.g. to simulate successive runs).
    """
    i = 0

    def set_run_id(run_id: int | None):
        nonlocal i
        if run_id is None:
            i = i + 1
            run_id = i
        else:
            i = run_id
        monkeypatch.setenv("APEX_ALGORITHMS_RUN_ID", f"test-run-{run_id}")

    # Automatically run it to initialize
    set_run_id(123)

    # Return the function to allow bumping
    yield set_run_id


def this_month() -> str:
    """
    Because of the setup of some of these tests (e.g. test suite in a subprocess)
    it would be pretty cumbersome (if not impossible) to mock the time in the appropriate places.
    Instead, we just here produce a string that represents the current month to be used in asserts.
    While this is not perfect (makes the tests a bit flaky), it's practically highly unlikely to hit that flakiness.
    """
    return time.strftime("%Y-%m")


def test_track_metric_basic_json(pytester: pytest.Pytester, tmp_path):
    pytester.makeconftest(CONTENT_CONFTEST)
    pytester.makepyfile(test_addition=CONTENT_TEST_ADDITION_PY)

    metrics_path = tmp_path / "metrics.json"

    run_result = pytester.runpytest_subprocess(
        f"--track-metrics-json={metrics_path}",
    )

    run_result.stdout.re_match_lines(
        [r"Plugin `track_metrics` is active, reporting to"]
    )
    run_result.assert_outcomes(passed=1, failed=1)

    assert metrics_path.exists()
    run_result.stdout.re_match_lines([f".*Generated.*{re.escape(str(metrics_path))}.*"])

    with metrics_path.open("r", encoding="utf8") as f:
        metrics = json.load(f)
    assert metrics == [
        {
            "nodeid": "test_addition.py::test_3plus[5]",
            "report": {
                "outcome": "passed",
                "duration": pytest.approx(0, abs=1),
                "start": roughly_now(),
                "stop": roughly_now(),
            },
            "metrics": [
                ["x squared", 25],
            ],
        },
        {
            "nodeid": "test_addition.py::test_3plus[6]",
            "report": {
                "outcome": "failed",
                "duration": pytest.approx(0, abs=1),
                "start": roughly_now(),
                "stop": roughly_now(),
            },
            "metrics": [
                ["x squared", 36],
            ],
        },
    ]


@pytest.mark.parametrize(
    ["src", "expected", "expected_warnings"],
    [
        (
            """
            def test_this(track_metric):
                track_metric("foo", 123, update=True)
            """,
            [["foo", 123]],
            None,
        ),
        (
            """
            def test_this(track_metric):
                track_metric("foo", 1)
                track_metric("foo", 22)
            """,
            [["foo", 1], ["foo", 22]],
            ["append with existing entries"],
        ),
        (
            """
            def test_this(track_metric):
                track_metric("foo", 1, update=True)
                track_metric("foo", 22, update=True)
                track_metric("foo", 333, update=True)
            """,
            [["foo", 333]],
            None,
        ),
        (
            """
            def test_this(track_metric):
                track_metric("foo", 1, update=True)
                track_metric("bar", 22, update=True)
                track_metric("foo", 333, update=True)
            """,
            [["foo", 333], ["bar", 22]],
            None,
        ),
        (
            """
            def test_this(track_metric):
                track_metric("foo", 1)
                track_metric("foo", 22)
                track_metric("foo", 333, update=True)
            """,
            [["foo", 333], ["foo", 333]],
            ["append with existing entries", "update with multiple entries"],
        ),
    ],
)
def test_track_metric_update_mode_json(
    pytester: pytest.Pytester, tmp_path, src, expected, expected_warnings
):
    pytester.makeconftest(CONTENT_CONFTEST)
    pytester.makepyfile(test_this=textwrap.dedent(src))

    metrics_path = tmp_path / "metrics.json"
    run_result = pytester.runpytest_subprocess(f"--track-metrics-json={metrics_path}")

    with metrics_path.open("r", encoding="utf8") as f:
        metrics = json.load(f)
    assert metrics == [
        {
            "nodeid": "test_this.py::test_this",
            "report": {
                "outcome": "passed",
                "duration": pytest.approx(0, abs=1),
                "start": roughly_now(),
                "stop": roughly_now(),
            },
            "metrics": expected,
        },
    ]

    if expected_warnings:
        run_result.stdout.re_match_lines(
            [f".*UserWarning:.*{re.escape(w)}.*" for w in expected_warnings],
        )
    else:
        assert "UserWarning" not in run_result.stdout.str()


@pytest.mark.parametrize(
    ["src", "expected"],
    [
        (
            """
            def test_phases(track_phase):
                with track_phase("setup"):
                    x = 123
                with track_phase("math"):
                    y = x * 2
                with track_phase("compare"):
                    assert y == 5
            """,
            [
                ["test:phase:start", "compare"],
                ["test:phase:end", "math"],
                ["test:phase:exception", "compare"],
            ],
        ),
        (
            """
            def test_phases(track_phase):
                with track_phase("setup"):
                    x = 123
                with track_phase("math"):
                    y = x * 2
                assert y == 5
            """,
            [
                ["test:phase:start", "math"],
                ["test:phase:end", "math"],
            ],
        ),
    ],
)
def test_track_phase_basic_json(pytester: pytest.Pytester, tmp_path, src, expected):
    pytester.makeconftest(CONTENT_CONFTEST)
    pytester.makepyfile(test_addition=textwrap.dedent(src))
    metrics_path = tmp_path / "metrics.json"

    pytester.runpytest_subprocess(f"--track-metrics-json={metrics_path}")

    with metrics_path.open("r", encoding="utf8") as f:
        metrics = json.load(f)
    assert metrics == [
        {
            "nodeid": "test_addition.py::test_phases",
            "report": {
                "outcome": "failed",
                "duration": pytest.approx(0, abs=1),
                "start": roughly_now(),
                "stop": roughly_now(),
            },
            "metrics": expected,
        },
    ]


def recursive_dir_listing(path: Path) -> List[str]:
    """Recursive and relative listing of files/dirs under a folder."""
    return sorted(str(p.relative_to(path)) for p in path.rglob("*"))


class TestTrackMetricsParquet:
    def _check_metrics_pandas(self, df: pandas.DataFrame):
        assert set(df.columns) == {
            "suite:run_id",
            "test:nodeid",
            "test:outcome",
            "test:duration",
            "test:start",
            "test:start:YYYYMM",
            "test:start:datetime",
            "test:stop",
            "x squared",
        }
        df = df.set_index("test:nodeid")
        assert df.loc["test_addition.py::test_3plus[5]"].to_dict() == {
            "suite:run_id": "test-run-123",
            "test:outcome": "passed",
            "test:duration": pytest.approx(0, abs=1),
            "test:start": roughly_now(),
            "test:start:YYYYMM": this_month(),
            "test:start:datetime": dirty_equals.IsStr(
                regex=this_month() + r"-\d{2}T\d{2}:\d{2}:\d{2}Z"
            ),
            "test:stop": roughly_now(),
            "x squared": 25,
        }
        assert df.loc["test_addition.py::test_3plus[6]"].to_dict() == {
            "suite:run_id": "test-run-123",
            "test:outcome": "failed",
            "test:duration": pytest.approx(0, abs=1),
            "test:start": roughly_now(),
            "test:start:YYYYMM": this_month(),
            "test:start:datetime": dirty_equals.IsStr(
                regex=this_month() + r"-\d{2}T\d{2}:\d{2}:\d{2}Z"
            ),
            "test:stop": roughly_now(),
            "x squared": 36,
        }

    def test_local_basic(self, pytester: pytest.Pytester, tmp_path):
        pytester.makeconftest(CONTENT_CONFTEST)
        pytester.makepyfile(test_addition=CONTENT_TEST_ADDITION_PY)

        metrics_path = tmp_path / "metrics.parquet"
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet={metrics_path}",
        )

        run_result.stdout.re_match_lines(
            [r"Plugin `track_metrics` is active, reporting to"]
        )
        run_result.assert_outcomes(passed=1, failed=1)
        run_result.stdout.re_match_lines(
            [f".*Generated.*{re.escape(str(metrics_path))}.*"]
        )

        assert metrics_path.exists() and metrics_path.is_file()
        table = pyarrow.parquet.read_table(metrics_path)
        self._check_metrics_pandas(df=table.to_pandas())

    def test_local_partitioning_simple(
        self, pytester: pytest.Pytester, tmp_path, new_run_id
    ):
        pytester.makeconftest(CONTENT_CONFTEST)
        pytester.makepyfile(test_addition=CONTENT_TEST_ADDITION_PY)

        metrics_path = tmp_path / "metrics.parquet"
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet={metrics_path}",
            "--track-metrics-parquet-partitioning=simple",
        )
        run_result.assert_outcomes(passed=1, failed=1)
        run_result.stdout.re_match_lines(
            [f".*Generated.*{re.escape(str(metrics_path))}.*"]
        )

        assert metrics_path.exists() and metrics_path.is_dir()
        assert recursive_dir_listing(metrics_path) == [
            "test-run-123-0.parquet",
        ]

        table = pyarrow.parquet.read_table(metrics_path)
        self._check_metrics_pandas(df=table.to_pandas())

        # Run second time to check for append mode
        new_run_id(456)
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet={metrics_path}",
            "--track-metrics-parquet-partitioning=simple",
        )
        run_result.assert_outcomes(passed=1, failed=1)
        assert recursive_dir_listing(metrics_path) == [
            "test-run-123-0.parquet",
            "test-run-456-0.parquet",
        ]

    def test_local_partitioning_yyyymm(
        self, pytester: pytest.Pytester, tmp_path, new_run_id
    ):
        pytester.makeconftest(CONTENT_CONFTEST)
        pytester.makepyfile(test_addition=CONTENT_TEST_ADDITION_PY)

        metrics_path = tmp_path / "metrics.parquet"
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet={metrics_path}",
            "--track-metrics-parquet-partitioning=YYYYMM",
        )
        run_result.assert_outcomes(passed=1, failed=1)
        run_result.stdout.re_match_lines(
            [f".*Generated.*{re.escape(str(metrics_path))}.*"]
        )

        assert metrics_path.exists() and metrics_path.is_dir()
        assert recursive_dir_listing(metrics_path) == [
            this_month(),
            f"{this_month()}/test-run-123-0.parquet",
        ]

        table = pyarrow.parquet.read_table(
            metrics_path,
            partitioning=pyarrow.dataset.partitioning(
                schema=pyarrow.schema([("test:start:YYYYMM", pyarrow.string())])
            ),
        )
        self._check_metrics_pandas(df=table.to_pandas())

        # Run second time to check for append mode
        new_run_id(456)
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet={metrics_path}",
            "--track-metrics-parquet-partitioning=YYYYMM",
        )
        run_result.assert_outcomes(passed=1, failed=1)

        assert recursive_dir_listing(metrics_path) == [
            this_month(),
            f"{this_month()}/test-run-123-0.parquet",
            f"{this_month()}/test-run-456-0.parquet",
        ]

    @pytest.mark.slow
    def test_s3_basic(
        self, pytester: pytest.Pytester, moto_server, s3_client, s3_bucket, monkeypatch
    ):
        pytester.makeconftest(CONTENT_CONFTEST)
        pytester.makepyfile(test_addition=CONTENT_TEST_ADDITION_PY)

        monkeypatch.setenv("APEX_ALGORITHMS_S3_ENDPOINT_URL", moto_server)
        s3_key = "metrics-v0.parquet"
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet-s3-bucket={s3_bucket}",
            f"--track-metrics-parquet-s3-key={s3_key}",
        )

        run_result.stdout.re_match_lines(
            [r"Plugin `track_metrics` is active, reporting to"]
        )
        run_result.assert_outcomes(passed=1, failed=1)
        run_result.stdout.re_match_lines(
            [f".*Generated.*{re.escape(str(s3_bucket))}.*{re.escape(str(s3_key))}.*"]
        )

        # Check for written Parquet files on S3
        object_listing = s3_client.list_objects(Bucket=s3_bucket)
        assert len(object_listing["Contents"])
        keys = sorted(obj["Key"] for obj in object_listing["Contents"])
        assert keys == [
            f"{s3_key}/",
            f"{s3_key}/test-run-123-0.parquet",
        ]

        # Load the Parquet file from S3
        fs = pyarrow.fs.S3FileSystem(endpoint_override=moto_server)
        table = pyarrow.parquet.read_table(f"{s3_bucket}/{s3_key}", filesystem=fs)
        self._check_metrics_pandas(df=table.to_pandas())

    @pytest.mark.slow
    def test_s3_partitioning_simple(
        self,
        pytester: pytest.Pytester,
        moto_server,
        s3_client,
        s3_bucket,
        monkeypatch,
        new_run_id,
    ):
        pytester.makeconftest(CONTENT_CONFTEST)
        pytester.makepyfile(test_addition=CONTENT_TEST_ADDITION_PY)

        monkeypatch.setenv("APEX_ALGORITHMS_S3_ENDPOINT_URL", moto_server)
        s3_key = "metrics-v0.parquet"
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet-s3-bucket={s3_bucket}",
            f"--track-metrics-parquet-s3-key={s3_key}",
            "--track-metrics-parquet-partitioning=simple",
        )
        run_result.assert_outcomes(passed=1, failed=1)
        run_result.stdout.re_match_lines(
            [f".*Generated.*{re.escape(str(s3_bucket))}.*{re.escape(str(s3_key))}.*"]
        )

        # Check for written Parquet files on S3
        object_listing = s3_client.list_objects(Bucket=s3_bucket)
        assert len(object_listing["Contents"])
        keys = sorted(obj["Key"] for obj in object_listing["Contents"])
        assert keys == [
            f"{s3_key}/",
            f"{s3_key}/test-run-123-0.parquet",
        ]

        # Load the Parquet file from S3
        fs = pyarrow.fs.S3FileSystem(endpoint_override=moto_server)
        table = pyarrow.parquet.read_table(f"{s3_bucket}/{s3_key}", filesystem=fs)
        self._check_metrics_pandas(df=table.to_pandas())

        # Run second time to check for append mode
        new_run_id(456)
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet-s3-bucket={s3_bucket}",
            f"--track-metrics-parquet-s3-key={s3_key}",
            "--track-metrics-parquet-partitioning=simple",
        )
        run_result.assert_outcomes(passed=1, failed=1)

        # Check for written Parquet files on S3
        object_listing = s3_client.list_objects(Bucket=s3_bucket)
        assert len(object_listing["Contents"])
        keys = sorted(obj["Key"] for obj in object_listing["Contents"])
        assert keys == [
            f"{s3_key}/",
            f"{s3_key}/test-run-123-0.parquet",
            f"{s3_key}/test-run-456-0.parquet",
        ]

    @pytest.mark.slow
    def test_s3_partitioning_yyyymm(
        self,
        pytester: pytest.Pytester,
        moto_server,
        s3_client,
        s3_bucket,
        monkeypatch,
        new_run_id,
    ):
        pytester.makeconftest(CONTENT_CONFTEST)
        pytester.makepyfile(test_addition=CONTENT_TEST_ADDITION_PY)

        monkeypatch.setenv("APEX_ALGORITHMS_S3_ENDPOINT_URL", moto_server)
        s3_key = "metrics-v0.parquet"
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet-s3-bucket={s3_bucket}",
            f"--track-metrics-parquet-s3-key={s3_key}",
            "--track-metrics-parquet-partitioning=YYYYMM",
        )
        run_result.assert_outcomes(passed=1, failed=1)
        run_result.stdout.re_match_lines(
            [f".*Generated.*{re.escape(str(s3_bucket))}.*{re.escape(str(s3_key))}.*"]
        )

        # Check for written Parquet files on S3
        object_listing = s3_client.list_objects(Bucket=s3_bucket)
        assert len(object_listing["Contents"])
        keys = sorted(obj["Key"] for obj in object_listing["Contents"])
        assert keys == [
            f"{s3_key}/",
            f"{s3_key}/{this_month()}/",
            f"{s3_key}/{this_month()}/test-run-123-0.parquet",
        ]

        # Load the Parquet file from S3
        fs = pyarrow.fs.S3FileSystem(endpoint_override=moto_server)
        table = pyarrow.parquet.read_table(
            f"{s3_bucket}/{s3_key}",
            filesystem=fs,
            partitioning=pyarrow.dataset.partitioning(
                schema=pyarrow.schema([("test:start:YYYYMM", pyarrow.string())])
            ),
        )
        self._check_metrics_pandas(df=table.to_pandas())

        # Run second time to check for append mode
        new_run_id(456)
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet-s3-bucket={s3_bucket}",
            f"--track-metrics-parquet-s3-key={s3_key}",
            "--track-metrics-parquet-partitioning=YYYYMM",
        )
        run_result.assert_outcomes(passed=1, failed=1)

        # Check for written Parquet files on S3
        object_listing = s3_client.list_objects(Bucket=s3_bucket)
        assert len(object_listing["Contents"])
        keys = sorted(obj["Key"] for obj in object_listing["Contents"])
        assert keys == [
            f"{s3_key}/",
            f"{s3_key}/{this_month()}/",
            f"{s3_key}/{this_month()}/test-run-123-0.parquet",
            f"{s3_key}/{this_month()}/test-run-456-0.parquet",
        ]
