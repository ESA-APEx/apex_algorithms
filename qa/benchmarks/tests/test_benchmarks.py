import openeo
import pytest
from apex_algorithm_qa_tools.scenarios import BenchmarkScenario, get_benchmark_scenarios


@pytest.mark.parametrize(
    "scenario",
    [
        # Use scenario id as parameterization id to give nicer test names.
        pytest.param(uc, id=uc.id)
        for uc in get_benchmark_scenarios()
    ],
)
def test_run_benchmark(scenario: BenchmarkScenario, connection_factory):
    connection: openeo.Connection = connection_factory(url=scenario.backend)

    # TODO: scenario option to use synchronous instead of batch job mode?
    job = connection.create_job(
        process_graph=scenario.process_graph,
        title=f"APEx benchmark {scenario.id}",
    )

    job.start_and_wait()

    # TODO download job results and inspect
