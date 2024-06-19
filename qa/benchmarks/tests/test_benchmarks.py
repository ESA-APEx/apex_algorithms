import openeo
import pytest
from apex_algorithm_qa_tools.usecases import UseCase, get_use_cases


@pytest.mark.parametrize(
    "use_case", [pytest.param(uc, id=uc.id) for uc in get_use_cases()]
)
def test_run_benchmark(use_case: UseCase):
    # TODO: cache connection?
    # TODO: authentication
    connection = openeo.connect(use_case.backend)

    job = connection.create_job(
        process_graph=use_case.process_graph,
        title=f"APEx benchmark {use_case.id}",
    )

    job.start_and_wait()
