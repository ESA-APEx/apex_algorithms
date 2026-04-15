import json
from pathlib import Path

import openeo
from openeo import UDF
from openeo.api.process import Parameter
from openeo.processes import if_, eq
from openeo.rest.connection import Connection
from openeo.rest.datacube import DataCube
from openeo.rest.udp import build_process_dict

from s2_index import (
    s2_scl,
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

    Runs per time slice and outputs waterline geometries.
    """

    # Vectorize cube
    #cube = cube.raster_to_vector()

    udf = UDF.from_file(
        Path(__file__).parent / "udf_waterlines_from_water_land_mask.py",
        context={"from_parameter": "context"},
    )
    return cube.apply_dimension(
        process=udf,
        dimension="t",
        context={"simplify_tolerance": simplify_tolerance},
    )


def build_water_land_mask_cube(
    con: Connection,
    bbox,
    time_range,
    max_cloud_coverage,
    method,
    iterations,
    ndwi_threshold,
    mndwi_threshold,
    ndvi_threshold,
    bndvi_threshold,
    gndvi_threshold,
):
    """
    Build a water/land mask using multiple selectable Sentinel-2 methods.

    All method branches are constructed and the selected one is chosen
    using openEO graph logic (since 'method' is a UDP parameter).
    """
    # Build all candidate branches

    _, scl_cube = s2_scl(
        con,
        DEFAULT_S2_COLLECTION,
        bbox,
        time_range,
        max_cloud_coverage=max_cloud_coverage
    )
    scl_cube = apply_morphology(scl_cube, iterations)

    _, ndwi_cube = s2_index_mask(
        con=con,
        collection_id=DEFAULT_S2_COLLECTION,
        bbox=bbox,
        time_range=time_range,
        index_name="S2_NDWI",
        threshold=ndwi_threshold,
        mode="gt",
        max_cloud_coverage=max_cloud_coverage,
    )
    ndwi_cube = apply_morphology(ndwi_cube, iterations)

    _, mndwi_cube = s2_index_mask(
        con=con,
        collection_id=DEFAULT_S2_COLLECTION,
        bbox=bbox,
        time_range=time_range,
        index_name="S2_MNDWI",
        threshold=mndwi_threshold,
        mode="gt",
        max_cloud_coverage=max_cloud_coverage,
    )
    mndwi_cube = apply_morphology(mndwi_cube, iterations)

    _, ndvi_cube = s2_index_mask(
        con=con,
        collection_id=DEFAULT_S2_COLLECTION,
        bbox=bbox,
        time_range=time_range,
        index_name="S2_NDVI",
        threshold=ndvi_threshold,
        mode="lt",
        max_cloud_coverage=max_cloud_coverage,
    )
    ndvi_cube = apply_morphology(ndvi_cube, iterations)

    _, bndvi_cube = s2_index_mask(
        con=con,
        collection_id=DEFAULT_S2_COLLECTION,
        bbox=bbox,
        time_range=time_range,
        index_name="S2_BNDVI",
        threshold=bndvi_threshold,
        mode="lt",
        max_cloud_coverage=max_cloud_coverage,
    )
    bndvi_cube = apply_morphology(bndvi_cube, iterations)

    _, gndvi_cube = s2_index_mask(
        con=con,
        collection_id=DEFAULT_S2_COLLECTION,
        bbox=bbox,
        time_range=time_range,
        index_name="S2_GNDVI",
        threshold=gndvi_threshold,
        mode="lt",
        max_cloud_coverage=max_cloud_coverage,
    )
    gndvi_cube = apply_morphology(gndvi_cube, iterations)

    # Select branch in the process graph.
    selected = if_(
        eq(method, "S2_SCL"),
        scl_cube,
        if_(
            eq(method, "S2_MNDWI"),
            mndwi_cube,
            if_(
                eq(method, "S2_NDVI"),
                ndvi_cube,
                if_(
                    eq(method, "S2_BNDVI"),
                    bndvi_cube,
                    if_(
                        eq(method, "S2_GNDVI"),
                        gndvi_cube,
                        ndwi_cube,  # default fallback
                    ),
                ),
            ),
        ),
    )

    return selected


def generate() -> dict:
    """
    Create the UDP for extracting waterlines from Sentinel-2 imagery.

    Workflow:
    1. Load data
    2. Create water/land mask (selectable method)
    3. Apply morphology
    4. Extract waterlines
    """

    ### 1. Create backend connection
    conn = openeo.connect(url="openeo.dataspace.copernicus.eu")

    ### 2. Define UDP input parameters
    spatial_extent = Parameter.bounding_box(
        name="spatial_extent",
        description=("Bounding box of the area of interest. " "Defined as west, south, east, north in EPSG:4326."),
    )

    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent",
        default=["2015-06-23", "2025-12-31"],
        description="Date range over which to extract waterlines.",
    )

    max_cloud_coverage = Parameter.number(
        name="max_cloud_coverage",
        default=DEFAULT_MAX_CLOUD_COVER,
        description=("Maximum allowed cloud coverage.")
    )

    method = Parameter.string(
        name="s2_method",
        default="S2_NDWI",
        values=["S2_NDWI", "S2_MNDWI", "S2_SCL", "S2_NDVI", "S2_BNDVI", "S2_GNDVI"],
        description="Method used to create the water/land mask from Sentinel-2 imagery.",
    )

    iterations = Parameter.integer(
        name="iterations",
        default=2,
        description="Number of iterations for morphological operations.",
    )

    ### 3. Define threshold parameters
    ndwi_threshold = Parameter.number(
        name="ndwi_threshold",
        default=WATERLAND_THRESHOLDS["S2_NDWI"].defaults["threshold"],
        description=WATERLAND_THRESHOLDS["S2_NDWI"].description,
    )
    mndwi_threshold = Parameter.number(
        name="mndwi_threshold",
        default=WATERLAND_THRESHOLDS["S2_MNDWI"].defaults["threshold"],
        description=WATERLAND_THRESHOLDS["S2_MNDWI"].description,
    )
    ndvi_threshold = Parameter.number(
        name="ndvi_threshold",
        default=WATERLAND_THRESHOLDS["S2_NDVI"].defaults["threshold"],
        description=WATERLAND_THRESHOLDS["S2_NDVI"].description,
    )
    bndvi_threshold = Parameter.number(
        name="bndvi_threshold",
        default=WATERLAND_THRESHOLDS["S2_BNDVI"].defaults["threshold"],
        description=WATERLAND_THRESHOLDS["S2_BNDVI"].description,
    )
    gndvi_threshold = Parameter.number(
        name="gndvi_threshold",
        default=WATERLAND_THRESHOLDS["S2_GNDVI"].defaults["threshold"],
        description=WATERLAND_THRESHOLDS["S2_GNDVI"].description,
    )

    ### 4. Build the water/land mask graph
    water_land_mask = build_water_land_mask_cube(
        con=conn,
        bbox=spatial_extent,
        time_range=temporal_extent,
        max_cloud_coverage=max_cloud_coverage,
        method=method,
        iterations=iterations,
        ndwi_threshold=ndwi_threshold,
        mndwi_threshold=mndwi_threshold,
        ndvi_threshold=ndvi_threshold,
        bndvi_threshold=bndvi_threshold,
        gndvi_threshold=gndvi_threshold,
    )

    ### 5. Extract waterlines from the cleaned water/land mask
    waterlines_cube = create_waterlines(water_land_mask)

    return build_process_dict(
        process_graph=waterlines_cube,
        process_id="waterlines",
        summary="Waterlines extracted from Sentinel-2.",
        description=(Path(__file__).parent / "README.md").read_text(),
        parameters=[
            spatial_extent,
            temporal_extent,
            max_cloud_coverage,
            method,
            iterations,
            ndwi_threshold,
            mndwi_threshold,
            ndvi_threshold,
            bndvi_threshold,
            gndvi_threshold,
        ],
        categories=["sentinel-2", "coastline", "waterlines"],
    )


if __name__ == "__main__":
    with open(Path(__file__).parent / "waterlines.json", "w") as f:
        json.dump(generate(), f, indent=2)
