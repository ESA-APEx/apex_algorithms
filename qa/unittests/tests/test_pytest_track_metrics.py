import json
import re
import time

import pyarrow.parquet
import pytest


def test_track_metric_json(pytester: pytest.Pytester, tmp_path):
    pytester.makeconftest(
        """
        pytest_plugins = [
            "apex_algorithm_qa_tools.pytest_track_metrics",
        ]
        """
    )
    pytester.makepyfile(
        test_addition="""
            import pytest

            @pytest.mark.parametrize("x", [5, 6])
            def test_3plus(track_metric, x):
                track_metric("x squared", x * x)
                assert 3 + x == 8
        """
    )

    metrics_path = tmp_path / "metrics.json"

    start_time = time.time()
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
                "start": pytest.approx(start_time, abs=1),
                "stop": pytest.approx(start_time, abs=1),
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
                "start": pytest.approx(start_time, abs=1),
                "stop": pytest.approx(start_time, abs=1),
            },
            "metrics": [
                ["x squared", 36],
            ],
        },
    ]


def test_track_metric_parquet_local(pytester: pytest.Pytester, tmp_path):
    pytester.makeconftest(
        """
        pytest_plugins = [
            "apex_algorithm_qa_tools.pytest_track_metrics",
        ]
        """
    )
    pytester.makepyfile(
        test_addition="""
            import pytest

            @pytest.mark.parametrize("x", [5, 6])
            def test_3plus(track_metric, x):
                track_metric("x squared", x * x)
                assert 3 + x == 8
        """
    )

    metrics_path = tmp_path / "metrics.json"

    start_time = time.time()
    run_result = pytester.runpytest_subprocess(
        f"--track-metrics-parquet={metrics_path}",
    )

    run_result.stdout.re_match_lines(
        [r"Plugin `track_metrics` is active, reporting to"]
    )
    run_result.assert_outcomes(passed=1, failed=1)

    assert metrics_path.exists()
    run_result.stdout.re_match_lines([f".*Generated.*{re.escape(str(metrics_path))}.*"])

    table = pyarrow.parquet.read_table(metrics_path)

    df = table.to_pandas()
    assert set(df.columns) == {
        "nodeid",
        "outcome",
        "duration",
        "start",
        "stop",
        "x squared",
    }
    df = df.set_index("nodeid")
    assert df.loc["test_addition.py::test_3plus[5]"].to_dict() == {
        "outcome": "passed",
        "duration": pytest.approx(0, abs=1),
        "start": pytest.approx(start_time, abs=1),
        "stop": pytest.approx(start_time, abs=1),
        "x squared": 25,
    }
    assert df.loc["test_addition.py::test_3plus[6]"].to_dict() == {
        "outcome": "failed",
        "duration": pytest.approx(0, abs=1),
        "start": pytest.approx(start_time, abs=1),
        "stop": pytest.approx(start_time, abs=1),
        "x squared": 36,
    }


def test_track_metric_parquet_s3(
    pytester: pytest.Pytester, moto_server, s3_client, s3_bucket, monkeypatch
):
    pytester.makeconftest(
        """
        pytest_plugins = [
            "apex_algorithm_qa_tools.pytest_track_metrics",
        ]
        """
    )
    pytester.makepyfile(
        test_addition="""
            import pytest

            @pytest.mark.parametrize("x", [5, 6])
            def test_3plus(track_metric, x):
                track_metric("x squared", x * x)
                assert 3 + x == 8
        """
    )

    monkeypatch.setenv("APEX_ALGORITHMS_S3_ENDPOINT_URL", moto_server)
    s3_key = "metrics-v0.parquet"

    start_time = time.time()
    run_result = pytester.runpytest_subprocess(
        f"--track-metrics-parquet-s3-bucket={s3_bucket}",
        f"--track-metrics-parquet-s3-key={s3_key}",
    )

    run_result.stdout.re_match_lines(
        [r"Plugin `track_metrics` is active, reporting to"]
    )
    run_result.assert_outcomes(passed=1, failed=1)

    # Check for written Parquet files on S3
    object_listing = s3_client.list_objects(Bucket=s3_bucket)
    assert len(object_listing["Contents"])
    keys = [obj["Key"] for obj in object_listing["Contents"]]
    assert f"{s3_key}/" in keys

    # Load the Parquet file from S3
    fs = pyarrow.fs.S3FileSystem(endpoint_override=moto_server)
    table = pyarrow.parquet.read_table(f"{s3_bucket}/{s3_key}", filesystem=fs)

    run_result.stdout.re_match_lines(
        [f".*Generated.*{re.escape(str(s3_bucket))}.*{re.escape(str(s3_key))}.*"]
    )

    df = table.to_pandas()
    assert set(df.columns) == {
        "nodeid",
        "outcome",
        "duration",
        "start",
        "stop",
        "x squared",
    }
    df = df.set_index("nodeid")
    assert df.loc["test_addition.py::test_3plus[5]"].to_dict() == {
        "outcome": "passed",
        "duration": pytest.approx(0, abs=1),
        "start": pytest.approx(start_time, abs=1),
        "stop": pytest.approx(start_time, abs=1),
        "x squared": 25,
    }
    assert df.loc["test_addition.py::test_3plus[6]"].to_dict() == {
        "outcome": "failed",
        "duration": pytest.approx(0, abs=1),
        "start": pytest.approx(start_time, abs=1),
        "stop": pytest.approx(start_time, abs=1),
        "x squared": 36,
    }
