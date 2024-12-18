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

> Note that generating multiple GeoTIFF files as output is a unique feature available only in a batch job.

By default, the output variable is set to NDVI.
However, by supplying one of the supported values listed above to the output parameter, a different result can be obtained.

