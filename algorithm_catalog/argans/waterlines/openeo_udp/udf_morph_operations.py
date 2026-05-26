# /// script
# dependencies = [
#   "scikit-image",
#   "scipy",
# ]
# ///

from openeo.udf import XarrayDataCube, inspect
import numpy as np
import xarray as xr
from scipy.ndimage import binary_fill_holes, binary_opening

DEFAULT_WATER_VALUE = 1


def _build_coastal_water_mask(
    arr: np.ndarray,
    water_value: int = DEFAULT_WATER_VALUE,
    nodata: float | None = 999,
    iterations: int = 1,
) -> np.ndarray:
    """
    Build coastal-water-only mask from land/water mask.
    Inland water is filled.

    Returns:
        0/1 mask where 1 is coastal water and 0 is land
    """
    water = arr == water_value
    if nodata is not None:
        water = water & (arr != nodata)

    # Remove small estuaries
    water = binary_opening(water, iterations=iterations)

    # Remove bridges
    land = ~water
    land = binary_opening(land, iterations=iterations)

    land_filled = binary_fill_holes(land)
    water_filled = ~land_filled
    return water_filled.astype(np.uint8)


def apply_datacube(cube: XarrayDataCube, context: dict) -> XarrayDataCube:
    """Apply morphological algorithms on DataCube"""

    cube_array: xr.DataArray = cube.get_array()
    inspect(data=[cube_array.shape], message="Input UDF cube_array shape")

    cube_array = cube_array.astype(np.uint8)

    cube_array_3d = cube_array.squeeze(dim="bands")

    modified = xr.apply_ufunc(
        _build_coastal_water_mask,
        cube_array_3d,
        input_core_dims=[["y", "x"]],
        output_core_dims=[["y", "x"]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[np.uint8],
        kwargs={
            "water_value": DEFAULT_WATER_VALUE,
            "nodata": 999,
            "iterations": context["iterations"],
        },
    )

    modified_da = xr.DataArray(
        modified,
        coords={
            "t": cube_array.coords["t"],
            "y": cube_array.coords["y"],
            "x": cube_array.coords["x"],
        },
        dims=["t", "y", "x"],
    )
    modified_da = modified_da.expand_dims(dim={"bands": cube_array.coords["bands"]})
    modified_da = modified_da.transpose("t", "bands", "y", "x")

    return XarrayDataCube(modified_da)
