import json

import pytest
from apex_algorithm_qa_tools.common import (
    assert_no_github_feature_branch_refs,
    get_project_root,
)


def check_udp_parameters(udp: dict):
    """
    Check if the parameters of the given UDP are valid.
    """
    assert "parameters" in udp, "UDP is missing 'parameters' field"
    for param in udp["parameters"]:
        assert "name" in param, f"Parameter is missing 'name' field: {param}"
        assert "description" in param, f"Parameter is missing 'description' field: {param}"

        # The schema can either be a single key-value pair or a list of key-value pairs. If it's a list, we need to 
        # check each item in the list.
        if isinstance(param.get("schema"), list):
            for schema_item in param["schema"]:
                assert "type" in schema_item, f"Parameter schema item is missing 'type' field: {schema_item}"
        else:
            assert "schema" in param, f"Parameter is missing 'schema' field: {param}"
            assert "type" in param["schema"], f"Parameter schema is missing 'type' field: {param}"

@pytest.mark.parametrize(
    "path",
    [
        # Use filename as parameterization id to give nicer test names.
        pytest.param(p, id=p.name)
        for p in (get_project_root() / "algorithm_catalog").glob("**/openeo_udp/*.json")
    ],
)
def test_lint_openeo_udp_json_file(path):
    data = json.loads(path.read_text())

    assert data["id"] == path.stem
    assert "description" in data
    assert "parameters" in data
    assert "process_graph" in data

    for link in data.get("links", []):
        assert_no_github_feature_branch_refs(link.get("href"))

    check_udp_parameters(data)

    # TODO #17 more checks
    # TODO require a standardized openEO "type"? https://github.com/Open-EO/openeo-api/issues/539

    
