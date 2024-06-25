import json
import sys
from pathlib import Path

import openeo
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict

# TODO: where to put reusable helpers? e.g. load description from README.md, dummy openeo connection, properly write to JSON file, ...


def generate() -> dict:
    # TODO: use/inject dummy connection instead of concrete one? (See cdse_marketplace_services)
    connection = openeo.connect("openeofed.dataspace.copernicus.eu")

    spatial_extent = Parameter.bounding_box(name="bbox")
    temporal_extent = Parameter.temporal_interval(name="temporal_extent")

    cube = connection.load_collection(
        "SENTINEL2_L2A",
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        bands=["B04", "B08"],
    )

    b04 = cube.band("B04")
    b08 = cube.band("B08")
    ndvi = (b08 - b04) / (b08 + b04)
    max_ndvi = ndvi.reduce_dimension(dimension="t", reducer="max")

    return build_process_dict(
        process_graph=max_ndvi,
        process_id="max_ndvi",
        summary="TODO",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[
            spatial_extent,
            temporal_extent,
        ],
        returns=None,  # TODO
        categories=None,  # TODO
    )


if __name__ == "__main__":
    # TODO: how to enforce a useful order of top-level keys?
    json.dump(generate(), sys.stdout, indent=2)
