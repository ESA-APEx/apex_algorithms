import jsonschema

import pytest
from apex_algorithm_qa_tools.records import (
    get_service_ogc_records,
    get_service_ogc_record_schema,
    get_platform_ogc_records,
    get_platform_ogc_record_schema,
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
