import json
from pathlib import Path
from typing import List

import openeo.rest.job
import openeo.testing.results
import pytest
from apex_algorithm_qa_tools.benchmarks import (
    analyse_results_comparison_exception,
    collect_metrics_from_job_metadata,
    collect_metrics_from_results_metadata,
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
