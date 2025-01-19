"""
The variability map will divide a polygon into different zones based on the pixel values
and their relative difference with the mean value of the field.
A map will be generated for each of the available S2 observation between the specified date range.

"""
import json
import sys
from pathlib import Path
from typing import Sequence, Union

import openeo
from openeo.api.process import Parameter
from openeo.processes import eq
from openeo.rest.udp import build_process_dict
from openeo.internal.graph_building import PGNode


def load_udf(filename: str) -> PGNode:
    with open(Path(__file__).parent / filename, 'r') as f:
        return f.read()

def get_variabilitymap(
    connection: openeo.Connection,
    temporal_extent: Union[Sequence[str], Parameter, None] = None,
    spatial_extent: Union[Parameter, dict, None] = None,
    raw: Union[bool, Parameter] = False,
) -> openeo.DataCube:
    
    ################ get input data #################
    s2_cube = connection.load_collection(
        collection_id="SENTINEL2_L2A",
        bands=["B03", "B04", "B08", "sunAzimuthAngles", "sunZenithAngles", "viewAzimuthMean","viewZenithMean"],
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent
    )
    scl = connection.load_collection(
        collection_id="SENTINEL2_L2A",
        bands=["SCL"],
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent
    )

    biopar_type = "FAPAR"

    mask = mask = scl.process("to_scl_dilation_mask", data=scl)
    S2_bands_mask = s2_cube.mask(mask)

    # fetch udf to reduce bands
    reduce_bands_udf = openeo.UDF(load_udf("shub_fapar_udf.py"))
    S2_bands_mask_reduced = S2_bands_mask.reduce_bands(reduce_bands_udf)

    input_data = S2_bands_mask_reduced.add_dimension(label=biopar_type, name=biopar_type, type='bands')

    ################ get and apply variability map udf #################

    mask_value = 999.0
    variabilitymap_udf = load_udf("variabilitymap_udf.py")

    udf_process = lambda data: data.run_udf(udf=variabilitymap_udf,
                                            runtime='Python', context={
            'mask_value': mask_value, 'raw': {"from_parameter": "raw"}, 'band': biopar_type
        })
    variabilitymap = input_data.apply_polygon(geometries=spatial_extent, process=udf_process, mask_value=mask_value)
    return variabilitymap


def generate() -> dict:
    connection = openeo.connect("openeofed.dataspace.copernicus.eu")

    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent", 
        description="Temporal extent specified as two-element array with start and end date/date-time. \nThis is date range for which to apply the data fusion"
        )
    spatial_extent = Parameter.spatial_extent(
        name="spatial_extent", 
        description="Limits the data to process to the specified bounding box or polygons.\\n\\nFor raster data, the process loads the pixel into the data cube if the point at the pixel center intersects with the bounding box or any of the polygons (as defined in the Simple Features standard by the OGC).\\nFor vector data, the process loads the geometry into the data cube if the geometry is fully within the bounding box or any of the polygons (as defined in the Simple Features standard by the OGC). Empty geometries may only be in the data cube if no spatial extent has been provided.\\n\\nEmpty geometries are ignored.\\nSet this parameter to null to set no limit for the spatial extent."
        )
    
    raw = Parameter.boolean(
        name="raw",
        description="Flag indicating if the yield map contains the raw differences or the result is categorized",
        default=False,
    )

    variabilitymap = get_variabilitymap(
        connection=connection,
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        raw=raw,
    )

    return build_process_dict(
        process_graph=variabilitymap,
        process_id="variabilitymap",
        summary="Daily crop performance calculation",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[
            temporal_extent,
            spatial_extent,
            raw
        ]
    )


if __name__ == "__main__":
    # save the generated process to a file
    with open(Path(__file__).parent / "variabilitymap_1901.json", "w") as f:
        json.dump(generate(), f, indent=2)