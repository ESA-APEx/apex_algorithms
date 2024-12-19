import logging
from pathlib import Path

import openeo
import pytest
from apex_algorithm_qa_tools.benchmarks import (
    collect_metrics_from_job_metadata,
    collect_metrics_from_results_metadata,
)
from apex_algorithm_qa_tools.scenarios import (
    BenchmarkScenario,
    download_reference_data,
    get_benchmark_scenarios,
)
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
    request
):
    track_metric("scenario_id", scenario.id)
    # Check if a backend override has been provided via cli options.
    override_backend = request.config.getoption("--override-backend")
    backend = scenario.backend
    if override_backend:
        _log.info(f"Overriding backend URL with {override_backend!r}")
        backend = override_backend

    connection: openeo.Connection = connection_factory(url=backend)

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

    collect_metrics_from_job_metadata(job, track_metric=track_metric)

    results = job.get_results()
    collect_metrics_from_results_metadata(results, track_metric=track_metric)

    # Download actual results
    actual_dir = tmp_path / "actual"
    paths = results.download_files(target=actual_dir, include_stac_metadata=True)
    # Upload assets on failure
    upload_assets_on_fail(*paths)

    # Compare actual results with reference data
    reference_dir = download_reference_data(
        scenario=scenario, reference_dir=tmp_path / "reference"
    )
    assert_job_results_allclose(
        actual=actual_dir,
        expected=reference_dir,
        tmp_path=tmp_path,
        rtol=scenario.reference_options.get("rtol", 1e-6),
        atol=scenario.reference_options.get("atol", 1e-6),
    )
