import json
import re
from pathlib import Path

import openeo
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

cwl_url = "https://emilesonneveld.be/dropbox_proxy/work/VITO/VITO2026/BiaB/444/SDM_maxEnt_multi_STAC_tested.cwl"


def _clean_input(cwl_input: dict) -> dict:
    cwl_input = dict(cwl_input)
    cwl_type = cwl_input.get("type")
    if isinstance(cwl_type, dict) and cwl_type.get("type") == "enum":
        cwl_input["type"] = {**cwl_type, "symbols": [s.rsplit("/", 1)[-1] for s in cwl_type["symbols"]]}
    return cwl_input


def generate() -> dict:
    cwl_yaml = yaml.safe_load(load_string_from_any(cwl_url))
    cwl_inputs = get_cwl_inputs(cwl_yaml)

    # Packed CWL has a list of inputs with ids like '#main/SDM>runMaxent.yml@108|fc'.
    # Skip file/directory inputs, which can't be expressed as openEO parameters.
    inputs = {}
    context = {}
    for cwl_input in cwl_inputs:
        cwl_type = json.dumps(cwl_input.get("type"))
        if "Directory" in cwl_type or '"File"' in cwl_type or "record" in cwl_type:
            continue
        cwl_id = cwl_input["id"].removeprefix("#main/")
        name = re.sub(r"\W+", "_", cwl_id).strip("_")
        while name in inputs:
            name += "_"
        inputs[name] = _clean_input(cwl_input)
        context[cwl_id] = {"from_parameter": name}
    parameters = cwl_input_to_parameters(inputs)

    connection = openeo.connect("https://openeofed.dataspace.copernicus.eu")
    datacube = connection.datacube_from_process(
        "run_udf",
        data=None,
        udf=cwl_url,
        runtime="EOAP-CWL",
        context=context,
    )

    return build_process_dict(
        process_graph=datacube,
        process_id="max_ent",
        description=normalize_cwl_doc(get_cwl_main(cwl_yaml).get("doc")),
        parameters=parameters,
    )


if __name__ == "__main__":
    j = generate()
    write_json(j, "max_ent.json")

    udp_path = Path("../records/max_ent.json")
    if udp_path.exists():
        j_record = json.loads(udp_path.read_text())
        j_record["properties"]["description"] = j["description"]
        write_json(j_record, udp_path)
    else:
        print(f"{udp_path} not found; skipping record description update")
