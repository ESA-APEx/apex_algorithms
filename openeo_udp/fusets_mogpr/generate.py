import json
from pathlib import Path
from typing import Union

from openeo import DataCube
from openeo.api.process import Parameter
from openeo.processes import ProcessBuilder, apply_neighborhood
from openeo.rest.udp import build_process_dict

from fusets.openeo import load_mogpr_udf


def get_mogpr(
        input_cube: Union[DataCube, Parameter],
) -> ProcessBuilder:
    return apply_neighborhood(input_cube,
                              lambda data: data.run_udf(udf=Path("set_path.py").read_text()+"\n"+load_mogpr_udf(), runtime='Python', context=dict()),
                              size=[
                                  {'dimension': 'x', 'value': 32, 'unit': 'px'},
                                  {'dimension': 'y', 'value': 32, 'unit': 'px'}
                              ], overlap=[])


def generate() -> dict:
    # define parameters
    input_cube = Parameter.datacube(
        name="data",
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
    with open(Path(__file__).parent / "fusets_mogpr.json", "w") as f:
        json.dump(generate(), f, indent=2)
