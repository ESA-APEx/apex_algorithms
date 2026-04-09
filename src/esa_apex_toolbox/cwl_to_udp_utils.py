from pathlib import Path

import requests
import yaml

import openeo
from openeo.api.process import Parameter


def load_string_from_any(content: str) -> str:
    # noinspection HttpUrlsUsage
    if content.lower().startswith("http://") or content.lower().startswith("https://"):
        resp = requests.get(content)
        resp.raise_for_status()
        return resp.text
    elif (
            content.lower().endswith(".cwl")
            or content.lower().endswith(".yaml")
            and not "\n" in content
            and not content.startswith("{")
    ):

        with Path(content).open(mode="r", encoding="utf-8") as f:
            return f.read()
    else:
        return content


def get_cwl_main(cwl_yaml):
    if isinstance(cwl_yaml, str):
        cwl_yaml = yaml.safe_load(cwl_yaml)
    cwl_graph = cwl_yaml.get("$graph", None)
    if cwl_graph is None:
        return cwl_yaml
    else:
        return next((item for item in cwl_graph if item.get("id") == "main"), None)


def get_cwl_inputs(cwl_yaml):
    return get_cwl_main(cwl_yaml).get("inputs", [])


def cwl_input_to_parameter(name, cwl_input_yaml):
    """
    Convert to Parameter object that openEO can use.
    Not all properties are converted. For example enum values are not.
    """
    if isinstance(cwl_input_yaml, list) and len(cwl_input_yaml) > 0:
        cwl_input_yaml = cwl_input_yaml[0]
    assert isinstance(cwl_input_yaml, dict)
    input_type = cwl_input_yaml.get("type")
    arguments = {"name": name}
    if isinstance(input_type, dict):
        input_type = cwl_input_yaml.get("type").get("type")

    if input_type.endswith("?"):
        input_type = input_type[:-1]
        arguments["optional"] = True

    if default := cwl_input_yaml.get("default"):
        arguments["default"] = default
    elif arguments.get("optional"):
        arguments["default"] = None

    if doc := cwl_input_yaml.get("doc"):
        arguments["description"] = str(doc).rstrip()

    if name == "spatial_extent":
        return Parameter.spatial_extent(**arguments)
    if name == "temporal_extent":
        return Parameter.temporal_interval(**arguments)
    elif input_type == "string":
        return Parameter.string(**arguments)
    elif input_type == "int":
        return Parameter.integer(**arguments)
    elif input_type == "enum":
        schema = {"type": "string"}
        if symbols := cwl_input_yaml.get("symbols"):
            schema["enum"] = symbols
        elif symbols := cwl_input_yaml.get("type", {}).get("symbols"):
            schema["enum"] = symbols
        return Parameter(
            **arguments,
            schema=schema,
        )
    else:
        print(f"input_type not found for {name}: {input_type}")
        return Parameter(**arguments)


def cwl_input_to_parameters(cwl_input_yaml):
    parameters = []
    for key, value in cwl_input_yaml.items():
        parameters.append(cwl_input_to_parameter(key, value))
    return parameters
