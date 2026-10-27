import importlib.util
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock

import pytest

from apex_algorithm_qa_tools.benchmarks.runners.base import (
    BenchmarkJobMetadata,
    BenchmarkResults,
    BenchmarkRunnerArtifacts,
)
from apex_algorithm_qa_tools.benchmarks.runners.factory import create_benchmark_runner
from apex_algorithm_qa_tools.benchmarks.runners.openeo import OpenEOBenchmarkRunner
from apex_algorithm_qa_tools.scenarios.openeo import openEOBenchmarkScenario


@pytest.fixture
def openeo_runner(monkeypatch, tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{"value": 42}')
    scenario = openEOBenchmarkScenario(
        id="test", type="openeo", backend="https://openeo.test",
        process_graph={}, reference_data={"result.json": source.as_uri()},
    )
    request = Mock()
    request.config.getoption.return_value = None
    monkeypatch.setattr(
        "apex_algorithm_qa_tools.benchmarks.runners.openeo.create_openeo_connection",
        Mock(),
    )
    return create_benchmark_runner(scenario=scenario, request=request)


def test_openeo_runner_defaults(openeo_runner, tmp_path):
    assert isinstance(openeo_runner, OpenEOBenchmarkRunner)
    assert openeo_runner.can_check_job_results_validity() is False
    reference_dir = tmp_path / "reference"
    assert openeo_runner.download_reference(openeo_runner.scenario, reference_dir) == reference_dir
    assert (reference_dir / "result.json").read_text() == '{"value": 42}'
    with pytest.raises(NotImplementedError):
        openeo_runner.assert_job_results_validity(reference_dir, tmp_path / "actual")


@pytest.mark.parametrize("custom_validation", [False, True])
def test_benchmark_validation_routing(monkeypatch, openeo_runner, tmp_path, custom_validation):
    # Load the real benchmark entry point without collecting catalogue scenarios.
    monkeypatch.setattr("apex_algorithm_qa_tools.scenarios.get_benchmark_scenarios", lambda: [])
    path = Path(__file__).parents[2] / "benchmarks/tests/test_benchmarks.py"
    spec = importlib.util.spec_from_file_location("benchmark_entrypoint", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    runner = openeo_runner
    monkeypatch.setattr(module, "create_benchmark_runner", lambda **kwargs: runner)
    monkeypatch.setattr(runner, "create_job", Mock())
    monkeypatch.setattr(runner, "run_job", Mock())
    monkeypatch.setattr(runner, "collect_artifacts", Mock(return_value=BenchmarkRunnerArtifacts(
        job_id=None, job_metadata=BenchmarkJobMetadata(cost=None, usage=[]),
        results_metadata=BenchmarkResults(assets={}),
    )))
    monkeypatch.setattr(runner, "download_actual", Mock(return_value=[]))
    if custom_validation:
        monkeypatch.setattr(runner, "can_check_job_results_validity", lambda: True)
    validate = Mock()
    compare = Mock()
    monkeypatch.setattr(runner, "assert_job_results_validity", validate)
    monkeypatch.setattr(module, "assert_job_results_allclose", compare)

    module.test_run_benchmark(
        scenario=runner.scenario, tmp_path=tmp_path, track_metric=Mock(),
        track_phase=Mock(side_effect=lambda **kwargs: nullcontext()),
        upload_assets_on_fail=Mock(), request=runner.request,
    )

    if custom_validation:
        validate.assert_called_once_with(tmp_path / "reference", tmp_path / "actual")
        compare.assert_not_called()
    else:
        validate.assert_not_called()
        compare.assert_called_once_with(
            actual=tmp_path / "actual", expected=tmp_path / "reference",
            tmp_path=tmp_path, rtol=1e-3, atol=1, pixel_tolerance=1,
        )
