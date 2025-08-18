from pathlib import Path

import pytest

pytest_plugins = [
    "pytester",
]

pytest.register_assert_rewrite("apex_algorithm_qa_tools.scenarios")


@pytest.fixture
def test_data_root() -> Path:
    """Fixture to provide the root path for test data."""
    return Path(__file__).parent / "data"
