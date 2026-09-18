import json
from pathlib import Path

import openeo


def generate_arguments(parameters):
    return {param["name"]: {"from_parameter": param["name"]} for param in parameters}


def generate():
    connection = openeo.connect("openeo-staging.dataspace.copernicus.eu").authenticate_oidc()

    process = connection.describe_process("force_tsa")
    process["description"] = (Path(__file__).parent / "description.md").read_text()
    process["process_graph"] = {
        "force_tsa": {
            "process_id": "force_tsa",
            "arguments": generate_arguments(process["parameters"]),
            "result": True,
        }
    }
    return process


if __name__ == "__main__":
    with open("force_tsa.json", "w") as f:
        json.dump(generate(), f, indent=2)
