import yaml
from openeo.rest.udp import build_process_dict

from esa_apex_toolbox.algorithms import write_json
from esa_apex_toolbox.cwl_to_udp_utils import (
    cwl_input_to_parameters,
    get_cwl_inputs,
    get_cwl_main,
    load_string_from_any,
    normalize_cwl_doc,
)

if __name__ == "__main__":
    cwl_url = "https://raw.githubusercontent.com/dmastrapasqua/cwl/refs/heads/master/compute-carbon-markets-ndvi.cwl"

    cwl_yaml = yaml.safe_load(load_string_from_any(cwl_url))
    parameters = [p for p in cwl_input_to_parameters(get_cwl_inputs(cwl_yaml)) if p.name != "output_dir"]

    context = {p.name: {"from_parameter": p.name} for p in parameters}
    context["output_dir"] = "output"

    process_graph = {
        "runudf1": {
            "process_id": "run_udf",
            "arguments": {
                # keep this identical to your already-working call's arguments —
                # only swap literal values for from_parameter refs in "context"
                "udf": cwl_url,
                "runtime": "EOAP-CWL",
                "context": context,
            },
            "result": True,
        }
    }

    udp = build_process_dict(
        process_graph=process_graph,
        process_id="compute_carbon_markets_ndvi",
        summary="Computes NDVI-based vegetation health anomalies over a user-defined area and time range.",
        description=normalize_cwl_doc(
            get_cwl_main(cwl_yaml).get("doc", "Computes NDVI over a feature collection and time range.")
        ),
        parameters=parameters,
        returns={
            "description": "STAC metadata of the generated NDVI collection",
            "schema": {"type": "object", "subtype": "stac"},
        },
    )

    write_json(udp, "compute_carbon_markets_ndvi.json")
