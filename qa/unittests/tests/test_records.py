import jsonschema

import pytest
from apex_algorithm_qa_tools.records import get_ogc_records, _get_ogc_record_schema


def test_get_ogc_records():
    records = get_ogc_records()
    assert len(records) > 0


# TODO: tests to check uniqueness of records ids?


@pytest.mark.parametrize(
    "record",
    [
        # Use scenario id as parameterization id to give nicer test names.
        pytest.param(record, id=record['id'])
        for record in get_ogc_records()
    ],
)
def test_record_validation(record):
    jsonschema.validate(instance=record, schema=_get_ogc_record_schema())
