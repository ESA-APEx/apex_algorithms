import json
from pathlib import Path
from typing import List

import openeo.rest.job
import openeo.testing.results
import pytest
from apex_algorithm_qa_tools.benchmarks import (
    analyse_results_comparison_exception,
    check_reference_performance,
    collect_metrics_from_job_metadata,
    collect_metrics_from_results_metadata,
    compute_adaptive_baselines,
)


class DummyTracker:
    def __init__(self):
        self.data = []

    def __call__(self, name, value) -> None:
        self.data.append((name, value))


@pytest.fixture
def dummy_tracker() -> DummyTracker:
    return DummyTracker()


def test_collect_metrics_from_job_metadata(dummy_tracker):
    metadata = {
        "id": "job-1",
        "costs": 42,
        "usage": {
            "cpu": {"unit": "cpu-seconds", "value": 123},
            "memory": {"unit": "mb-seconds", "value": 345},
        },
    }
    collect_metrics_from_job_metadata(metadata, track_metric=dummy_tracker)
    assert dummy_tracker.data == [
        ("costs", 42),
        ("usage:cpu:cpu-seconds", 123),
        ("usage:memory:mb-seconds", 345),
    ]


def test_collect_metrics_from_results_metadata_proj_shape(dummy_tracker):
    metadata = {
        "type": "Collection",
        "id": "j-240911a7fc064f64abd5a62bd8ef42ce",
        "assets": {
            "openEO.nc": {
                "proj:shape": [1200, 800],
            }
        },
    }
    collect_metrics_from_results_metadata(metadata, track_metric=dummy_tracker)
    assert dummy_tracker.data == [
        ("results:proj:shape:area:megapixel", 1.2 * 0.8),
    ]


def test_collect_metrics_from_results_metadata_shape_and_bbox(dummy_tracker):
    metadata = {
        "type": "Collection",
        "id": "j-240911a7fc064f64abd5a62bd8ef42ce",
        "assets": {
            "openEO.nc": {
                "proj:bbox": [500000, 5645000, 508000, 5657000],
                "proj:epsg": 32631,
                "proj:shape": [1200, 800],
            }
        },
    }
    collect_metrics_from_results_metadata(metadata, track_metric=dummy_tracker)
    assert dummy_tracker.data == [
        ("results:proj:shape:area:megapixel", 1.2 * 0.8),
        ("results:proj:bbox:area:utm:km2", 12 * 8),
    ]




def test_check_reference_performance_pass():
    """Test that check_reference_performance passes when metrics are within bounds."""
    tracked = {
        "costs": 4.5,
        "usage:cpu:cpu-seconds": 2500,
        "usage:duration:seconds": 100,
    }
    reference = {
        "costs": {"max": 5, "tolerance": 0.2},
        "usage:cpu:cpu-seconds": {"max": 3000, "tolerance": 0.2},
        "usage:duration:seconds": {"max": 120, "tolerance": 0.2},
    }
    violations = check_reference_performance(
        scenario_id="test_scenario",
        reference_performance=reference,
        tracked_metrics=tracked,
    )
    assert violations == []


def test_check_reference_performance_regression():
    """Test that check_reference_performance detects regressions."""
    tracked = {
        "costs": 7.0,  # exceeds 5 * 1.2 = 6.0
        "usage:cpu:cpu-seconds": 2500,
    }
    reference = {
        "costs": {"max": 5, "tolerance": 0.2},
        "usage:cpu:cpu-seconds": {"max": 3000, "tolerance": 0.2},
    }
    violations = check_reference_performance(
        scenario_id="test_scenario",
        reference_performance=reference,
        tracked_metrics=tracked,
    )
    assert len(violations) == 1
    assert "regression in 'costs'" in violations[0]


def test_check_reference_performance_missing_metric():
    """Test that missing metrics are silently skipped (only flag regressions)."""
    tracked = {"costs": 4.5}
    reference = {
        "costs": {"max": 5},
        "usage:cpu:cpu-seconds": {"max": 3000},
    }
    violations = check_reference_performance(
        scenario_id="test_scenario",
        reference_performance=reference,
        tracked_metrics=tracked,
    )
    assert violations == []


def test_compute_adaptive_baselines_single_observation():
    """With 1 observation, uses the value with 50% tolerance."""
    history = [{"costs": 10.0}]
    baselines = compute_adaptive_baselines(history, metric_names=["costs"])
    assert baselines["costs"]["max"] == 10.0
    assert baselines["costs"]["tolerance"] == 0.5
    assert baselines["costs"]["n_samples"] == 1


def test_compute_adaptive_baselines_two_observations():
    """With 2 observations, k(2)=4.0 so threshold is very loose."""
    history = [{"costs": 10.0}, {"costs": 12.0}]
    baselines = compute_adaptive_baselines(history, metric_names=["costs"])
    assert baselines["costs"]["n_samples"] == 2
    assert baselines["costs"]["k"] == 4.0
    assert baselines["costs"]["tolerance"] == 0  # baked into max
    # mean=11, std~=1.414, threshold = 11 + 4.0*1.414 = ~16.66
    assert baselines["costs"]["max"] > 16.0


def test_compute_adaptive_baselines_many_observations():
    """With many observations, only last 10 are used, k(10)=2.0."""
    history = [{"costs": 10.0 + i * 0.1} for i in range(20)]
    baselines = compute_adaptive_baselines(history, metric_names=["costs"])
    assert baselines["costs"]["n_samples"] == 10  # capped at 10
    assert baselines["costs"]["k"] == 2.0  # exactly 2σ at n=10


def test_compute_adaptive_baselines_auto_detect_metrics():
    """Without explicit metric_names, auto-detects numeric fields."""
    history = [
        {"costs": 10.0, "usage:cpu:cpu-seconds": 100, "scenario_id": "foo"},
        {"costs": 12.0, "usage:cpu:cpu-seconds": 110, "scenario_id": "foo"},
        {"costs": 11.0, "usage:cpu:cpu-seconds": 105, "scenario_id": "foo"},
    ]
    baselines = compute_adaptive_baselines(history)
    assert "costs" in baselines
    assert "usage:cpu:cpu-seconds" in baselines
    # scenario_id is a string, not numeric, so should not appear
    assert "scenario_id" not in baselines


def test_compute_adaptive_baselines_empty():
    """Empty history returns empty baselines."""
    assert compute_adaptive_baselines([]) == {}


def test_adaptive_baselines_integration():
    """Adaptive baselines work end-to-end with check_reference_performance."""
    history = [
        {"costs": 10.0},
        {"costs": 11.0},
        {"costs": 10.5},
    ]
    baselines = compute_adaptive_baselines(history, metric_names=["costs"])
    # A value within the adaptive band should pass
    violations = check_reference_performance(
        scenario_id="test",
        reference_performance=baselines,
        tracked_metrics={"costs": 12.0},
    )
    assert violations == []
    # A wildly high value should fail
    violations = check_reference_performance(
        scenario_id="test",
        reference_performance=baselines,
        tracked_metrics={"costs": 50.0},
    )
    assert len(violations) == 1
    assert "regression" in violations[0]


def _create_metadata_file(path: Path, *, links: List[dict] | None):
    metadata = {}
    if links is not None:
        metadata["links"] = links
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf8") as f:
        json.dump(fp=f, obj=metadata)


def test_analyse_results_comparison_exception_derived_from(tmp_path):
    actual = tmp_path / "actual"
    reference = tmp_path / "reference"

    _create_metadata_file(
        actual / openeo.rest.job.DEFAULT_JOB_RESULTS_FILENAME,
        links=[{"rel": "derived_from", "href": "/path/to/S2_V1.SAFE"}],
    )
    _create_metadata_file(
        reference / openeo.rest.job.DEFAULT_JOB_RESULTS_FILENAME,
        links=[{"rel": "derived_from", "href": "/path/to/S2_V2.SAFE"}],
    )

    with pytest.raises(
        AssertionError, match="Differing.*derived_from.*links"
    ) as exc_info:
        openeo.testing.results.assert_job_results_allclose(
            actual=actual,
            expected=reference,
        )

    assert analyse_results_comparison_exception(exc_info.value) == "derived_from-change"
