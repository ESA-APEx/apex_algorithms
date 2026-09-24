"""
Test / demo script for the `gfm_temporal_aggregation` UDP.

It reproduces the openEO Platform GFM use case (Pakistan floods, September 2022) and
writes a GeoTIFF with the maximum observed flood extent.
"""

import openeo
from algorithm_catalog.esa.gfm_aggregation.openeo_udp.gfm_temporal_aggregation import BACKEND, PROCESS_ID, build_cube

# Pakistan flood 2022, as in https://docs.openeo.cloud/usecases/gfm/
SPATIAL_EXTENT = {"west": 67.5, "east": 70.0, "south": 24.5, "north": 26.0}
TEMPORAL_EXTENT = ["2022-09-01", "2022-10-01"]
UDP_URL = (
    "https://raw.githubusercontent.com/ESA-APEx/apex_algorithms/refs/heads/gfm_aggregation/"
    "algorithm_catalog/vito/gfm_aggregation/openeo_udp/gfm_temporal_aggregation.json"
)

BANDS = ["ensemble_flood_extent"]
STATISTIC = "max"


def main() -> None:
    connection = openeo.connect(BACKEND).authenticate_oidc()
    output = "gfm_aggregation.tif"

    cube = connection.datacube_from_process(
        process_id=PROCESS_ID,
        namespace=UDP_URL,
        spatial_extent=SPATIAL_EXTENT,
        temporal_extent=TEMPORAL_EXTENT,
        bands=BANDS,
        statistic=STATISTIC,
    )

    # cube = build_cube(
    #     spatial_extent=SPATIAL_EXTENT,
    #     temporal_extent=TEMPORAL_EXTENT,
    #     bands=BANDS,
    #     statistic=STATISTIC,
    #     connection=connection,
    # )

    cube.execute_batch(output, title=f"GFM Temporal Aggregation - {STATISTIC} for {', '.join(BANDS)}")
    print(f"Result written to {output}")


if __name__ == "__main__":
    main()
