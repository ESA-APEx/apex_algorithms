from apex_algorithm_qa_tools.usecases import (
    get_algorithm_invocation_root,
    get_use_cases,
)


def test_get_algorithm_invocation_root():
    assert get_algorithm_invocation_root().is_dir()


def test_get_use_cases():
    use_cases = get_use_cases()
    assert len(use_cases) > 0


# TODO: tests to check uniqueness of use case ids?
