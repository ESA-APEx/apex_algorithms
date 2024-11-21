import pytest
from apex_algorithm_qa_tools.benchmarks import (
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
