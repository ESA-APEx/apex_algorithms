import json
import sys
from pathlib import Path

import openeo
from openeo.api.process import Parameter
from openeo.processes import array_create, and_, if_, inspect, array_element, not_
from openeo.processes import sqrt as sqrt_, add, multiply, subtract
from openeo.rest.udp import build_process_dict
from openeo.rest.connection import Connection

from typing import List, Union

d_description = {
    "te": "Temporal extend", 
    "bb": "Bounding Box",
    "cc": "Maximum allowed scene-wide cloud cover for the scene to be considered in the composite",
    "sigma": "Sigma for median absolute deviation outlier detection in Band B02, default=3.0",
    "sza": "Maximum sun zenith angle (at pixel level) for a pixel to be considered in the composite. Default value (70.0) derived from Sen2Cor recommendation.",
    "ci": "Computes the 95-Confidence interval for each band. Will increase credit consumption"
}

S2_BANDS = "B02 B03 B04 B05 B06 B07 B08 B8A B11 B12".split()
RES_BANDS = {
    "SRC": [f"SRC_{b}" for b in S2_BANDS],
    "SRC-STD": [f"SRC-STD_{b}" for b in S2_BANDS],
    "MREF": [f"MREF_{b}" for b in S2_BANDS],
    "MREF-STD": [f"MREF-STD_{b}" for b in S2_BANDS],
    "SRC-CI": [f"SRC-CI95_{b}" for b in S2_BANDS],
    "SFREQ-VALID": "ValidPixels",
    "SFREQ-COUNT": "BareSoilPixelsCount",
    "SFREQ-FREQ": "BareSoilFrequency"
}

SCL_LEGEND = {
        "no_data": 0,
        "saturated_or_defective": 1,
        "dark_area_pixels": 2,
        "cloud_shadows": 3,
        "vegetation": 4,
        "not_vegetated": 5,
        "water": 6,
        "unclassified": 7,
        "cloud_medium_probability": 8,
        "cloud_high_probability": 9,
        "thin_cirrus": 10,
        "snow": 11}

def scl_to_masks(scl_layer):
        to_mask = openeo.processes.any(
            array_create(
                [
                    scl_layer == SCL_LEGEND["cloud_shadows"],
                    scl_layer == SCL_LEGEND["cloud_medium_probability"],
                    scl_layer == SCL_LEGEND["cloud_high_probability"],
                    scl_layer == SCL_LEGEND["thin_cirrus"],
                    scl_layer == SCL_LEGEND["saturated_or_defective"],
                    scl_layer == SCL_LEGEND["snow"],
                    scl_layer == SCL_LEGEND["no_data"],
                    scl_layer == SCL_LEGEND["dark_area_pixels"],
                    scl_layer == SCL_LEGEND["unclassified"],
                ]
            ),
        )

        return to_mask

def nmad(cube: openeo.DataCube, nmad_sigma: float|Parameter, min_offset=80.0) -> openeo.DataCube:
    def _nmad(ts):
        med = ts.median()
        absdev = (ts - med).absolute()
        mad   = absdev.median()
        nmad  = mad * 1.4826

        upper = med + nmad_sigma * nmad
        min_limit = med + min_offset
        return and_(ts.gt(upper), ts.gt(min_limit))       # logicals need to be called as functions
    
    b02 = cube.band("B02")
    is_outlier = b02.apply_dimension(dimension="t", process=_nmad)
    return cube.mask(is_outlier)


def _ci95(combined_cube: openeo.DataCube, sd_bands: List[str], n: str) -> openeo.DataCube:
    """ Compute 95% confidence interval according to 
    +- 1.96 * (sd / sqrt(n))
    """
    z = 1.96
    cubes = []
    n_sqrt = combined_cube.band(n).apply("sqrt")
    # FIXME Broadcasting to avoid loop
    # sd_cube = combined_cube.filter_bands(sd_bands)
    # n_sqrt = n_sqrt.add_dimension(name="bands", label=sd_bands[0])
    # n_sqrt = n_sqrt.rename_labels(
    #     dimension="bands",
    #     source=[sd_bands[0]],
    #     target=sd_bands
    # )
    # ci = sd_cube.divide(n_sqrt)
    # ci = ci * z
    # ci = ci.rename_labels(dimension="bands", target=RES_BANDS["SRC-CI"], source=sd_bands)
    # return ci

    
    for b in sd_bands:
        sd_cube = combined_cube.filter_bands(b)
        ci = sd_cube.divide(n_sqrt)
        ci = ci * z
        # ci = ci.rename_labels(dimension="bands", target=[RES_BANDS["SRC-CI"][bi]], source=[b[bi]])
        cubes.append(ci)
        
    for i in range(1, len(cubes)):
        cubes[0] = cubes[0].merge_cubes(cubes[i])
    
    cubes[0] = cubes[0].rename_labels(dimension="bands", target=RES_BANDS["SRC-CI"], source=sd_bands)
    return cubes[0]

def check_tile(x):
    return x.eq("32UPU")

def composite(con: Connection,
              temporal_extent: List[str]|Parameter,
              spatial_extent: dict|Parameter,
              max_cloud_cover: int|Parameter, 
              nmad_sigma: float|Parameter, 
              max_sun_zenith_angle: float=70, 
              compute_ci: bool|Parameter=True) -> openeo.DataCube:
    """
    Generate a Bare Surface Composite (SRC) and additional derived products.

    This function loads Sentinel-2 data through the provided openEO
    connection, applies quality filtering (cloud cover, SZA), performs
    NMAD-based outlier masking, and produces a temporal bare-sruface composite 
    and other by-products.
    The resulting product is returned as an openEO `DataCube`.

    Parameters
    ----------
    con : Connection
        An active openEO `Connection` used to load and process data.
    temporal_extent : list[str] or Parameter
        Start and end date of the period to composite
        (e.g. `["2022-01-01", "2022-12-31"]`). May also be provided
        as an openEO process parameter.
    spatial_extent : dict or Parameter
        Spatial extent (bounding box or polygon) defining the area of
        interest as defined by openEO spatial extent conventions.
    max_cloud_cover : int or Parameter
        Maximum allowed cloud cover percentage for selecting images.
    nmad_sigma : float or Parameter
        Threshold (in units of NMAD) used to mask outliers prior to
        compositing.
    max_sun_zenith_angle : float, optional
        Upper limit for the sun zenith angle filter, by default 70 degrees.
    compute_ci : bool, optional
        Can be disabled if Confidence Interval is not needed. Speeds up computation

    Returns
    -------
    openeo.DataCube
        A merged data cube containing the Bare Surface Composite and by-products
    """

    ### Input Data ###
    s2_cube = con.load_collection(
        collection_id="SENTINEL2_L2A",
        bands=["B02", "SCL"],
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        max_cloud_cover=max_cloud_cover,
        # properties={"tileId": check_tile}     # works
        # properties={"tileId": {"process_id": "eq","arguments": {"x":{"from_parameter":"value"},"y":"32UPU","case_sensitive":False},"result":True}}
    ).resample_spatial(resolution=20, method="average")

    
    # s2_cube = s2_cube.reduce_dimension(dimension='t', reducer="first").band("B02").multiply(1.0)
    # scl = scl.reduce_dimension(dimension='t', reducer="first").multiply(1.0)
    scl = s2_cube.band("SCL")
    s2_cube = s2_cube.band("B02")
    
    k = 11
    kernel_1D = array_create([[1.0] * k for _ in range(k)])
    # kernel = array_create(kernel_1D, repeat=k)
    kernel = kernel_1D

    cond_scl = scl.apply(process=scl_to_masks)

    # kernel = [[1] * 11 for _ in range(11)]

    b02_0 = s2_cube.mask(cond_scl)
    b02_0 = b02_0.reduce_dimension(dimension='t', reducer="first")
    dilated_mask = cond_scl.apply_kernel(kernel=kernel)
    dilated_mask = dilated_mask >= 1.0 
    b02_1 = s2_cube.mask(dilated_mask)
    b02_1 = b02_1.reduce_dimension(dimension='t', reducer="first")
    b02_1 = b02_1.add_dimension(name="bands", label="B02_d")
    ret = b02_0.merge_cubes(b02_1)
    cond_scl = cond_scl.add_dimension(name="bands", label="scl")
    dilated_mask = dilated_mask.add_dimension(name="bands", label="dilated_scl")
    ret = ret.merge_cubes(cond_scl)
    ret = ret.merge_cubes(dilated_mask)
    return ret


def auth(url: str="openeo.dataspace.copernicus.eu") -> Connection:
    connection = openeo.connect(url=url)
    connection.authenticate_oidc()
    return connection


def generate() -> dict:
    # TODO (paul) : Possibily replace with openeo.connect("openeofed.dataspace.copernicus.eu")
    con: Connection = auth()

    temporal_extent = Parameter.temporal_interval(
        name="temporal_extent",
        description=d_description["te"]
    )
    spatial_extent = Parameter.bounding_box(
        name = "bounding_box",
        description=d_description["bb"],
        default={"west": 11.1, "south": 48.0, "east": 11.3, "north": 48.2, "crs": "EPSG:4326"} 
    )
    max_scene_cloud_cover = Parameter.number(
        name = "max_cloud_cover",
        description=d_description["cc"], 
        default=80
    )
    # max_sun_zenith_angle = Parameter.number(
    #     name = "max_sun_zenith_angle",
    #     description=d_description["sza"],
    #     default=70
    # )
    nmad_sigma = Parameter.number(
        name = "nmad_sigma",
        description=d_description["sigma"],
        default=3.0
    )

    compute_ci = Parameter.boolean(
        name = "compute_ci",
        description=d_description["ci"],
        default=False
    )

    scmap_composite = composite(
        con=con, 
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        max_cloud_cover=max_scene_cloud_cover,
        nmad_sigma=nmad_sigma, 
        compute_ci=compute_ci
        # max_sun_zenith_angle=max_sun_zenith_angle
    )

    schema = {
        "description": "Bare surface composite with statistical producs",
        "schema": {
            "type": "object",
            "subtype": "datacube"
        }
    }

    return build_process_dict(
        process_graph=scmap_composite,
        process_id="scmap_composite",
        summary="Bare surface composite with statistical producs",
        description=(
            Path(__file__).parent / "Readme.md"
        ).read_text(),
        parameters=[
            temporal_extent,
            spatial_extent,
            max_scene_cloud_cover,
            nmad_sigma, 
            compute_ci,
            # max_sun_zenith_angle
        ],
        returns=schema,
        categories=["sentinel-2", "composites", "bare surface"]
    )

test_setup_small = {
    "bbox": { "west": 11.1, "south": 48.1, "east": 11.2, "north": 48.2, "crs": "EPSG:4326"},
    "temporal_extent": ["2025-04-01", "2025-05-07"],
    "nmad_sigma": 3.0,
    "max_sun_zenith_angle": 70.0,
}

test_setup_large = {
    "bbox": { "west": 11.60, "south": 48.50, "east": 12.0, "north": 48.9, "crs": "EPSG:4326"},
    "temporal_extent": ["2023-02-01", "2023-02-20"],
    "nmad_sigma": 3.0,
    "max_sun_zenith_angle": 70.0,
}

def test_run(d_test_setup=test_setup_small, path_out=Path("./result/")):
    con = auth()
    bbox = d_test_setup["bbox"]
    temporal_extent = d_test_setup["temporal_extent"]
    nmad_sigma = d_test_setup["nmad_sigma"]
    max_sun_zenith_angle = d_test_setup["max_sun_zenith_angle"]

    scmap_composite = composite(
        con=con,
        temporal_extent=temporal_extent,
        spatial_extent=bbox,
        max_cloud_cover=80,
        nmad_sigma=nmad_sigma,
        max_sun_zenith_angle=max_sun_zenith_angle,
        compute_ci=True
    )

    job = scmap_composite.create_job(title="scmap_composite")
    job.start_and_wait()
    path_out.mkdir(parents=True, exist_ok=True)
    job.get_results().download_files(path_out.as_posix())


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="scmap openEO implmementation")
    parser.add_argument("--test", action="store_true", help="Run test case")

    args = parser.parse_args()
    if args.test:
        test_run(d_test_setup=test_setup_large)
    else:
        # save process to json
        with open(Path(__file__).parent / "scmap_composite.json", "w") as fp:
            json.dump(generate(), fp, indent=2)

