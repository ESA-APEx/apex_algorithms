import json
from pathlib import Path

import openeo
import yaml
from openeo.api.process import Parameter
from openeo.internal.graph_building import PGNode
from openeo.rest.stac_resource import StacResource
from openeo.rest.udp import build_process_dict

from esa_apex_toolbox.algorithms import write_json
from esa_apex_toolbox.cwl_to_udp_utils import (
    get_cwl_main,
    get_cwl_inputs,
    cwl_input_to_parameters,
    load_string_from_any,
)

cwl_url = "https://raw.githubusercontent.com/cloudinsar/s1-workflows/refs/heads/main/cwl/sar_interferogram.cwl"
# cwl_url = "/home/emile/openeo/s1-workflows/cwl/sar_interferogram.cwl"


def generate() -> dict:
    cwl_yaml = yaml.safe_load(load_string_from_any(cwl_url))
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
        process_id="sentinel1_sar_interferogram",
        description=get_cwl_main(cwl_yaml).get("doc"),
        parameters=parameters,
    )


if __name__ == "__main__":
    j = generate()
    write_json(j, "sentinel1_sar_interferogram.json")

    udp_path = Path("../records/sentinel1_sar_interferogram.json")
    j_record = json.loads(udp_path.read_text())
    j_record["properties"]["description"] = j["description"]
    write_json(j_record, udp_path)
