import jsonschema

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
        pytest.param(record, id=record["id"])
        for record in get_service_ogc_records()
    ],
)
def test_service_record_validation(record):
    jsonschema.validate(instance=record, schema=get_service_ogc_record_schema())


@pytest.mark.parametrize(
    "record",
    [
        # Use scenario id as parameterization id to give nicer test names.
        pytest.param(record, id=record["id"])
        for record in get_platform_ogc_records()
    ],
)
def test_platform_record_validation(record):
    jsonschema.validate(instance=record, schema=get_platform_ogc_record_schema())


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
        pytest.param(record, id=record["id"])
        for record in get_provider_ogc_records()
    ],
)
def test_provider_record_validation(record):
    jsonschema.validate(instance=record, schema=get_provider_ogc_record_schema())
