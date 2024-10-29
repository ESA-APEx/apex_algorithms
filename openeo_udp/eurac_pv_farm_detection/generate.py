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
    spatial_extent = Parameter.bounding_box(
        name="spatial_extent",
        default={"west": 16.342, "south": 47.962, "east": 16.414, "north": 48.008},
    )

    # define temporal_extent
    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent", default=["2023-05-01", "2023-09-30"]
    )

    # load the input data
    conn = openeo.connect(
        "https://openeofed.dataspace.copernicus.eu/"
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

    return build_process_dict(
        process_graph=dilated_cube,
        process_id="eurac_pv_farm_detection",
        summary="An openEO process developed by EURAC to detect photovoltaic farms, based on sentinel2 data.",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[spatial_extent, temporal_extent],
        returns=None,  # TODO
        categories=None,  # TODO
    )


if __name__ == "__main__":
    # save the generated process to a file
    output_path = Path(__file__).parent
    print(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save the generated process to a file
    with open(output_path / "eurac_pv_farm_detection.json", "w") as f:
        json.dump(generate(), f, indent=2)
