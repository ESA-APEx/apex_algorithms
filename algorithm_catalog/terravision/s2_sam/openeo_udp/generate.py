from datetime import date
import json
from pathlib import Path

import openeo
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict

def generate():
    connection = openeo.connect("openeofed.dataspace.copernicus.eu").authenticate_oidc()

    spatial_extent = Parameter.spatial_extent(
        name="spatial_extent", 
        description="Limits the data to process to the specified bounding box or polygons.\\n\\nFor raster data, the process loads the pixel into the data cube if the point at the pixel center intersects with the bounding box or any of the polygons (as defined in the Simple Features standard by the OGC).\\nFor vector data, the process loads the geometry into the data cube if the geometry is fully within the bounding box or any of the polygons (as defined in the Simple Features standard by the OGC). Empty geometries may only be in the data cube if no spatial extent has been provided.\\n\\nEmpty geometries are ignored.\\nSet this parameter to null to set no limit for the spatial extent."
        )
    
    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent", 
        description="Temporal extent specified as two-element array with start and end date/date-time."
        )


    bap_cube = connection.datacube_from_process(
            "bap_composite", 
            namespace = "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/refs/heads/main/algorithm_catalog/vito/bap_composite/openeo_udp/bap_composite.json",
            temporal_extent = temporal_extent,
            geometry= spatial_extent,
            bands = ['B01','B02','B03','B04','B05','B06','B07','B08','B8A','B09','B11','B12'],
            max_cloud_cover = 80
            )
    composite = bap_cube.aggregate_temporal_period("month","first")

    udf = openeo.UDF.from_file(
        Path(__file__).parent / "sam_udf.py",
    )
    processed_cube = composite.apply(process=udf)
    

    return build_process_dict(
        process_graph=processed_cube,
        process_id="s2_sam",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[
            spatial_extent,
            temporal_extent,
        ]
    )


if __name__ == "__main__":
    with open("s2_sam.json", "w") as f:
        json.dump(generate(), f, indent=2)