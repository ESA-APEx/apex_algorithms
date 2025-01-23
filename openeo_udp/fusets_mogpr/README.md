# Sentinel-1 and Sentinel-2 data fusion through Multi-output Gaussian process regression (MOGPR)

This service is designed to enable multi-output regression analysis using Gaussian Process Regression (GPR) on geospatial data. It provides a powerful tool for understanding and predicting spatiotemporal phenomena by filling gaps based on other correlated indicators. This service focusses on the fusion of Sentinel-1 and Sentinel-2 data, allowing the user to select one of the predefined data sources.

## Parameters

The `fusets_mogpr_s1s2` service requires the following parameters:

| Name | Description | Type | Default |
|---|---|---|---------|
| polygon | Polygon representing the AOI on which to apply the data fusion | GeoJSON |         | 
| temporal_extent | Date range for which to apply the data fusion | Array |         |
| s1_collection | S1 data collection to use for the fusion | Text | RVI     |
| s2_collection | S2 data collection to use for fusing the data | Text | NDVI       | 

## Supported collections

#### Sentinel-1

* RVI
* GRD

#### Sentinel-2

* NDVI
* FAPAR
* LAI
* FCOVER
* EVI
* CCC
* CWC

## Limitations

The spatial extent is limited to a maximum size equal to a Sentinel-2 MGRS tile (100 km x 100 km).

## Output

This User-Defined-Process (UDP) produces a datacube that contains a gap-filled time series for all pixels within the specified temporal and spatial range. This datacube can be seamlessly integrated with other openEO processes.