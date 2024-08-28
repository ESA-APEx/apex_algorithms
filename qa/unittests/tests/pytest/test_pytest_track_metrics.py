import json
import re
import time

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
def _set_run_id(monkeypatch):
    monkeypatch.setenv("APEX_ALGORITHMS_RUN_ID", "test-run-123")


def test_track_metric_json(pytester: pytest.Pytester, tmp_path):
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
            "test:start:YYYYMM": dirty_equals.IsStr(regex=r"\d{4}-\d{2}"),
            "test:start:datetime": dirty_equals.IsStr(
                regex=r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
            ),
            "test:stop": roughly_now(),
            "x squared": 25,
        }
        assert df.loc["test_addition.py::test_3plus[6]"].to_dict() == {
            "suite:run_id": "test-run-123",
            "test:outcome": "failed",
            "test:duration": pytest.approx(0, abs=1),
            "test:start": roughly_now(),
            "test:start:YYYYMM": dirty_equals.IsStr(regex=r"\d{4}-\d{2}"),
            "test:start:datetime": dirty_equals.IsStr(
                regex=r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
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

    def test_local_partitioning_simple(self, pytester: pytest.Pytester, tmp_path):
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
        assert len(list(metrics_path.glob("*-0.parquet"))) == 1

        table = pyarrow.parquet.read_table(metrics_path)
        self._check_metrics_pandas(df=table.to_pandas())

        # Run second time to check for append mode
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet={metrics_path}",
            "--track-metrics-parquet-partitioning=simple",
        )
        run_result.assert_outcomes(passed=1, failed=1)

        assert len(list(metrics_path.glob("*-0.parquet"))) == 2

    def test_local_partitioning_yyyymm(self, pytester: pytest.Pytester, tmp_path):
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

        partitions = list(metrics_path.iterdir())
        assert len(partitions) == 1
        assert partitions[0].name == dirty_equals.IsStr(regex=r"\d{4}-\d{2}")
        assert partitions[0].is_dir()
        assert len(list(partitions[0].glob("*-0.parquet"))) == 1

        table = pyarrow.parquet.read_table(
            metrics_path,
            partitioning=pyarrow.dataset.partitioning(
                schema=pyarrow.schema([("test:start:YYYYMM", pyarrow.string())])
            ),
        )
        self._check_metrics_pandas(df=table.to_pandas())

        # Run second time to check for append mode
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet={metrics_path}",
            "--track-metrics-parquet-partitioning=YYYYMM",
        )
        run_result.assert_outcomes(passed=1, failed=1)

        partitions = list(metrics_path.iterdir())
        assert len(partitions) == 1
        assert partitions[0].name == dirty_equals.IsStr(regex=r"\d{4}-\d{2}")
        assert partitions[0].is_dir()
        assert len(list(partitions[0].glob("*-0.parquet"))) == 2

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
        keys = [obj["Key"] for obj in object_listing["Contents"]]
        assert keys == [
            f"{s3_key}/",
            dirty_equals.IsStr(regex=rf"^{re.escape(s3_key)}/[0-9a-f]+-0.parquet$"),
        ]

        # Load the Parquet file from S3
        fs = pyarrow.fs.S3FileSystem(endpoint_override=moto_server)
        table = pyarrow.parquet.read_table(f"{s3_bucket}/{s3_key}", filesystem=fs)
        self._check_metrics_pandas(df=table.to_pandas())

    def test_s3_partitioning_simple(
        self, pytester: pytest.Pytester, moto_server, s3_client, s3_bucket, monkeypatch
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
        keys = [obj["Key"] for obj in object_listing["Contents"]]
        assert keys == [
            f"{s3_key}/",
            dirty_equals.IsStr(regex=rf"^{re.escape(s3_key)}/[0-9a-f]+-0.parquet$"),
        ]

        # Load the Parquet file from S3
        fs = pyarrow.fs.S3FileSystem(endpoint_override=moto_server)
        table = pyarrow.parquet.read_table(f"{s3_bucket}/{s3_key}", filesystem=fs)
        self._check_metrics_pandas(df=table.to_pandas())

        # Run second time to check for append mode
        run_result = pytester.runpytest_subprocess(
            f"--track-metrics-parquet-s3-bucket={s3_bucket}",
            f"--track-metrics-parquet-s3-key={s3_key}",
            "--track-metrics-parquet-partitioning=simple",
        )
        run_result.assert_outcomes(passed=1, failed=1)

        # Check for written Parquet files on S3
        object_listing = s3_client.list_objects(Bucket=s3_bucket)
        assert len(object_listing["Contents"])
        keys = [obj["Key"] for obj in object_listing["Contents"]]
        assert keys == [
            f"{s3_key}/",
            dirty_equals.IsStr(regex=rf"^{re.escape(s3_key)}/[0-9a-f]+-0.parquet$"),
            dirty_equals.IsStr(regex=rf"^{re.escape(s3_key)}/[0-9a-f]+-0.parquet$"),
        ]

    def test_s3_partitioning_yyyymm(
        self, pytester: pytest.Pytester, moto_server, s3_client, s3_bucket, monkeypatch
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
            dirty_equals.IsStr(regex=rf"^{re.escape(s3_key)}/\d{{4}}-\d{{2}}/$"),
            dirty_equals.IsStr(
                regex=rf"^{re.escape(s3_key)}/\d{{4}}-\d{{2}}/[0-9a-f]+-0.parquet$"
            ),
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
            dirty_equals.IsStr(regex=rf"^{re.escape(s3_key)}/\d{{4}}-\d{{2}}/$"),
            dirty_equals.IsStr(
                regex=rf"^{re.escape(s3_key)}/\d{{4}}-\d{{2}}/[0-9a-f]+-0.parquet$"
            ),
            dirty_equals.IsStr(
                regex=rf"^{re.escape(s3_key)}/\d{{4}}-\d{{2}}/[0-9a-f]+-0.parquet$"
            ),
        ]
