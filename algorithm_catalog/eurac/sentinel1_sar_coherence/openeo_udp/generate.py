import json
from pathlib import Path

import openeo
import yaml
from openeo.api.process import Parameter
from openeo.internal.graph_building import PGNode
from openeo.rest.stac_resource import StacResource
from openeo.rest.udp import build_process_dict

from esa_apex_toolbox.cwl_to_udp_utils import (
    get_cwl_main,
    get_cwl_inputs,
    cwl_input_to_parameters,
    load_string_from_any,
)

cwl_url = "https://raw.githubusercontent.com/cloudinsar/s1-workflows/refs/heads/main/cwl/sar_coherence_parallel_temporal_extent.cwl"
# cwl_url = "/home/emile/openeo/s1-workflows/cwl/sar_coherence_parallel_temporal_extent.cwl"


def generate() -> dict:
    from urllib.request import urlopen

    cwl_yaml = yaml.safe_load(load_string_from_any(cwl_url))
    cwl_inputs = get_cwl_inputs(cwl_yaml)
    parameters = cwl_input_to_parameters(cwl_inputs)

    context = {}
    for parameter in parameters:
        context[parameter.name] = {"from_parameter": parameter.name}

    connection = openeo.connect("openeofed.dataspace.copernicus.eu").authenticate_oidc()
    # TODO: Use run_cwl_to_stac once https://github.com/cloudinsar/s1-workflows/issues/80 is deployed
    # datacube = StacResource(
    #     graph=PGNode(
    #         "run_cwl_to_stac",
    #         namespace=None,
    #         arguments={
    #             "cwl": cwl_url,
    #             "context": context,
    #         },
    #     ),
    #     connection=connection,
    # )
    datacube = connection.datacube_from_process(
        "run_udf",
        data=None,
        udf=cwl_url,
        runtime="EOAP-CWL",
        context=context,
    )

    return build_process_dict(
        process_graph=datacube,
        process_id="sentinel1_sar_coherence",
        description=get_cwl_main(cwl_yaml).get("doc"),
        parameters=parameters,
    )


if __name__ == "__main__":
    j = generate()
    with open("sentinel1_sar_coherence.json", "w") as f:
        json.dump(j, f, indent=2)

    j_record = json.loads(Path("../records/sentinel1_sar_coherence.json").read_text())
    j_record["properties"]["description"] = j["description"]
    with open(Path("../records/sentinel1_sar_coherence.json"), "w") as f:
        json.dump(j_record, f, indent=2)
