import json

import pytest
from apex_algorithm_qa_tools.common import get_project_root


@pytest.mark.parametrize(
    "path",
    [
        # Use filename as parameterization id to give nicer test names.
        pytest.param(p, id=p.name)
        for p in (get_project_root() / "openeo_udp").glob("**/*.json")
    ],
)
def test_lint_openeo_udp_json_file(path):
    data = json.loads(path.read_text())

    assert data["id"] == path.stem
    assert "description" in data
    assert "parameters" in data
    assert "process_graph" in data
    # TODO #17 more checks
    # TODO require a standardized openEO "type"? https://github.com/Open-EO/openeo-api/issues/539
