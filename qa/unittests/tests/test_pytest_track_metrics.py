import json
import re
import time

import pyarrow.parquet
import pytest


def test_track_metric_basics_json(pytester: pytest.Pytester, tmp_path):
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
    run_result = pytester.runpytest(
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
    approx_now = pytest.approx(time.time(), abs=1)
    assert metrics == [
        {
            "nodeid": "test_addition.py::test_3plus[5]",
            "report": {
                "outcome": "passed",
                "duration": pytest.approx(0, abs=1),
                "start": approx_now,
                "stop": approx_now,
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
                "start": approx_now,
                "stop": approx_now,
            },
            "metrics": [
                ["x squared", 36],
            ],
        },
    ]


def test_track_metric_basics_parquet(pytester: pytest.Pytester, tmp_path):
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

    metrics_path = tmp_path / "metrics.parquet"
    run_result = pytester.runpytest(
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

    approx_now = pytest.approx(time.time(), abs=1)

    assert df.loc["test_addition.py::test_3plus[5]"].to_dict() == {
        "outcome": "passed",
        "duration": pytest.approx(0, abs=1),
        "start": approx_now,
        "stop": approx_now,
        "x squared": 25,
    }
    assert df.loc["test_addition.py::test_3plus[6]"].to_dict() == {
        "outcome": "failed",
        "duration": pytest.approx(0, abs=1),
        "start": approx_now,
        "stop": approx_now,
        "x squared": 36,
    }
