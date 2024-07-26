from pathlib import Path

import openeo
import pytest
from apex_algorithm_qa_tools.scenarios import (
    BenchmarkScenario,
    download_reference_data,
    get_benchmark_scenarios,
)
from openeo.testing.results import assert_job_results_allclose


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
    connection: openeo.Connection = connection_factory(url=scenario.backend)

    # TODO #14 scenario option to use synchronous instead of batch job mode?
    job = connection.create_job(
        process_graph=scenario.process_graph,
        title=f"APEx benchmark {scenario.id}",
    )

    # TODO: monitor timing and progress
    # TODO: abort excessively long batch jobs? https://github.com/Open-EO/openeo-python-client/issues/589
    job.start_and_wait()

    job_metadata = job.describe()
    track_metric("costs", job_metadata.get("costs"))
    track_metric("usage", job_metadata.get("usage"))

    # Download actual results
    actual_dir = tmp_path / "actual"
    paths = job.get_results().download_files(
        target=actual_dir, include_stac_metadata=True
    )

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
