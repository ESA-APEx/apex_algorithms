import jsonschema
import requests

import pytest
from apex_algorithm_qa_tools.common import get_project_root
from pathlib import Path
from apex_algorithm_qa_tools.records import (
    get_service_ogc_records,
    get_service_ogc_record_schema,
    get_platform_ogc_records,
    get_platform_ogc_record_schema,
    get_provider_ogc_records,
    get_provider_ogc_record_schema,
)


def test_get_service_ogc_records():
    records = get_service_ogc_records()
    assert len(records) > 0


def test_get_platform_ogc_records():
    records = get_platform_ogc_records()
    assert len(records) > 0


# TODO: tests to check uniqueness of records ids?


@pytest.mark.parametrize(
    "record",
    [
        # Use scenario id as parameterization id to give nicer test names.
        pytest.param(record, id=record["data"]["id"])
        for record in get_service_ogc_records()
    ],
)
def test_service_record_validation(record):
    ## Validate if record file is located at the expected path '*/{record['data']['id']}/records/{record['data']['id']}.json'
    assert record["path"].endswith(f"{record["data"]["id"]}/records/{record['data']['id']}.json"), f"Record file is not located at the expected path '*/{record['data']['id']}/records/{record['data']['id']}.json'"
    
    ## Validate record against the service OGC record schema.
    jsonschema.validate(instance=record["data"], schema=get_service_ogc_record_schema())

    ## Validate if the links in the record is returning a 200 OK response.
    for link in record["data"].get("links", []):
        assert "href" in link, f"Link in record '{record['data']['id']}' is missing 'href' field"
        href = link["href"]
        if href.startswith("http"):
            response = requests.head(href)
            assert response.status_code in [200, 301, 302, 308, 401, 403], f"Link '{href}' in record '{record['data']['id']}' is not returning a valid response (200, 301, 302, 308, 401, 403), got {response.status_code}"


@pytest.mark.parametrize(
    "record",
    [
        # Use scenario id as parameterization id to give nicer test names.
        pytest.param(record, id=record["data"]["id"])
        for record in get_platform_ogc_records()
    ],
)
def test_platform_record_validation(record):
    record_name = Path(record["path"]).name
    assert record_name == f"{record['data']['id']}.json", f"Record file name '{record_name}' does not match record id '{record['data']['id']}'"
    jsonschema.validate(instance=record["data"], schema=get_platform_ogc_record_schema())


def test_algorithm_provider_records_():
    # Test that there is at least one provider record based on the folder structure in the algorithm_repo directory.
    # For each subfolder in the `algorithm_catalog` folder, there should be exactly one provider record with a matching `record.json`.
    algorithm_catalog_dir: Path = get_project_root() / "algorithm_catalog"
    subdirs = [p.name for p in algorithm_catalog_dir.iterdir() if p.is_dir()]
    assert len(subdirs) > 0, "No subfolders found under algorithm_catalog"

    for subdir in subdirs:
        assert (algorithm_catalog_dir / subdir / "record.json").exists(), f"Missing record.json for provider '{subdir}'"


@pytest.mark.parametrize(
    "record",
    [
        # Use scenario id as parameterization id to give nicer test names.
        pytest.param(record, id=record["data"]["id"])
        for record in get_provider_ogc_records()
    ],
)
def test_provider_record_validation(record):
    jsonschema.validate(instance=record["data"], schema=get_provider_ogc_record_schema())
