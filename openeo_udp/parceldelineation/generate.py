import json
from pathlib import Path
import openeo
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict


# TODO investigate setting max cloud cover and kernel size as parameters as well
def generate() -> dict:
    # define spatial_extent
    spatial_extent = Parameter.bounding_box(
        name="spatial_extent",
        default={"west": 5.0, "south": 51.2, "east": 5.1, "north": 51.3})

    # define temporal_extent
    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent", default=["2021-01-01", "2021-12-31"]
    )

    # backend to connect and load
    backend_url = "openeo.dataspace.copernicus.eu/"
    conn = openeo.connect(backend_url).authenticate_oidc()

    # load the input data and filter based on cloud cover.
    # max cloud cover should be less than 10%
    s2_bands = conn.load_collection(
        collection_id="SENTINEL2_L2A",
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        bands=["B04", "B08"],
        max_cloud_cover=10,
    )

    # The delineation will be estimated based on the NDVI. The `ndvi` process can be used for these calculations.
    ndviband = s2_bands.ndvi(red="B04", nir="B08")

    # Apply ML algorithm
    # We now apply a neural network, that requires 128x128 pixel 'chunks' input.
    segment_udf = openeo.UDF.from_file("udf_segmentation.py")
    # segment_udf = openeo.UDF.from_url("https://raw.githubusercontent.com/Open-EO/openeo-community-examples/main/python/ParcelDelineation/udf_segmentation.py")
    segmentationband = ndviband.apply_neighborhood(
        process=segment_udf,
        size=[{"dimension": "x", "value": 64, "unit": "px"},
              {"dimension": "y", "value": 64, "unit": "px"}],
        overlap=[{"dimension": "x", "value": 32, "unit": "px"},
                 {"dimension": "y", "value": 32, "unit": "px"}],
    )
    
    # We postprocess the output from the neural network using a sobel filter and
    # Felzenszwalb's algorithm, which are then merged. This time, we work on larger
    # chunks, to reduce the need for stitching the vector output.
    segment_postprocess_udf = openeo.UDF.from_file("udf_sobel_felzenszwalb.py")
    # segment_postprocess_udf = openeo.UDF.from_url("https://raw.githubusercontent.com/Open-EO/openeo-community-examples/refs/heads/main/python/ParcelDelineation/udf_sobel_felzenszwalb.py")
    sobel_felzenszwalb = segmentationband.apply_neighborhood(
        process=segment_postprocess_udf,
        size=[{"dimension": "x", "value": 2048, "unit": "px"},
              {"dimension": "y", "value": 2048, "unit": "px"}],
        overlap=[{"dimension": "x", "value": 0, "unit": "px"},
                 {"dimension": "y", "value": 0, "unit": "px"}],
    )

    return build_process_dict(
        process_graph=sobel_felzenszwalb,
        process_id= "Parcel Delineation",
        summary= "Parcel delineation using Sentinel-2 data retrived from the CDSE and processed on openEO.",
        description= "Parcel delineation using Sentinel-2",
        parameters= [spatial_extent, temporal_extent],
        returns=None,  # TODO
        categories=None,  # TODO
    )


if __name__ == "__main__":
    # save the generated process to a file
    output_path = Path(__file__).parent
    print(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save the generated process to a file
    with open(output_path / "parcel_delineation.json", "w") as f:
        json.dump(generate(), f, indent=2)
