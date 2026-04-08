import json
import sys
from pathlib import Path
import openeo
from openeo.api.process import Parameter
from openeo.rest.connection import Connection
from openeo.rest.datacube import DataCube
from openeo.rest.udp import build_process_dict
from openeo import UDF
from s2_index import (
    WATERLAND_THRESHOLDS,
    s2_scl,
    s2_index_mask,
    DEFAULT_S2_COLLECTION,
    Reducer,
    DEFAULT_MAX_CLOUD_COVER,
)


def build_water_land_mask_cube(
    con: Connection,
    bbox,
    time_range,
    method,
    threshold,
    iterations,
) -> DataCube:
    """Build an openEO processing cube for the given water/land mask run specification."""
    spec = WATERLAND_THRESHOLDS.get(method)

    if spec is None:
        raise ValueError(f"Unsupported water/land mask method: {method}")

    if method == "S2_SCL":
        _, water_land_mask_cube = s2_scl(
            con, DEFAULT_S2_COLLECTION, bbox, time_range, Reducer.NONE
        )

    else:
        # If user doesn't specify, always take the default.
        threshold = threshold if threshold is not None else spec.defaults["threshold"]

        _, water_land_mask_cube = s2_index_mask(
            con=con,
            collection_id=DEFAULT_S2_COLLECTION,
            bbox=bbox,
            time_range=time_range,
            reducer=Reducer.NONE,
            index_name=method,
            threshold=threshold,
            mode=spec.mode.value,  # "gt" or "lt"
            max_cloud_coverage=DEFAULT_MAX_CLOUD_COVER,
        )

    udf = UDF.from_file(
        Path(__file__).parent / "udf_morph_operations.py",
        context={"from_parameter": "context"},
    )
    water_land_mask_cube = water_land_mask_cube.apply_dimension(
        process=udf, dimension="t", context={"iterations": iterations}
    )

    return water_land_mask_cube


def generate() -> dict:

    # 1. Connection
    conn = openeo.connect(url="openeo.dataspace.copernicus.eu")

    # 2. Define parameters
    spatial_extent = Parameter.bounding_box(
        name="spatial_extent",
        default={"west": 5.0, "south": 51.2, "east": 5.1, "north": 51.3},
    )
    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent", default=["2025-01-01", "2025-12-31"]
    )
    
    #method = Parameter.string(name="s2_method", default="S2_NDWI")

    #threshold = Parameter.number(name="threshold", default=None)

    iterations = Parameter.integer(name="iterations", default=2)

    water_land_mask = build_water_land_mask_cube(
        con=conn,
        bbox=spatial_extent,
        time_range=temporal_extent,
        method="S2_NDWI",
        threshold=None,
        iterations=iterations,
    )

    udf = UDF.from_file(
        Path(__file__).parent / "udf_waterlines_from_water_land_mask.py",
        context={"from_parameter": "context"},
    )
    waterlines_cube = water_land_mask.apply_dimension(
        process=udf, dimension="t", context={"crs": "EPSG:3857", "time_dim": "t"}
    )

    return build_process_dict(
        process_graph=waterlines_cube,
        process_id="waterlines",
        summary="Waterlines extracted from Sentinel-2.",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[
            spatial_extent,
            temporal_extent,
            iterations,
        ],
        categories=["sentinel-2", "coastline", "waterlines"],
    )

if __name__ == "__main__":
    json.dump(generate(), sys.stdout, indent=2)