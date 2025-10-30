import json
from pathlib import Path
import openeo
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict


def generate() -> dict:
    # DEFINE PARAMETERS
    # define spatial_extent
    spatial_extent = Parameter.bounding_box(
        name="spatial_extent", default={"west": 5.0, "south": 51.2, "east": 5.1, "north": 51.3}
    )
    # define temporal_extent
    temporal_extent = Parameter.temporal_interval(name="temporal_extent", default=["2021-01-01", "2021-12-31"])

    # backend to connect and load
    backend_url = "openeo.dataspace.copernicus.eu/"
    conn = openeo.connect(backend_url).authenticate_oidc()

    # Compute cloud mask, and filter input data based on cloud mask.
    # compute cloud mask using the SCL band
    scl = conn.load_collection(
        "SENTINEL2_L2A",
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        bands=["SCL"],
        max_cloud_cover=10,
    )
    cloud_mask = scl.process(
        "to_scl_dilation_mask",
        data=scl,
        kernel1_size=17,
        kernel2_size=77,
        mask1_values=[2, 4, 5, 6, 7],
        mask2_values=[3, 8, 9, 10, 11],
        erosion_kernel_size=3,
    )

    # Load s2 bands and set max cloud cover to be less than 10%
    s2_bands = conn.load_collection(
        collection_id="SENTINEL2_L2A",
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        bands=["B04", "B08"],
        max_cloud_cover=10,
    )
    # mask data with cloud mask
    s2_bands_masked = s2_bands.mask(cloud_mask)

    # The delineation will be estimated based on the NDVI. The `ndvi` process can be used for these calculations.
    ndviband = s2_bands_masked.ndvi(red="B04", nir="B08")

    # Apply ML algorithm
    # apply a neural network, requires 128x128 pixel 'chunks' as input.
    segment_udf = openeo.UDF.from_file("udf_segmentation.py", version="3.8")
    segmentationband = ndviband.apply_neighborhood(
        process=segment_udf,
        size=[{"dimension": "x", "value": 64, "unit": "px"}, {"dimension": "y", "value": 64, "unit": "px"}],
        overlap=[{"dimension": "x", "value": 32, "unit": "px"}, {"dimension": "y", "value": 32, "unit": "px"}],
    )

    # Postprocess the output from the neural network using a sobel filter and
    # Felzenszwalb's algorithm, which are then merged.
    segment_postprocess_udf = openeo.UDF.from_file("udf_sobel_felzenszwalb.py")
    sobel_felzenszwalb = segmentationband.apply_neighborhood(
        process=segment_postprocess_udf,
        size=[{"dimension": "x", "value": 2048, "unit": "px"}, {"dimension": "y", "value": 2048, "unit": "px"}],
        overlap=[{"dimension": "x", "value": 0, "unit": "px"}, {"dimension": "y", "value": 0, "unit": "px"}],
    )
    job_options = {
        "udf-dependency-archives": [
            "https://artifactory.vgt.vito.be/auxdata-public/openeo/onnx_dependencies.zip#onnx_deps",
            "https://artifactory.vgt.vito.be/artifactory/auxdata-public/openeo/parcelDelination/BelgiumCropMap_unet_3BandsGenerator_Models.zip#onnx_models",
        ],
        "driver-memory": "500m",
        "driver-memoryOverhead": "1000m",
        "executor-memory": "1000m",
        "executor-memoryOverhead": "500m",
        "python-memory": "4200m",
    }

    # Build the process dictionary
    return build_process_dict(
        process_graph=sobel_felzenszwalb,
        process_id="parcel_delineation",
        summary="Parcel delineation using Sentinel-2 data retrieved from the CDSE and processed on openEO.",
        description= (Path(__file__).parent / "README.md").read_text(),
        parameters=[spatial_extent, temporal_extent],
        default_job_options=job_options,
    )


if __name__ == "__main__":
    # save the generated process to a file
    output_path = Path(__file__).parent
    print(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save the generated process to a file
    with open(output_path / "parcel_delineation.json", "w") as f:
        json.dump(generate(), f, indent=2)
