import json
from pathlib import Path

import openeo
from openeo.api.process import Parameter
from openeo.rest._datacube import THIS
from openeo.rest.udp import build_process_dict

def generate():
    connection = openeo.connect("openeo.cloud").authenticate_oidc()

    spatial_extent = Parameter.spatial_extent(
        name="spatial_extent", 
        description="Limits the data to process to the specified bounding box or polygons.\\n\\nFor raster data, the process loads the pixel into the data cube if the point at the pixel center intersects with the bounding box or any of the polygons (as defined in the Simple Features standard by the OGC).\\nFor vector data, the process loads the geometry into the data cube if the geometry is fully within the bounding box or any of the polygons (as defined in the Simple Features standard by the OGC). Empty geometries may only be in the data cube if no spatial extent has been provided.\\n\\nEmpty geometries are ignored.\\nSet this parameter to null to set no limit for the spatial extent."
        )
    
    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent", 
        description="Temporal extent specified as two-element array with start and end date/date-time."
        )

    collection = 'SENTINEL2_L1C'
    bands = ["B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"]

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
        "description": "A data cube with the newly computed values.\n\nAll dimensions stay the same, except for the dimensions specified in corresponding parameters. There are three cases how the dimensions can change:\n\n1. The source dimension is the target dimension:\n   - The (number of) dimensions remain unchanged as the source dimension is the target dimension.\n   - The source dimension properties name and type remain unchanged.\n   - The dimension labels, the reference system and the resolution are preserved only if the number of values in the source dimension is equal to the number of values computed by the process. Otherwise, all other dimension properties change as defined in the list below.\n2. The source dimension is not the target dimension. The target dimension exists with a single label only:\n   - The number of dimensions decreases by one as the source dimension is 'dropped' and the target dimension is filled with the processed data that originates from the source dimension.\n   - The target dimension properties name and type remain unchanged. All other dimension properties change as defined in the list below.\n3. The source dimension is not the target dimension and the latter does not exist:\n   - The number of dimensions remain unchanged, but the source dimension is replaced with the target dimension.\n   - The target dimension has the specified name and the type other. All other dimension properties are set as defined in the list below.\n\nUnless otherwise stated above, for the given (target) dimension the following applies:\n\n- the number of dimension labels is equal to the number of values computed by the process,\n- the dimension labels are incrementing integers starting from zero,\n- the resolution changes, and\n- the reference system is undefined.",
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