from apex_algorithm_qa_tools.common import get_project_root


def test_get_project_root():
    assert get_project_root().is_dir()
