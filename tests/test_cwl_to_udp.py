from pathlib import Path

import yaml
from jsonschema import Draft7Validator

from esa_apex_toolbox.cwl_to_udp_utils import (
    get_cwl_inputs,
    cwl_input_to_parameters,
    load_string_from_any,
)

DATA_ROOT = Path(__file__).parent / "data"


def test_cwl_to_udp_hello_world():
    path = DATA_ROOT / "hello_world.cwl"
    cwl_yaml = yaml.safe_load(load_string_from_any(path))
    cwl_inputs = get_cwl_inputs(cwl_yaml)
    parameters = cwl_input_to_parameters(cwl_inputs)
    assert parameters[0].schema == {'type': 'string'}
    Draft7Validator.check_schema(parameters[0].schema)


def test_cwl_to_udp_array_inputs():
    path = DATA_ROOT / "array-inputs.cwl"
    cwl_yaml = yaml.safe_load(load_string_from_any(path))
    cwl_inputs = get_cwl_inputs(cwl_yaml)
    parameters = cwl_input_to_parameters(cwl_inputs)
    for parameter in parameters:
        print(parameter.schema)
        Draft7Validator.check_schema(parameter.schema)
        assert parameter.schema == {'type': 'array', 'items': {'type': 'string'}}
