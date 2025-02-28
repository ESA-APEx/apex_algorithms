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
    biopar_type = Parameter.string(
        name="biopar_type",
        description="BIOPAR type [FAPAR,LAI,FCOVER,CCC,CWC]",
        default="FAPAR",
        values=["FAPAR", "LAI", "FCOVER", "CCC", "CWC"],
    )

    cube = connection.load_collection(
        collection_id="SENTINEL2_L2A",
        bands=[
        "B03",
        "B04",
        "B08",
        "sunAzimuthAngles",
        "sunZenithAngles",
        "viewAzimuthMean",
        "viewZenithMean"
        ],
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
    )
    scl = connection.load_collection(
        collection_id="SENTINEL2_L2A",
        bands=["SCL"],
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
    )

    mask = scl.process("to_scl_dilation_mask", data=scl)
    cube = cube.mask(mask)

    udf = openeo.UDF.from_file(
        Path(__file__).parent / "biopar_udf.py",
        runtime="Python",
        context={"biopar_type": {"from_parameter": "biopar_type"}},
    )
    # print(udf)
    biopar = cube.reduce_dimension(
        dimension="bands",
        reducer=udf,
    )
    biopar = biopar.add_dimension("bands", label=biopar_type, type="bands")
    

    return build_process_dict(
        process_graph=biopar,
        process_id="biopar",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[
            spatial_extent,
            temporal_extent,
            biopar_type,
        ]
    )


if __name__ == "__main__":
    with open("biopar_apex.json", "w") as f:
        json.dump(generate(), f, indent=2)