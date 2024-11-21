import json

import pytest
from apex_algorithm_qa_tools.common import (
    assert_no_github_feature_branch_refs,
    get_project_root,
)
from esa_apex_toolbox.algorithms import Algorithm


@pytest.mark.parametrize(
    "path", list((get_project_root() / "algorithm_catalog").glob("**/*.json"))
)
def test_lint_algorithm_catalog_json_file(path):
    data = json.loads(path.read_text())

    assert data["id"] == path.stem
    assert data["type"] == "Feature"
    assert (
        "http://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core"
        in data["conformsTo"]
    )

    assert "geometry" in data

    assert data["properties"]["type"] == "apex_algorithm"

    assert "openeo-process" in {k["rel"] for k in data["links"]}

    for link in data["links"]:
        assert_no_github_feature_branch_refs(link.get("href"))

    # TODO #17 more checks

    algo = Algorithm.from_ogc_api_record(path)

    assert len(algo.service_links) > 0
    assert algo.udp_link is not None
    assert algo.organization is not None
