# %%



import json
from pathlib import Path

import numpy as np
import openeo
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict


# TODO investigate setting max cloud cover and kernel size as parameters as well
def generate() -> dict:
    # define spatial_extent
    spatial_extent = Parameter.spatial_extent(
        default={"west": 16.342, "south": 47.962, "east": 16.414, "north": 48.008}
    )

    # define temporal_extent
    temporal_extent = Parameter.temporal_interval(default=["2023-05-01", "2023-09-30"])

    # load the input data
    conn = openeo.connect(
        "openeofed.dataspace.copernicus.eu"
    ).authenticate_oidc()

    s2_cube = conn.load_collection(
        collection_id="SENTINEL2_L2A",
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        bands=["B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"],
        max_cloud_cover=85,
    )

    # Mask out clouded data
    scl = conn.load_collection(
        "SENTINEL2_L2A",
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        bands=["SCL"],
        max_cloud_cover=85,
    )

    mask = scl.process("to_scl_dilation_mask", data=scl)
    s2_cube = s2_cube.mask(mask)

    # Create weekly composites by taking the mean
    s2_cube = s2_cube.aggregate_temporal_period(period="week", reducer="mean")

    # Fill gaps in the data using linear interpolation
    s2_cube = s2_cube.apply_dimension(dimension="t", process="array_interpolate_linear")

    s2_cube = s2_cube.reduce_dimension(dimension="t", reducer="median")

    # Run ML inference to get the classification output
    udf = openeo.UDF.from_file(
        Path(__file__).parent / "udf_eurac_pvfarm_onnx.py",
        
    )

    prediction = s2_cube.reduce_bands(reducer=udf)

    # Post-process the data with an opening (erosion + dilation)
    kernel = np.ones((3, 3))
    factor = 1.0 / np.prod(np.shape(kernel))

    eroded_cube = (prediction.apply_kernel(kernel=kernel, factor=factor) >= 1) * 1.0
    dilated_cube = (eroded_cube.apply_kernel(kernel=kernel, factor=factor) > 0) * 1.0

    returns = {
        "description": "A data cube with the newly computed values.\n\nAll dimensions stay the same, except for the dimensions specified in corresponding parameters. There are three cases how the dimensions can change:\n\n1. The source dimension is the target dimension:\n   - The (number of) dimensions remain unchanged as the source dimension is the target dimension.\n   - The source dimension properties name and type remain unchanged.\n   - The dimension labels, the reference system and the resolution are preserved only if the number of values in the source dimension is equal to the number of values computed by the process. Otherwise, all other dimension properties change as defined in the list below.\n2. The source dimension is not the target dimension. The target dimension exists with a single label only:\n   - The number of dimensions decreases by one as the source dimension is 'dropped' and the target dimension is filled with the processed data that originates from the source dimension.\n   - The target dimension properties name and type remain unchanged. All other dimension properties change as defined in the list below.\n3. The source dimension is not the target dimension and the latter does not exist:\n   - The number of dimensions remain unchanged, but the source dimension is replaced with the target dimension.\n   - The target dimension has the specified name and the type other. All other dimension properties are set as defined in the list below.\n\nUnless otherwise stated above, for the given (target) dimension the following applies:\n\n- the number of dimension labels is equal to the number of values computed by the process,\n- the dimension labels are incrementing integers starting from zero,\n- the resolution changes, and\n- the reference system is undefined.",
        "schema": {
            "type": "object",
            "subtype": "datacube"
        }
    }

    default_options = {
        "driver-memory": "1g",
        "executor-memory": "1g",
        "python-memory": "3g",
        "udf-dependency-archives": [
            "https://artifactory.vgt.vito.be/artifactory/auxdata-public/openeo/onnx_dependencies_1.16.3.zip#onnx_deps"
        ]
    }

    return build_process_dict(
        process_graph=dilated_cube,
        process_id="eurac_pv_farm_detection",
        summary="An openEO process developed by Eurac Research to detect photovoltaic farms, based on sentinel2 data.",
        description=(Path(__file__).parent / "eurac_pv_farm_detection_description.md").read_text(),
        parameters=[spatial_extent, temporal_extent],
        returns=returns,
        categories=["sentinel-2", "energy"],
        default_job_options=default_options
    )


if __name__ == "__main__":
    # save the generated process to a file
    output_path = Path(__file__).parent
    print(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save the generated process to a file
    with open(output_path / "eurac_pv_farm_detection.json", "w") as f:
        json.dump(generate(), f, indent=2)


#%%
