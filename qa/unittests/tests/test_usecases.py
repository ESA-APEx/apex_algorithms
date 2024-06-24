import pytest
from apex_algorithm_qa_tools.usecases import UseCase, get_use_cases, lint_usecase


def test_get_use_cases():
    use_cases = get_use_cases()
    assert len(use_cases) > 0


# TODO: tests to check uniqueness of use case ids?


@pytest.mark.parametrize(
    "use_case",
    [
        # Use use case id as parameterization id to give nicer test names.
        pytest.param(uc, id=uc.id)
        for uc in get_use_cases()
    ],
)
def test_lint_usecase(use_case: UseCase):
    lint_usecase(use_case)
