from typing import Union, Sequence
import json
from pathlib import Path

import openeo
from set_path import load_set_path
from fusets.openeo import load_mogpr_udf
from fusets.openeo.services.publish_mogpr import NEIGHBORHOOD_SIZE
from openeo.api.process import Parameter
from openeo.processes import ProcessBuilder, apply_neighborhood, merge_cubes
from openeo.rest.udp import build_process_dict

from data_loading import load_s1_collection, load_s2_collection

S1_COLLECTIONS = ['RVI', 'GRD']
S2_COLLECTIONS = ['NDVI', 'FAPAR', 'LAI', 'FCOVER', 'EVI', 'CCC', 'CWC']


def get_mogpr_s1_s2(
        connection,
        spatial_extent: Union[Parameter, dict] = None,
        temporal_extent: Union[Sequence[str], Parameter] = None,
        s1_collection: Union[str, Parameter] = S1_COLLECTIONS[0],
        s2_collection: Union[str, Parameter] = S2_COLLECTIONS[0],
) -> ProcessBuilder:
    # Build the S1 and S2 input data cubes
    s1_input_cube = load_s1_collection(connection, s1_collection, spatial_extent, temporal_extent)
    s2_input_cube = load_s2_collection(connection, s2_collection, spatial_extent, temporal_extent)

    # Merge the inputs to a single datacube
    merged_cube = merge_cubes(s1_input_cube, s2_input_cube)

    # Apply the MOGPR UDF to the multi source datacube
    return apply_neighborhood(merged_cube,
                              lambda data: data.run_udf(udf=load_set_path()+"\n"+load_mogpr_udf(), runtime='Python', context=dict()),
                              size=[
                                  {'dimension': 'x', 'value': NEIGHBORHOOD_SIZE, 'unit': 'px'},
                                  {'dimension': 'y', 'value': NEIGHBORHOOD_SIZE, 'unit': 'px'}
                              ], overlap=[])


def generate() -> dict:
    connection = openeo.connect("openeofed.dataspace.copernicus.eu")
    spatial_extent = Parameter.spatial_extent(
        name="spatial_extent", 
        description="Limits the data to process to the specified bounding box or polygons.\\n\\nFor raster data, the process loads the pixel into the data cube if the point at the pixel center intersects with the bounding box or any of the polygons (as defined in the Simple Features standard by the OGC).\\nFor vector data, the process loads the geometry into the data cube if the geometry is fully within the bounding box or any of the polygons (as defined in the Simple Features standard by the OGC). Empty geometries may only be in the data cube if no spatial extent has been provided.\\n\\nEmpty geometries are ignored.\\nSet this parameter to null to set no limit for the spatial extent."
        )
    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent", 
        description="Temporal extent specified as two-element array with start and end date/date-time. \nThis is date range for which to apply the data fusion"
        )
    s1_collection = Parameter.string(
        name="s1_collection", 
        description="S1 data collection to use for fusing the data",
        default=S1_COLLECTIONS[0], 
        values=[S1_COLLECTIONS[0], S1_COLLECTIONS[1]]
    )
    s2_collection = Parameter.string(
        name="s2_collection", 
        description="S2 data collection to use for fusing the data",
        default=S2_COLLECTIONS[0], 
        values=['NDVI', 'FAPAR', 'LAI', 'FCOVER', 'EVI', 'CCC', 'CWC']
    )

    mogpr_s1_s2 = get_mogpr_s1_s2(
        connection=connection,
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        s1_collection=s1_collection,
        s2_collection=s2_collection
    )

    return build_process_dict(
        process_graph=mogpr_s1_s2,
        process_id="mogpr_s1_s2_130125",
        summary="Integrate S1 and S2 timeseries using multi-output gaussian process regression",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[
            spatial_extent,
            temporal_extent,
            s1_collection,
            s2_collection
        ]
    )


if __name__ == "__main__":
    with open(Path(__file__).parent / "fusets_mogpr_s1s2.json", "w") as f:
        json.dump(generate(), f, indent=2)