import pytest
from apex_algorithm_qa_tools.common import (
    assert_no_github_feature_branch_refs,
    get_project_root,
)


def test_get_project_root():
    assert get_project_root().is_dir()


@pytest.mark.parametrize(
    "href",
    [
        "https://example.com/foo/bar",
        "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/refs/heads/main/openeo_udp/examples/max_ndvi_composite/max_ndvi_composite.json",
        "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/main/openeo_udp/examples/max_ndvi_composite/max_ndvi_composite.json"
        "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/3b5a011a90f4a3050ff8fdf69ca5bc2fd1535881/openeo_udp/biopar/biopar.json",
    ],
)
def test_assert_no_github_feature_branch_refs_ok(href):
    assert_no_github_feature_branch_refs(href)


@pytest.mark.parametrize(
    ["href", "expected_error"],
    [
        (
            "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/refs/heads/footurebranch/openeo_udp/examples/max_ndvi_composite/max_ndvi_composite.json",
            "should not point to ephemeral feature branches: found 'footurebranch'",
        ),
        (
            "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/footurebranch/openeo_udp/examples/max_ndvi_composite/max_ndvi_composite.json",
            "should not point to ephemeral feature branches: found 'footurebranch'",
        ),
    ],
)
def test_assert_no_github_feature_branch_refs_not_ok(href, expected_error):
    with pytest.raises(ValueError, match=expected_error):
        assert_no_github_feature_branch_refs(href)
