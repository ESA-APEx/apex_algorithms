from functools import lru_cache
import numpy as np
from typing import Dict
from openeo.udf.xarraydatacube import XarrayDataCube
from openeo.udf.debug import inspect
from biopar.bioparnp import BioParNp

@lru_cache(maxsize=6)
def get_bioparrun(biopar) -> BioParNp:
    return BioParNp(version='3band', parameter=biopar, singleConfig = True)
    
def apply_datacube(cube: XarrayDataCube, context: Dict) -> XarrayDataCube:
    valid_biopars= ['FAPAR','LAI','FCOVER','CWC','CCC']
    biopar = context.get('biopar_type', 'FAPAR') 
    if biopar not in valid_biopars:
        biopar = 'FAPAR'
        inspect(biopar, "is not in valid Biopar list, defaulting to FAPAR") 
    
    inarr = cube.get_array()
    ds_date = inarr
    
    from numpy import cos, radians
    scaling_bands = 0.0001

    saa = ds_date.sel(bands='sunAzimuthAngles')
    sza = ds_date.sel(bands='sunZenithAngles')
    vaa = ds_date.sel(bands='viewAzimuthMean')
    vza = ds_date.sel(bands='viewZenithMean')
    
    B03 = ds_date.sel(bands='B03') * scaling_bands
    B04 = ds_date.sel(bands='B04') * scaling_bands
    B8 = ds_date.sel(bands='B08') * scaling_bands
    g1 = cos(radians(vza))
    g2 = cos(radians(sza))
    g3 = cos(radians(saa - vaa))
    #### FLATTEN THE ARRAY ####
    flat = list(map(lambda arr: arr.flatten(), [B03.values, B04.values,B8.values, g1.values, g2.values, g3.values]))
    bands = np.array(flat)

    # inspect the parameter passed
    inspect(biopar, "biopar parameter passed to the UDF") 

    #### CALCULATE THE BIOPAR BASED ON THE BANDS #####
    image = get_bioparrun(biopar).run(bands, output_scale=1,output_dtype=np.float32,minmax_flagging=False)  # netcdf algorithm
    as_image = image.reshape((g1.shape))
    ## set nodata to nan
    as_image[np.where(np.isnan(B03))] = np.nan
    xr_biopar = vza.copy()
    xr_biopar.values = as_image
    
    return XarrayDataCube(xr_biopar)  # xarray.DataArray(as_image,vza.dims,vza.coords)'''