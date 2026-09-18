import json
from pathlib import Path

import openeo


def generate_arguments(parameters):
    return {param["name"]: {"from_parameter": param["name"]} for param in parameters}


def generate():
    connection = openeo.connect("openeo-staging.dataspace.copernicus.eu").authenticate_oidc()

    process = connection.describe_process("force_level2")
    process["description"] = (Path(__file__).parent / "description.md").read_text()
    process["process_graph"] = {
        "force_level_2": {
            "process_id": "force_level_2",
            "arguments": generate_arguments(process["parameters"]),
            "result": True,
        }
    }
    return process


if __name__ == "__main__":
    with open("force_level2.json", "w") as f:
        json.dump(generate(), f, indent=2)
