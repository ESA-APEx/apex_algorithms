import logging
import re
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
    track_phase,
    upload_assets_on_fail,
    request,
):
    track_metric("scenario_id", scenario.id)

    with track_phase(phase="connect"):
        # Check if a backend override has been provided via cli options.
        override_backend = request.config.getoption("--override-backend")
        backend_filter = request.config.getoption("--backend-filter")
        if backend_filter and not re.match(backend_filter, scenario.backend):
            # TODO apply filter during scenario retrieval, but seems to be hard to retrieve cli param
            pytest.skip(
                f"skipping scenario {scenario.id} because backend {scenario.backend} does not match filter {backend_filter!r}"
            )
        backend = scenario.backend
        if override_backend:
            _log.info(f"Overriding backend URL with {override_backend!r}")
            backend = override_backend

        connection: openeo.Connection = connection_factory(url=backend)

    with track_phase(phase="create-job"):
        # TODO #14 scenario option to use synchronous instead of batch job mode?
        job = connection.create_job(
            process_graph=scenario.process_graph,
            title=f"APEx benchmark {scenario.id}",
            additional=scenario.job_options,
        )
        track_metric("job_id", job.job_id)

    with track_phase(phase="run-job"):
        # TODO: monitor timing and progress
        # TODO: abort excessively long batch jobs? https://github.com/Open-EO/openeo-python-client/issues/589
        job.start_and_wait()
        # TODO: separate "job started" and run phases?

    with track_phase(phase="collect-metadata"):
        collect_metrics_from_job_metadata(job, track_metric=track_metric)

        results = job.get_results()
        collect_metrics_from_results_metadata(results, track_metric=track_metric)

    with track_phase(phase="download-actual"):
        # Download actual results
        actual_dir = tmp_path / "actual"
        paths = results.download_files(target=actual_dir, include_stac_metadata=True)

        # Upload assets on failure
        upload_assets_on_fail(*paths)

    with track_phase(phase="download-reference"):
        reference_dir = download_reference_data(
            scenario=scenario, reference_dir=tmp_path / "reference"
        )

    with track_phase(phase="compare"):
        # Compare actual results with reference data
        assert_job_results_allclose(
            actual=actual_dir,
            expected=reference_dir,
            tmp_path=tmp_path,
            rtol=scenario.reference_options.get("rtol", 1e-6),
            atol=scenario.reference_options.get("atol", 1e-6),
            pixel_tolerance=scenario.reference_options.get("pixel_tolerance", 0.0),
        )
