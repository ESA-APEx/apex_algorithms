import json
import yaml

import openeo
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict
from openeo.rest.stac_resource import StacResource
from openeo.internal.graph_building import PGNode

cwl_url = "https://raw.githubusercontent.com/cloudinsar/s1-workflows/refs/heads/main/cwl/sar_coherence_parallel_temporal_extent.cwl"


def get_cwl_main(cwl_yaml):
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

    if doc := cwl_input_yaml.get("doc"):
        arguments["description"] = doc

    # todo, enum values
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
        return Parameter(
            **arguments,
            schema=schema,
        )
    else:
        print(f"input_type not found: {input_type}")
        return Parameter(**arguments)


def cwl_input_to_parameters(cwl_input_yaml):
    parameters = []
    for key, value in cwl_input_yaml.items():
        parameters.append(cwl_input_to_parameter(key, value))
    return parameters


def generate():
    from urllib.request import urlopen

    cwl_yaml = yaml.safe_load(urlopen(cwl_url).read().decode('utf-8'))
    cwl_inputs = get_cwl_inputs(cwl_yaml)
    parameters = cwl_input_to_parameters(cwl_inputs)

    context = {}
    for parameter in parameters:
        context[parameter.name] = {"from_parameter": parameter.name}

    connection = openeo.connect("openeofed.dataspace.copernicus.eu").authenticate_oidc()
    stac_resource = StacResource(
        graph=PGNode(
            "run_cwl_to_stac",
            namespace=None,
            arguments={
                "cwl": cwl_url,
                "context": context,
            },
        ),
        connection=connection,
    )

    return build_process_dict(
        process_graph=stac_resource,
        process_id="sar_coherence",
        description=get_cwl_main(cwl_yaml).get("doc"),
        parameters=parameters,
    )


if __name__ == "__main__":
    with open("sar_coherence.json", "w") as f:
        json.dump(generate(), f, indent=2)
