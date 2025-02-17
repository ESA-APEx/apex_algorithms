from numpy import float32
import xarray as xr
import numpy as np
from openeo.udf.xarraydatacube import XarrayDataCube


def mask_values(data: xr.DataArray, values: list, drop: bool) -> xr.DataArray:
    """
    Mask a list of values in a given xarray DataArray
    :param data: xarray DataArray to mask
    :param values: Values that should be masked
    :param drop: Flag indicating if the values should be removed from the array
    :return:
    """
    result = data.copy()
    for value in values:
        result = result.where(data != value, drop=drop)
    return result

def generate_map(array: xr.DataArray, band: str, mask: float, raw: bool) -> XarrayDataCube:
    """
    Generate the variability map by taking the relative difference between all pixel values and the median value of
    the field. These differences are then categorized in bins to represent the different zones in the field.
    :param array: Data array containing the pixel values
    :param band: Name of the band on which to base the variability map
    :param mask: Value that should be masked in the data array
    :param raw:  Flag indicating if the raw values should be returned
    :return: DataCube containing the same set of pixels but the value is set to one of the different zones
    """
    # Get the x array containing the time series
    values = array.where(array != mask).astype(float32)
    pixels = mask_values(data=values, values=[mask], drop=True)
    medians = pixels.median(dim=["x", "y"], skipna=True)
    min = 0.85
    max = 1.15
    step = 0.1
    relative_diff = (1 + (values - medians) / medians) * 100

    if raw:
        data = relative_diff
    else:
        bins = np.arange(min, max + step, step)
        bins = np.concatenate([[0], bins, [255]])
        bins = bins * 100
        data = np.digitize(relative_diff,
                              bins=bins).astype(float32)
        data = np.ma.masked_array(data=data, mask=(data == 6), fill_value=np.nan).filled()

    result = array.copy()
    result.values = data
    return XarrayDataCube(result)


def apply_datacube(cube: XarrayDataCube, context) -> XarrayDataCube:
    mask_value = context.get('mask_value', 999.0)
    raw = context.get('raw', False)
    band = context.get('band', 'FAPAR')
    return generate_map(array=cube.get_array(), band=band, mask=mask_value, raw=raw)