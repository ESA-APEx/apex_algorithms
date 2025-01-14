# Multi-output Gaussian process regression (MOGPR)

The MOGPR service is designed to enable multi-output regression analysis using Gaussian Process Regression (GPR) on geospatial data. It provides a powerful tool for understanding and predicting spatiotemporal phenomena by filling gaps based on other correlated indicators.

## Parameters

The MOGPR service requires the following parameters:

- `datacube`: The input datacube that contains the data to be gap-filled.

## Usage

The MOGPR service can be used as follows:

```python

import openeo

## Setup of parameters
spat_ext = {
    "type": "Polygon",
    "coordinates": [
 [
 [
                5.170012098271149,
                51.25062964728295
 ],
 [
                5.17085904378298,
                51.24882567194015
 ],
 [
                5.17857421368097,
                51.2468515482926
 ],
 [
                5.178972704726344,
                51.24982704376254
 ],
 [
                5.170012098271149,
                51.25062964728295
 ]
 ]
 ]
}
temp_ext = ["2022-05-01", "2023-07-31"]

## Setup connection to openEO
eoconn = openeo.connect(
        "openeo.dataspace.copernicus.eu"
 ).authenticate_oidc("CDSE")

## Create a base NDVI datacube that can be used as input for the service
base = eoconn.load_collection('SENTINEL2_L2A',
                                  spatial_extent=spat_ext,
                                  temporal_extent=temp_ext,
                                  bands=["B04", "B08", "SCL"])
mask = scl.process("to_scl_dilation_mask", data=scl)
base_cloudmasked = base.mask(mask)
base_ndvi = base_cloudmasked.ndvi(red="B04", nir="B08")

process_id = "fusets_mogpr"
namespace_url = "public_url"    # publised URL of the process
## Create a processing graph from the MOGPR process using an active openEO connection
mogpr = eoconn.datacube_from_process(
       process_id=process_id,
       namespace= namespace_url,
      data=base_ndvi, 
 )


## Calculate the average time series value for the given area of interest
mogpr = mogpr.aggregate_spatial(spat_ext, reducer='mean')

# Execute the service as a batch process
mogpr_job = mogpr.execute_batch('./mogpr.json', out_format="json", title=f'FuseTS - MOGPR') 

```

## Output

The User-Defined-Process (UDP) produces a datacube that contains a gap-filled time series for all pixels within the specified temporal and spatial range. This datacube can be seamlessly integrated with other openEO processes.