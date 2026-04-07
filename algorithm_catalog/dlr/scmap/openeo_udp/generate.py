import json
from pathlib import Path

import openeo
from openeo.api.process import Parameter
from openeo.processes import array_create, and_, if_, inspect, array_element, not_, or_

# from openeo.processes import sqrt as sqrt_, add, multiply, subtract
from openeo.rest.udp import build_process_dict
from openeo.rest.connection import Connection

from typing import List, Union

d_description = {
    "te": "Temporal extend",
    "bb": "Bounding Box",
    "cc": "Maximum allowed scene-wide cloud cover for the scene to be considered in the composite",
    "sigma": "Sigma for median absolute deviation outlier detection in Band B02, default=3.0",
    "sza": "Maximum sun zenith angle (at pixel level) for a pixel to be considered in the composite. Default value (70.0) derived from Sen2Cor recommendation.",
    "do_ci": "Computes the 95-Confidence interval for each band. Will increase credit consumption and execution time significantly",
    "do_mref": "Computes the mean reflectance for each band. Will increase credit consumption and execution time",
    "do_mask": "Computes the mask. Will increase credit consumption and execution time",
}

S2_BANDS = "B02 B03 B04 B05 B06 B07 B08 B8A B11 B12".split()
RES_BANDS = {
    "SRC": [f"SRC_{b}" for b in S2_BANDS],
    "SRC-STD": [f"SRC-STD_{b}" for b in S2_BANDS],
    "MREF": [f"MREF_{b}" for b in S2_BANDS],
    "MREF-STD": [f"MREF-STD_{b}" for b in S2_BANDS],
    "SRC-CI": [f"SRC-CI95_{b}" for b in S2_BANDS],
    "SFREQ-VALID": "VPC",
    "SFREQ-COUNT": "BSC",
    "SFREQ-FREQ": "BSF",
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
    "snow": 11,
}

# def scl_to_masks(scl_layer):
#         to_mask = openeo.processes.any(
#             array_create(
#                 [
#                     scl_layer == SCL_LEGEND["cloud_shadows"],
#                     scl_layer == SCL_LEGEND["cloud_medium_probability"],
#                     scl_layer == SCL_LEGEND["cloud_high_probability"],
#                     scl_layer == SCL_LEGEND["thin_cirrus"],
#                     scl_layer == SCL_LEGEND["saturated_or_defective"],
#                     scl_layer == SCL_LEGEND["snow"],
#                     scl_layer == SCL_LEGEND["no_data"],
#                     scl_layer == SCL_LEGEND["dark_area_pixels"],
#                     scl_layer == SCL_LEGEND["unclassified"],
#                 ]
#             ),
#         )
#
#         return to_mask


def nmad(cube: openeo.DataCube, nmad_sigma: float | Parameter, min_offset=80.0) -> openeo.DataCube:
    def _nmad(ts):
        med = ts.median()
        absdev = (ts - med).absolute()
        mad = absdev.median()
        nmad = mad * 1.4826

        upper = med + nmad_sigma * nmad
        min_limit = med + min_offset
        return and_(ts.gt(upper), ts.gt(min_limit))  # logicals need to be called as functions

    b02 = cube.band("B02")
    is_outlier = b02.apply_dimension(dimension="t", process=_nmad)
    return cube.mask(is_outlier)


def _ci95(combined_cube: openeo.DataCube, sd_bands: List[str], n: str) -> openeo.DataCube:
    """Compute 95% confidence interval according to
    +- 1.96 * (sd / sqrt(n))
    """
    z = 1.96
    cubes = []
    n_sqrt = combined_cube.band(n).apply("sqrt")

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


def composite(
    con: Connection,
    temporal_extent: List[str] | Parameter,
    spatial_extent: dict | Parameter,
    max_cloud_cover: int | Parameter,
    nmad_sigma: float | Parameter,
    max_sun_zenith_angle: float = 70,
    # compute_ci: bool|Parameter=False,
    compute_mref: bool | Parameter = False,
    compute_mask: bool | Parameter = False,
) -> openeo.DataCube:
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
    compute_mref : bool, optional
        Can be disabled if Mean Reflectance Computation is not needed. Speeds up computation and saves credits
    compute_mask : bool, optional
        Can be disabled to save compuation time and credits
    Returns
    -------
    openeo.DataCube
        A merged data cube containing the Bare Surface Composite and by-products
    """

    ### Input Data ###
    cube = con.load_collection(
        "SENTINEL2_L2A",
        bands=S2_BANDS + ["SCL", "sunZenithAngles"],
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        max_cloud_cover=max_cloud_cover,
    ).resample_spatial(resolution=20, method="average")

    s2_cube = cube.filter_bands(S2_BANDS)
    scl = cube.band("SCL")
    sza = cube.band("sunZenithAngles")

    worldcover = con.load_collection(
        "ESA_WORLDCOVER_10M_2021_V2",
        spatial_extent=spatial_extent,
        # temporal_extent=["2021-01-01", "2021-12-31"],
        bands=["MAP"],
    )
    worldcover = worldcover.reduce_dimension(dimension="t", reducer="first")

    # cond_scl = scl.apply(process=scl_to_masks)
    cond_scl = (
        (scl == SCL_LEGEND["no_data"])
        | (scl == SCL_LEGEND["saturated_or_defective"])
        | (scl == SCL_LEGEND["dark_area_pixels"])
        | (scl == SCL_LEGEND["cloud_shadows"])
        | (scl == SCL_LEGEND["unclassified"])
        | (scl == SCL_LEGEND["cloud_medium_probability"])
        | (scl == SCL_LEGEND["cloud_high_probability"])
        | (scl == SCL_LEGEND["thin_cirrus"])
        | (scl == SCL_LEGEND["snow"])
    )
    # cloud mask dilation
    k = 11
    if k > 1:
        kernel = array_create([[int(1)] * k for _ in range(k)])
        cond_scl_cloud = (scl == 3) | (scl == 8) | (scl == 9) | (scl == 10)
        dilated_mask = cond_scl_cloud.apply_kernel(kernel=kernel)
        dilated_mask = dilated_mask > 0.01
    cond_sza = sza > max_sun_zenith_angle

    # dilated_mask = dilated_mask * 1 > 0     # Force it to boolean ??
    # combined_mask = cond_sza | cond_scl | dilated_mask
    # combined_mask = or_(or_(cond_sza, cond_scl),dilated_mask)
    # s2_cube = s2_cube.mask(combined_mask)
    s2_cube = s2_cube.mask(cond_sza)
    s2_cube = s2_cube.mask(cond_scl)
    if k > 1:
        s2_cube = s2_cube.mask(dilated_mask)

    sfreq_valid = (
        s2_cube.band(S2_BANDS[0])
        .reduce_dimension(dimension="t", reducer="count")
        .add_dimension(name="bands", label=RES_BANDS["SFREQ-VALID"], type="bands")
    )

    ### Threshold image ###
    stac_url_th_img = "https://raw.githubusercontent.com/Schiggebam/dlr_scmap_resources/refs/heads/main/th_S2_s2cr_buffered_stac_yflip_no_t.json"
    th_item = con.load_stac(stac_url_th_img, bands=["S2_s2cr_pvir2_threshold_img"], spatial_extent=spatial_extent)
    thresholds = th_item.resample_cube_spatial(s2_cube, method="bilinear").reduce_dimension(
        dimension="bands", reducer="first"
    )
    worldcover = worldcover.resample_cube_spatial(s2_cube, method="near")

    # s2_cube = s2_cube.merge_cubes(thresholds)

    # b_scl = s2_cube.band("SCL")
    # cond_scl = ~((b_scl == SCL_LEGEND['vegetation']) | (b_scl == SCL_LEGEND['not_vegetated']) | (b_scl == SCL_LEGEND['water']))
    # s2_cube = s2_cube.mask(cond_scl)

    s2_merged = s2_cube

    #### MREF ####
    if compute_mref:
        s2_cube = nmad(s2_cube, 4.0)
        mref = s2_cube.reduce_dimension(dimension="t", reducer="mean").filter_bands(S2_BANDS)
        mref_std = s2_cube.reduce_dimension(dimension="t", reducer="sd").filter_bands(S2_BANDS)

        mref = mref.rename_labels(dimension="bands", target=RES_BANDS["MREF"], source=S2_BANDS)
        mref_std = mref_std.rename_labels(dimension="bands", target=RES_BANDS["MREF-STD"], source=S2_BANDS)

    # sfreq_valid.rename_labels(dimension="bands", target=RES_BANDS["SFREQ-VALID"], source=S2_BANDS[0])
    ######## SRC ########

    b_04 = s2_merged.band("B04")
    b_08 = s2_merged.band("B08")
    b_12 = s2_merged.band("B12")

    ndvi = (b_08 - b_04) / (b_08 + b_04)
    nbr = (b_08 - b_12) / (b_08 + b_12)
    pvir2 = ndvi + nbr

    pvir2_named = pvir2.add_dimension(name="bands", label="pvir2", type="bands")
    th_named = thresholds.add_dimension(name="bands", label="th_img", type="bands")
    th_named = th_named.reduce_dimension(dimension="t", reducer="mean")

    s2_merged = s2_merged.merge_cubes(pvir2_named)
    s2_merged = s2_merged.merge_cubes(th_named)

    th = s2_merged.band("th_img")

    mask = s2_merged.band("pvir2") > th
    s2_masked = s2_merged.mask(mask)
    # s2_masked = s2_masked.filter_bands(S2_BANDS)        # opt

    cond_wc = (worldcover == 50) | (worldcover == 80)
    s2_masked = s2_masked.mask(cond_wc)

    s2_masked = nmad(s2_masked, nmad_sigma)

    sfreq_count = s2_masked.band(S2_BANDS[0]).reduce_dimension(dimension="t", reducer="count")
    # sfc = sfreq_count
    sfreq_count = sfreq_count.add_dimension(name="bands", label=RES_BANDS["SFREQ-COUNT"], type="bands")

    cond_count = sfreq_count < 3
    s2_masked = s2_masked.mask(cond_count)
    sfreq_count = sfreq_count.mask(cond_count)

    src = s2_masked.filter_bands(S2_BANDS).reduce_dimension(dimension="t", reducer="mean")
    src_std = s2_masked.filter_bands(S2_BANDS).reduce_dimension(dimension="t", reducer="sd")

    src = src.rename_labels(dimension="bands", target=RES_BANDS["SRC"], source=S2_BANDS)
    src_std = src_std.rename_labels(dimension="bands", target=RES_BANDS["SRC-STD"], source=S2_BANDS)

    # sfreq_count.rename_labels(dimension="bands", target=RES_BANDS["SFREQ-COUNT"], source=S2_BANDS[0])

    # src_ci = _ci95(src_std, sfreq_count).filter_bands(RES_BANDS["SRC-STD"])
    # src_ci = src_ci.rename_labels(dimension="bands", target=RES_BANDS["SRC-CI"], source=RES_BANDS["SRC-STD"])

    combined_output = src.merge_cubes(src_std).merge_cubes(sfreq_valid).merge_cubes(sfreq_count)

    if compute_mref:
        combined_output = combined_output.merge_cubes(mref).merge_cubes(mref_std)

    # inner math
    # if False:
    #     ci = _ci95(combined_output, RES_BANDS["SRC-STD"], RES_BANDS["SFREQ-COUNT"])   # works but slow
    #     combined_output = combined_output.merge_cubes(ci)
    sfreq_freq = combined_output.band(RES_BANDS["SFREQ-COUNT"]) / combined_output.band(RES_BANDS["SFREQ-VALID"])
    sfreq_freq = sfreq_freq.add_dimension(name="bands", label=RES_BANDS["SFREQ-FREQ"], type="bands")
    # sfreq_freq = sfreq_freq.rename_labels(dimension="bands", target=RES_BANDS["SFREQ-FREQ"], source=[RES_BANDS["SFREQ-COUNT"]])

    combined_output = combined_output.merge_cubes(sfreq_freq)

    ### MASK ###
    if compute_mask:
        masked = s2_merged.band("pvir2") < th
        is_perm_veg = masked.reduce_dimension(dimension="t", reducer="any")
        is_perm_veg = is_perm_veg.apply(process=openeo.processes.not_)
        is_perm_veg = is_perm_veg.apply(process=openeo.processes.round)
        is_perm_veg = is_perm_veg.add(2)

        # TODO test
        # masked = s2_merged.band("pvir2") > th
        # is_perm_veg = masked.reduce_dimension(dimension="t", reducer="all")     # TODO doesn't work because of nans (but should work with ignore_nodata=true)

        worldcover = worldcover.band("MAP")
        is_other = (
            (worldcover == 0)
            | (worldcover == 50)
            | (worldcover == 70)
            | (worldcover == 80)
            | (worldcover == 90)
            | (worldcover == 95)
        )

        bspc = combined_output.band(RES_BANDS["SFREQ-COUNT"])  # (x,y)

        z = is_perm_veg.multiply(0)
        z = z.mask(is_perm_veg, replacement=2)
        z = z.mask((bspc > 2), replacement=1)
        z = z.mask(is_other, replacement=3)
        z = z.mask((z == 0))
        z = z.add_dimension("bands", "MASK", "bands")
        combined_output = combined_output.merge_cubes(z)

    return combined_output


def auth(url: str = "openeo.dataspace.copernicus.eu") -> Connection:
    connection = openeo.connect(url=url)
    connection.authenticate_oidc()
    return connection


def generate() -> dict:
    # TODO (paul) : Possibily replace with openeo.connect("openeofed.dataspace.copernicus.eu")
    con: Connection = auth()

    temporal_extent = Parameter.temporal_interval(name="temporal_extent", description=d_description["te"])
    spatial_extent = Parameter.bounding_box(
        name="bounding_box",
        description=d_description["bb"],
        default={"west": 11.1, "south": 48.0, "east": 11.3, "north": 48.2, "crs": "EPSG:4326"},
    )
    max_scene_cloud_cover = Parameter.number(name="max_cloud_cover", description=d_description["cc"], default=80)
    # max_sun_zenith_angle = Parameter.number(
    #     name = "max_sun_zenith_angle",
    #     description=d_description["sza"],
    #     default=70
    # )
    nmad_sigma = Parameter.number(name="nmad_sigma", description=d_description["sigma"], default=3.0)

    # compute_ci = Parameter.boolean(
    #     name = "compute_ci",
    #     description=d_description["do_ci"],
    #     default=False
    # )

    compute_mref = Parameter.boolean(name="compute_mref", description=d_description["do_mref"], default=False)

    compute_mask = Parameter.boolean(name="compute_mask", description=d_description["do_mask"], default=False)

    scmap_composite = composite(
        con=con,
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        max_cloud_cover=max_scene_cloud_cover,
        nmad_sigma=nmad_sigma,
        # compute_ci=compute_ci,
        compute_mref=compute_mref,
        compute_mask=compute_mask,
        # max_sun_zenith_angle=max_sun_zenith_angle
    )

    schema = {
        "description": "Bare surface composite with statistical producs",
        "schema": {"type": "object", "subtype": "datacube"},
    }

    return build_process_dict(
        process_graph=scmap_composite,
        process_id="scmap_composite",
        summary="Bare surface composite with statistical producs",
        description=(Path(__file__).parent / "Readme.md").read_text(),
        parameters=[
            temporal_extent,
            spatial_extent,
            max_scene_cloud_cover,
            nmad_sigma,
            # compute_ci,
            compute_mref,
            compute_mask,
            # max_sun_zenith_angle
        ],
        returns=schema,
        categories=["sentinel-2", "composites", "bare surface"],
    )


test_setup_tiny = {
    "bbox": {"west": 11.1, "south": 48.1, "east": 11.2, "north": 48.2, "crs": "EPSG:4326"},
    "temporal_extent": ["2025-04-01", "2025-05-07"],
    "nmad_sigma": 3.0,
    "max_sun_zenith_angle": 70.0,
    # "compute_ci": False,
    "compute_mref": True,
    "compute_mask": True,
}

test_setup_git = {
    "bbox": {"west": 11.05, "south": 48.0, "east": 11.3, "north": 48.2, "crs": "EPSG:4326"},
    "temporal_extent": ["2025-04-01", "2025-05-07"],
    "nmad_sigma": 3.0,
    "max_sun_zenith_angle": 70.0,
    # "compute_ci": False,
    "compute_mref": False,
    "compute_mask": True,
}

test_setup_small = {
    "bbox": {"west": 11.1, "south": 48.1, "east": 11.2, "north": 48.2, "crs": "EPSG:4326"},
    "temporal_extent": ["2025-01-01", "2025-12-31"],
    "nmad_sigma": 3.0,
    "max_sun_zenith_angle": 70.0,
    # "compute_ci": False,
    "compute_mref": False,
    "compute_mask": False,
}

test_setup_large = {
    "bbox": {"west": 10.8, "south": 48.0, "east": 11.3, "north": 48.5, "crs": "EPSG:4326"},
    "temporal_extent": ["2025-01-01", "2025-12-31"],
    "nmad_sigma": 3.0,
    "max_sun_zenith_angle": 70.0,
    # "compute_ci": False,
    "compute_mref": False,
    "compute_mask": False,
}


def test_run(d_test_setup=None, path_out=Path("./result/")):
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
        # compute_ci=d_test_setup['compute_ci'],
        compute_mref=d_test_setup["compute_mref"],
        compute_mask=d_test_setup["compute_mask"],
    )

    job = scmap_composite.create_job(title="scmap_composite")
    job.start_and_wait()
    path_out.mkdir(parents=True, exist_ok=True)
    job.describe()
    job.get_results().download_files(path_out.as_posix())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="scmap openEO implmementation")
    parser.add_argument("--test", action="store_true", help="Run test case")

    args = parser.parse_args()
    if args.test:
        test_run(d_test_setup=test_setup_tiny)
    else:
        # save process to json
        with open(Path(__file__).parent / "scmap_composite.json", "w") as fp:
            json.dump(generate(), fp, indent=2)
