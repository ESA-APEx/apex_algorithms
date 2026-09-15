import datetime

import pyarrow
from apex_algorithm_qa_tools.github_issue_handler import (
    GithubContext,
    PerformanceRegressionInfo,
)
from apex_algorithm_qa_tools.metrics.parquet_metrics import (
    load_recent_scenario_metrics_map,
)
from apex_algorithm_qa_tools.metrics.performance_baselines import (
    _check_reference_performance,
    _compute_baselines,
    _compute_threshold_stats,
)


def test_compute_threshold_stats_respects_min_margin_floor():
    stats = _compute_threshold_stats([10.0, 10.0, 10.0], k=3.0, min_margin=2.0)

    assert stats["k"] == 3.0
    assert isinstance(stats["observations"], int)
    assert stats["observations"] == 3
    assert stats["margin"] == 2.0
    assert stats["upper_limit"] == 12.0
    assert stats["lower_limit"] == 8.0


def test_compute_baselines_skips_nan_and_limits_sample_window():
    historical_values = [
        {"costs": 1.0},
        {"costs": 2.0},
        {"costs": float("nan")},
        {"costs": 3.0},
        {"costs": 4.0},
    ]

    baselines = _compute_baselines(historical_values, metric_names=["costs"], max_samples=3)

    assert "costs" in baselines
    # Last non-NaN values within sample window are 2.0, 3.0, 4.0 -> median 3.0.
    assert baselines["costs"]["median"] == 3.0


def test_check_reference_performance_can_do_upper():
    violations = _check_reference_performance(
        scenario_id="s1",
        reference_performance={"costs": {"upper_limit": 10.0}},
        tracked_metrics={"costs": 12.0},
    )

    assert violations == ["[s1] regression in 'costs': actual=12.0 exceeds upper_limit=10.0"]


def test_check_reference_performance_reports_below_lower_limit_when_present():
    violations = _check_reference_performance(
        scenario_id="s1",
        reference_performance={"costs": {"lower_limit": 5.0, "upper_limit": 10.0}},
        tracked_metrics={"costs": 4.0},
    )

    assert violations == ["[s1] regression in 'costs': actual=4.0 below lower_limit=5.0"]


def test_check_reference_performance_no_violations_within_band():
    violations = _check_reference_performance(
        scenario_id="s1",
        reference_performance={"costs": {"lower_limit": 5.0, "upper_limit": 10.0}},
        tracked_metrics={"costs": 8.0},
    )

    assert violations == []

def test_compute_baselines_exposes_upper_and_lower_limit_fields():
    baselines = _compute_baselines(
        [{"costs": 4.0}, {"costs": 5.0}, {"costs": 6.0}],
        metric_names=["costs"],
    )

    assert "costs" in baselines
    assert "upper_limit" in baselines["costs"]
    assert "lower_limit" in baselines["costs"]


def test_load_recent_scenario_metrics_map_groups_and_formats_timestamps(monkeypatch):
    now = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
    older = now - 3600

    table = pyarrow.table(
        {
            "test:nodeid": [
                "qa/tests/test_benchmarks.py::test_run_benchmark[scenario-a]",
                "qa/tests/test_benchmarks.py::test_run_benchmark[scenario-a]",
                "qa/tests/test_benchmarks.py::test_run_benchmark[scenario-b]",
            ],
            "test:outcome": ["passed", "passed", "passed"],
            "test:start": [older, now, now],
            "costs": [1.0, 2.0, 3.0],
        }
    )

    class DummyDataset:
        schema = pyarrow.schema(
            [
                pyarrow.field("test:nodeid", pyarrow.string()),
                pyarrow.field("test:outcome", pyarrow.string()),
                pyarrow.field("test:start", pyarrow.float64()),
                pyarrow.field("costs", pyarrow.float64()),
            ]
        )

        def to_table(self, columns, filter=None):
            # Ensure the scan path only asks for projected columns.
            assert "test:nodeid" in columns
            assert "costs" in columns
            return table

    monkeypatch.setattr(
        "apex_algorithm_qa_tools.metrics.parquet_metrics.pyarrow.dataset.dataset",
        lambda *args, **kwargs: DummyDataset(),
    )

    result = load_recent_scenario_metrics_map(
        parquet_path="dummy/path",
        metric_names=["costs"],
        test_outcome="passed",
        max_age_days=1,
    )

    assert sorted(result.keys()) == ["scenario-a", "scenario-b"]
    assert [row["costs"] for row in result["scenario-a"]] == [1.0, 2.0]
    assert "_timestamp" in result["scenario-a"][0]
    assert "_datetime" in result["scenario-a"][0]


def test_performance_regression_issue_body_contains_summary_table():
    info = PerformanceRegressionInfo(
        scenario_id="scenario-a",
        github_context=GithubContext(),
        violation="[scenario-a] regression in 'costs': actual=12.0 exceeds upper_limit=10.0",
        baseline={"upper_limit": 10.0},
        latest_metrics={"costs": 12.0},
        history_values=[7.0, 8.0, 9.0],
        history_labels=["d1", "d2", "d3"],
        latest_label="latest",
        metric_name="costs",
        scenario=None,
    )

    body = info.build_issue_body()

    assert "### Summary" in body
    assert "| current | median | upper_limit | lower_limit | nr_observations |" in body
    assert "12" in body


