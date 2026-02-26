import json
from pathlib import Path

import openeo
from openeo.api.process import Parameter
from openeo.rest._datacube import THIS
from openeo.rest.udp import build_process_dict

def generate():
    connection = openeo.connect("https://openeo.eodc.eu/openeo/1.2.0/").authenticate_oidc()

    spatial_extent = Parameter.spatial_extent(
        name="spatial_extent", 
        description="Limits the data to process to the specified bounding box or polygons.\\n\\nFor raster data, the process loads the pixel into the data cube if the point at the pixel center intersects with the bounding box or any of the polygons (as defined in the Simple Features standard by the OGC).\\nFor vector data, the process loads the geometry into the data cube if the geometry is fully within the bounding box or any of the polygons (as defined in the Simple Features standard by the OGC). Empty geometries may only be in the data cube if no spatial extent has been provided.\\n\\nEmpty geometries are ignored.\\nSet this parameter to null to set no limit for the spatial extent."
        )
    
    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent", 
        description="Temporal extent specified as two-element array with start and end date/date-time."
        )

    schema = {
        "type": "string",
        "enum": ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"],
    }
    bands = Parameter.array(
        name="bands",
        description="Sentinel-2 bands to include in the composite.",
        item_schema=schema,
        default=["B04", "B03", "B02"],
        optional=True,
    )

    collection = 'SENTINEL2_L2A'

    s2_l1c = connection.load_collection(
        collection,
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        bands=bands)

    sen2like = s2_l1c.process('sen2like', {
        'data': THIS,
        'target_product': 'L2F',
        'export_original_files': True,
        'cloud_cover': 50})

    returns = {
        "description": "A data cube with the newly computed values.\n\nThe result will combine Sentinel-2 and Landsat timesteps for the requested extent. Just like Sentinel 2 data, sen2like generates .SAFE output files, which are zipped for the purpose of openEO. For both Landsat and Sentinel acquisitions the .SAFE files include the requested bands. Note, that the sen2like Landsat outputs do not include equivalents of Sentinel-2 bands B05, B06, B07.",
        "schema": {
            "type": "object",
            "subtype": "datacube"
        }
    }

    return build_process_dict(
        process_graph=sen2like,
        process_id="sen2like",
        summary="Computes a harmonzed Sentinel-2 and Landsat timeseries.",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[
            spatial_extent,
            temporal_extent
        ],
        returns=returns,
        categories=["sentinel-2", "ARD"]
    )


if __name__ == "__main__":
    with open("sen2like.json", "w") as f:
        json.dump(generate(), f, indent=2)