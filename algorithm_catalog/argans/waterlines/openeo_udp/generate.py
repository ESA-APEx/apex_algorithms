import json
from pathlib import Path

import openeo
from openeo import UDF
from openeo.api.process import Parameter
from openeo.rest.connection import Connection
from openeo.rest.datacube import DataCube
from openeo.rest.udp import build_process_dict

from s2_index import (
    s2_index_mask,
    DEFAULT_S2_COLLECTION,
    DEFAULT_MAX_CLOUD_COVER,
    WATERLAND_THRESHOLDS,
)


def apply_morphology(cube: DataCube, iterations: int) -> DataCube:
    """
    Apply morphological operations to each time slice of a water/land mask.

    Used to clean the mask (remove noise, fill gaps, smooth shapes)
    before extracting waterlines.
    """
    udf = UDF.from_file(
        Path(__file__).parent / "udf_morph_operations.py",
        context={"from_parameter": "context"},
    )
    return cube.apply_dimension(
        process=udf,
        dimension="t",
        context={"iterations": iterations},
    )


def create_waterlines(cube: DataCube, simplify_tolerance: float = 10) -> DataCube:
    """
    Extract waterlines from a water/land mask using a UDF.

    The input must remain a DataCube because the workflow relies on
    `raster_to_vector()` before applying the vector-based waterline UDF.
    """
    cube = cube.raster_to_vector()

    udf = UDF.from_file(
        Path(__file__).parent / "udf_waterlines_from_water_land_mask.py",
        context={"from_parameter": "context"},
    )
    return cube.apply_dimension(
        process=udf,
        dimension="geometry",
        context={"simplify_tolerance": simplify_tolerance},
    )


def build_water_land_mask_cube(
    con: Connection,
    bbox,
    time_range,
    max_cloud_coverage,
    iterations,
    ndwi_threshold,
) -> DataCube:
    """
    Build a water/land mask using Sentinel-2 NDWI only.

    MVP rationale:
    Multiple selectable methods were intentionally removed from this UDP.
    Selecting between whole DataCubes through nested openEO `if_()` expressions
    turns the selected result into a ProcessBuilder rather than a DataCube.
    That breaks the next step of the workflow, because `raster_to_vector()` is
    used as a DataCube method when preparing input for the vector-based
    waterline UDF.

    S2_NDWI was chosen for the MVP because it is a standard water-detection
    index, fits the existing index-mask pipeline, and allows validation of the
    complete end-to-end workflow without introducing graph-selection complexity.

    Future extensions can add the other methods either as separate UDPs or by
    refactoring the waterline UDF to work directly on raster input.
    """
    _, cube = s2_index_mask(
        con=con,
        collection_id=DEFAULT_S2_COLLECTION,
        bbox=bbox,
        time_range=time_range,
        index_name="S2_NDWI",
        threshold=ndwi_threshold,
        mode="gt",
        max_cloud_coverage=max_cloud_coverage,
    )
    return apply_morphology(cube, iterations)


def generate() -> dict:
    """
    Create the MVP UDP for extracting waterlines from Sentinel-2 imagery.

    Workflow:
    1. Load Sentinel-2 data
    2. Create water/land mask using S2_NDWI
    3. Apply morphology
    4. Vectorize the mask
    5. Extract waterlines

    Why only S2_NDWI?
    The original multi-method design used a runtime UDP parameter to choose
    between several masking methods. In practice, selecting between whole cubes
    with openEO graph logic (`if_`) produced a ProcessBuilder instead of a
    DataCube. Because the downstream workflow needs `raster_to_vector()`, that
    design blocked the current implementation.

    Restricting the MVP to a single method keeps the graph in DataCube form and
    allows the existing vector-based waterline UDF to work unchanged.
    """

    conn = openeo.connect(url="openeo.dataspace.copernicus.eu")

    spatial_extent = Parameter.bounding_box(
        name="spatial_extent",
        description="Bounding box of the area of interest. Defined as west, south, east, north in EPSG:4326.",
    )

    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent",
        default=["2015-06-23", "2025-12-31"],
        description="Date range over which to extract waterlines.",
    )

    max_cloud_coverage = Parameter.number(
        name="max_cloud_coverage",
        default=DEFAULT_MAX_CLOUD_COVER,
        description="Maximum allowed cloud coverage.",
    )

    iterations = Parameter.integer(
        name="iterations",
        default=2,
        description="Number of iterations for morphological operations.",
    )

    ndwi_threshold = Parameter.number(
        name="ndwi_threshold",
        default=WATERLAND_THRESHOLDS["S2_NDWI"].defaults["threshold"],
        description=WATERLAND_THRESHOLDS["S2_NDWI"].description,
    )

    simplify_tolerance = Parameter.number(
        name="simplify_tolerance",
        default=10,
        description="Tolerance used to simplify vectorized water polygons before extracting waterlines.",
    )

    water_land_mask = build_water_land_mask_cube(
        con=conn,
        bbox=spatial_extent,
        time_range=temporal_extent,
        max_cloud_coverage=max_cloud_coverage,
        iterations=iterations,
        ndwi_threshold=ndwi_threshold,
    )

    waterlines_cube = create_waterlines(
        water_land_mask,
        simplify_tolerance=simplify_tolerance,
    )

    return build_process_dict(
        process_graph=waterlines_cube,
        process_id="waterlines_s2_ndwi",
        summary="Waterlines extracted from Sentinel-2 using NDWI.",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[
            spatial_extent,
            temporal_extent,
            max_cloud_coverage,
            iterations,
            ndwi_threshold,
            simplify_tolerance,
        ],
        categories=["sentinel-2", "coastline", "waterlines"],
    )


if __name__ == "__main__":
    with open(Path(__file__).parent / "waterlines_s2_ndwi.json", "w") as f:
        json.dump(generate(), f, indent=2)