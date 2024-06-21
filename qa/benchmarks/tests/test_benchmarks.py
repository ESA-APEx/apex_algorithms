import openeo
import pytest
from apex_algorithm_qa_tools.usecases import UseCase, get_use_cases


@pytest.mark.parametrize(
    "use_case",
    [
        # Use use case id as parameterization id to give nicer test names.
        pytest.param(uc, id=uc.id)
        for uc in get_use_cases()
    ],
)
def test_run_benchmark(use_case: UseCase, connection_factory):
    connection: openeo.Connection = connection_factory(url=use_case.backend)

    # TODO: scenario option to use synchronous instead of batch job mode?
    job = connection.create_job(
        process_graph=use_case.process_graph,
        title=f"APEx benchmark {use_case.id}",
    )

    job.start_and_wait()

    # TODO download job results and inspect
