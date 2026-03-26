import json
from pathlib import Path
import yaml

import openeo
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict
from openeo.rest.stac_resource import StacResource
from openeo.internal.graph_building import PGNode

cwl_url = "https://raw.githubusercontent.com/cloudinsar/s1-workflows/refs/heads/main/cwl/sar_coherence_parallel_temporal_extent.cwl"


def get_cwl_inputs(cwl_yaml):
    cwl_graph = cwl_yaml.get("$graph", [])
    cwl_main = next((item for item in cwl_graph if item.get("id") == "main"), None)
    return cwl_main.get("inputs", [])


def cwl_input_to_parameter(name, cwl_input_yaml):
    input_type = cwl_input_yaml.get("type")
    arguments = {"name": name}
    if input_type.endswith("?"):
        input_type = input_type[:-1]
        arguments["optional"] = True

    if default := cwl_input_yaml.get("default"):
        arguments["default"] = default

    if doc := cwl_input_yaml.get("doc"):
        arguments["description"] = doc

    # todo, enum
    if name == "sub_swath":
        return Parameter(
            schema={"type": "string", "enum": ["IW1", "IW2", "IW3", "EW1", "EW2", "EW3", "EW4", "EW5"]},
            **arguments,
        )
    if name == "polarization":
        return Parameter(
            schema={"type": "string", "enum": ["VV", "VH", "HH", "HV"]},
            **arguments,
        )
    if name == "spatial_extent":
        return Parameter.spatial_extent(**arguments)
    if name == "temporal_extent":
        return Parameter.temporal_interval(**arguments)
    elif input_type == "string":
        return Parameter.string(**arguments)
    elif input_type == "int":
        return Parameter.integer(**arguments)
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
        description=cwl_yaml.get("doc"),
        parameters=parameters,
    )


if __name__ == "__main__":
    with open("sar_coherence.json", "w") as f:
        json.dump(generate(), f, indent=2)
