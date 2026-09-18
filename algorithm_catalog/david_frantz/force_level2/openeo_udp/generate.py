import json
from pathlib import Path

import openeo
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict

def generate():
    connection = openeo.connect("openeo.dataspace.copernicus.eu").authenticate_oidc()

   

    # cube = connection.load_collection(
    #     collection_id="SENTINEL2_L2A",
    #     bands=[
    #     "B03",
    #     "B04",
    #     "B08",
    #     "sunAzimuthAngles",
    #     "sunZenithAngles",
    #     "viewAzimuthMean",
    #     "viewZenithMean"
    #     ],
    #     temporal_extent=temporal_extent,
    #     spatial_extent=spatial_extent,
    # )
    # scl = connection.load_collection(
    #     collection_id="SENTINEL2_L2A",
    #     bands=["SCL"],
    #     temporal_extent=temporal_extent,
    #     spatial_extent=spatial_extent,
    # )

    # mask = scl.process("to_scl_dilation_mask", data=scl)
    # cube = cube.mask(mask)

    # udf = openeo.UDF.from_file(
    #     Path(__file__).parent / "biopar_udf.py",
    #     runtime="Python",
    #     context={"biopar_type": {"from_parameter": "biopar_type"}},
    # )
    # # print(udf)
    # biopar = cube.reduce_dimension(
    #     dimension="bands",
    #     reducer=udf,
    # )
    # biopar = biopar.add_dimension("bands", label=biopar_type, type="bands")
    

    # return build_process_dict(
    #     process_graph=biopar,
    #     process_id="biopar",
    #     description=(Path(__file__).parent / "README.md").read_text(),
    #     parameters=[
    #         spatial_extent,
    #         temporal_extent,
    #         biopar_type,
    #     ]
    # )
    
    connection.describe_process("force_level2")
    return {}


if __name__ == "__main__":
    with open("force_level2.json", "w") as f:
        json.dump(generate(), f, indent=2)