from pathlib import Path
from typing import Any, Union, List

import requests
import yaml

import openeo
from openeo.api.process import Parameter


def load_string_from_any(content: Union[str, Path]) -> str:
    if isinstance(content, Path):
        with open(content, "r") as f:
            return f.read()

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


def cwl_input_to_parameter(name: str, cwl_input_yaml: Any) -> Parameter:
    """
    Convert to Parameter object that openEO can use.
    Not all properties are converted. For example enum values are not.
    """
    if isinstance(cwl_input_yaml, list) and len(cwl_input_yaml) > 0:
        # Not sure why this construction is possible, but needs to be supported
        cwl_input_yaml = cwl_input_yaml[0]
        input_type = cwl_input_yaml
    else:
        input_type = cwl_input_yaml.get("type")

    assert isinstance(cwl_input_yaml, dict)
    arguments: dict[str, Any] = {"name": name}

    if default := cwl_input_yaml.get("default"):
        arguments["default"] = default
    elif arguments.get("optional"):
        arguments["default"] = None

    if doc := cwl_input_yaml.get("doc"):
        arguments["description"] = str(doc).rstrip()

    def cwl_type_to_openeo_param(cwl_type: Any) -> Parameter:
        if isinstance(cwl_type, str) and cwl_type.endswith("?"):
            cwl_type = cwl_type[:-1]
            arguments["optional"] = True  # Hack
            if not "default" in arguments:
                arguments["default"] = None

        if isinstance(cwl_type, str) and cwl_type.endswith("[]"):
            # Make sure array is always in the same complex form when parsing.
            sub_type = cwl_type[:-2]
            cwl_type = {"type": "array", "items": sub_type}

        if name == "spatial_extent":
            return Parameter.spatial_extent(**arguments)
        if name == "temporal_extent":
            return Parameter.temporal_interval(**arguments)
        elif cwl_type == "string":
            return Parameter.string(**arguments)
        elif cwl_type == "int":
            return Parameter.integer(**arguments)
        elif isinstance(cwl_type, dict) and cwl_type.get("type") == "array":
            schema = {"type": "array", "items": None}
            if input_items := cwl_type.get("items"):
                sub_parameter = cwl_type_to_openeo_param(input_items)
                sub_schema = sub_parameter.schema
                schema["items"] = sub_schema
            return Parameter(
                **arguments,
                schema=schema,
            )
        elif isinstance(cwl_type, dict) and cwl_type.get("type") == "enum":
            schema = {"type": "string"}
            if symbols := cwl_type.get("symbols"):
                schema["enum"] = symbols
            elif symbols := cwl_type.get("type", {}).get("symbols"):
                schema["enum"] = symbols
            return Parameter(
                **arguments,
                schema=schema,
            )
        else:
            print(f"Type not found for {name}: {cwl_type}")
            return Parameter(**arguments)

    return cwl_type_to_openeo_param(input_type)


def cwl_input_to_parameters(cwl_input_yaml) -> List[Parameter]:
    parameters = []
    for key, value in cwl_input_yaml.items():
        parameters.append(cwl_input_to_parameter(key, value))
    return parameters
