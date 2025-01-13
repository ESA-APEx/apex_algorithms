# Sentinel-1 and Sentinel-2 data fusion through multi output gaussian process regression

## Description

Compute a temporal dense timeseries based on the fusion of Sentinel-1 (S1) and Sentinel-2 (S2) using MOGPR.

## Parameters
| Name | Description | Type | Default |
|---|---|---|---------|
| polygon | Polygon representing the AOI on which to apply the data fusion | GeoJSON |         | 
| temporal_extent | Date range for which to apply the data fusion | Array |         |
| s1_collection | S1 data collection to use for the fusion | Text | RVI     |
| s2_collection | S2 data collection to use for fusing the data | Text | NDVI       | 

### Supported collections

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
