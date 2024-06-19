from apex_algorithm_qa_tools.usecases import get_use_cases


def test_get_use_cases():
    use_cases = get_use_cases()
    assert len(use_cases) > 0
