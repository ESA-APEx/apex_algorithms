# CropSAR_px

## Description

The `CropSAR_px` process produces Sentinel-2 data cloud-free with a regularity of five-day intervals. 
In the current version of the service, the output types supported include:

- NDVI
- FAPAR
- FCOVER

> The 'startdate' parameter corresponds to the date of the first image in the result. 
> From this start date, a new image will be generated every five days up to, or beyond, the specified end date.

## Usage

The following example demonstrates how the 'CropSAR_px' process can be executed using an OpenEO batch job. 
This batch job produces a netCDF file containing the results. 
Additionally, the `GeoTIFF` format can be specified to yield separate files for each date. 

```python

import openeo
connection = openeo.connect("openeofed.dataspace.copernicus.eu").authenticate_oidc()

spat_ext = {
        "coordinates": [
          [
            [
              5.178303838475193,
              51.252856237848164
            ],
            [
              5.178003609252369,
              51.25109194151486
            ],
            [
              5.179280940922463,
              51.25103833409551
            ],
            [
              5.179565949577788,
              51.25278555186941
            ],
            [
              5.178303838475193,
              51.252856237848164
            ]
          ]
        ],
        "type": "Polygon"
      }

startdate = "2021-01-01"
enddate = "2021-01-20"
cropsarpx_id = 'cropsar_px'
namespace = "REPLACE_WITH_NAMESPACE"

cropsarpx = connection.datacube_from_process(
    process_id=cropsarpx_id,
    namespace=namespace,
    spatial_extent=spat_ext,
    startdate=startdate,
    enddate=enddate,
    output="NDVI"
)

cropsarpx.execute_batch('results/cropsar_px_290125.nc', title=f'cropsar_px', job_options={
    "executor-memory": "2G",
    "executor-memoryOverhead": "500m",
    "python-memory": "3G"
})

```


Refer to this [blog post](https://blog.vito.be/remotesensing/cropsar2023) for more information on how to run batch jobs.
