import pytest

pytest_plugins = [
    "pytester",
]

pytest.register_assert_rewrite("apex_algorithm_qa_tools.scenarios")
