import json
from pathlib import Path
import openeo
from openeo.api.process import Parameter
from openeo.rest.udp import build_process_dict


def generate() -> dict:

    conn = openeo.connect("openeo.vito.be").authenticate_oidc()

    # define input parameter
    spatial_extent = Parameter.spatial_extent(
        name = "spatial_extent", 
        description = "Limits the data to process to the specified bounding box or polygons."
        )

    temporal_extent = Parameter.temporal_interval(
        name = "temporal_extent", 
        description = "Temporal extent specified as two-element array with start and end date/date-time."
        )
    # Load s2 bands and set max cloud cover to be less than 10%
    s2_bands = conn.load_collection(
        collection_id="SENTINEL2_L2A",
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        bands=["B04", "B08"],
        max_cloud_cover=10,
    )

    # Build the process dictionary
    return build_process_dict(
        process_graph=s2_bands,
        process_id="s2_bands",
        summary="s2_bands",
        description="s2_bands",
        parameters=[spatial_extent, temporal_extent]
    )


if __name__ == "__main__":
    # save the generated process to a file
    with open(Path(__file__).parent / "random_forest_firemapping.json", "w") as f:
        json.dump(generate(), f, indent=2)
