import logging
from pathlib import Path

import openeo
import pytest
from apex_algorithm_qa_tools.pytest.pytest_track_metrics import MetricsTracker
from apex_algorithm_qa_tools.scenarios import (
    BenchmarkScenario,
    download_reference_data,
    get_benchmark_scenarios,
)
from openeo.rest.job import JobResults
from openeo.testing.results import assert_job_results_allclose

_log = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "scenario",
    [
        # Use scenario id as parameterization id to give nicer test names.
        pytest.param(uc, id=uc.id)
        for uc in get_benchmark_scenarios()
    ],
)
def test_run_benchmark(
    scenario: BenchmarkScenario,
    connection_factory,
    tmp_path: Path,
    track_metric,
    upload_assets_on_fail,
):
    track_metric("scenario_id", scenario.id)

    connection: openeo.Connection = connection_factory(url=scenario.backend)

    # TODO #14 scenario option to use synchronous instead of batch job mode?
    job = connection.create_job(
        process_graph=scenario.process_graph,
        title=f"APEx benchmark {scenario.id}",
        additional=scenario.job_options,
    )
    track_metric("job_id", job.job_id)

    # TODO: monitor timing and progress
    # TODO: abort excessively long batch jobs? https://github.com/Open-EO/openeo-python-client/issues/589
    job.start_and_wait()

    _collect_metrics_from_job_metadata(job=job, track_metric=track_metric)

    results = job.get_results()
    _collect_metrics_from_results_metadata(results=results, track_metric=track_metric)

    # Download actual results
    actual_dir = tmp_path / "actual"
    paths = results.download_files(target=actual_dir, include_stac_metadata=True)
    # Upload assets on failure
    upload_assets_on_fail(*paths)

    # Compare actual results with reference data
    reference_dir = download_reference_data(
        scenario=scenario, reference_dir=tmp_path / "reference"
    )
    # TODO: allow to override rtol/atol options of assert_job_results_allclose
    assert_job_results_allclose(
        actual=actual_dir, expected=reference_dir, tmp_path=tmp_path
    )


def _collect_metrics_from_job_metadata(
    job: openeo.BatchJob, track_metric: MetricsTracker
):
    # TODO move this to apex_algorithm_qa_tools for better reuse, and testability
    job_metadata = job.describe()
    track_metric("costs", job_metadata.get("costs"))
    for usage_metric, usage_data in job_metadata.get("usage", {}).items():
        if "unit" in usage_data and "value" in usage_data:
            track_metric(
                f"usage:{usage_metric}:{usage_data['unit']}", usage_data["value"]
            )


def _collect_metrics_from_results_metadata(
    results: JobResults, track_metric: MetricsTracker
):
    # TODO move this to apex_algorithm_qa_tools for better reuse, and testability
    results_metadata = results.get_metadata()
    proj_shapes = []
    for asset_name, asset_data in results_metadata.get("assets", {}).items():
        if "proj:shape" in asset_data:
            proj_shapes.append(asset_data["proj:shape"])

    if proj_shapes:
        track_metric("results:_proj_shapes", proj_shapes)
        if len(proj_shapes) > 1:
            _log.warning(f"Multiple proj:shape values: {proj_shapes}")
        # Pick first shape for now
        sy, sx = proj_shapes[0]
        area_in_pixels = sx * sy
        track_metric("results:area_in_pixels", area_in_pixels)
