import json
from pathlib import Path
from set_path import load_set_path
from typing import Union

import openeo
from openeo import DataCube
from openeo.api.process import Parameter
from openeo.processes import ProcessBuilder, apply_neighborhood
from openeo.rest.udp import build_process_dict

from fusets.openeo import load_mogpr_udf
from fusets.openeo.services.publish_mogpr import NEIGHBORHOOD_SIZE

def get_mogpr(
        input_cube: Union[DataCube, Parameter],
) -> ProcessBuilder:
    return apply_neighborhood(input_cube,
                              lambda data: data.run_udf(udf=load_set_path()+"\n"+load_mogpr_udf(), runtime='Python', context=dict()),
                              size=[
                                  {'dimension': 'x', 'value': NEIGHBORHOOD_SIZE, 'unit': 'px'},
                                  {'dimension': 'y', 'value': NEIGHBORHOOD_SIZE, 'unit': 'px'}
                              ], overlap=[])


def generate() -> dict:
    connection = openeo.connect("openeofed.dataspace.copernicus.eu")

    # define parameters
    input_cube = Parameter.datacube(
        name="input_raster_cube",
        description="Raster cube for which to calculate the peaks and valleys"
    )

    mogpr = get_mogpr(
        input_cube=input_cube,
    )

    return build_process_dict(
        process_graph=mogpr,
        process_id="fusets_mogpr",
        summary="Integrates timeseries in data cube using multi-output gaussian process regression",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[input_cube],
        returns=None,  # TODO
        categories=None,  # TODO
    )


if __name__ == "__main__":
    # save the generated process to a file
    with open(Path(__file__).parent / "mogpr.json", "w") as f:
        json.dump(generate(), f, indent=2)
